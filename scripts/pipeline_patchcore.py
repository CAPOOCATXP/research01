# -*- coding: utf-8 -*-
"""Phase 2/3 真实实验：PatchCore 风格参考检测器 + 库压缩的决策分歧 + 区间筛查。

做什么
------
对每个类别（默认 bottle/tile/screw）：

  1. 冻结 WRN-50 提取 patch 特征（layer2 + layer3，局部邻域聚合后拼接），
     图像分数 = 全图 patch 最近邻距离的**最大值**（max-score reference detector）；
  2. 用 **calibration 角色**的正常图定阈值 t（默认 95 分位 = 名义 5% 误报），
     全程不读任何缺陷标签；
  3. 用 reference-fit 的正常图构建全库 M，再用贪心 k-中心压缩到 1/5/10/25%；
  4. 在测试集（test/good + 全部缺陷图）上比较压缩库与全库的**二元决策**；
  5. 每个压缩库**单独重校准**，看"简单重校准能否消除分歧"；
  6. 在 10% 库上做**逐 cell 半径的区间筛查**，测升级率与本地裁决的一致性。

与 handout 的对应
-----------------
  A7 的 (i)(ii)(iii)(iv)：分歧/召回/区间宽度/字节与时延
  A8 的 L/U 公式与"区间跨阈值就升级"
  A6 的"单独命名的 max-score 参考检测器"（非 PatchCore 重加权分数）

诚实边界
--------
* 这是**自研的 max-score 参考检测器**，不是官方 PatchCore 的数值复现；
  官方重加权分数不在本管线内，也不会与这里的结果混表。
* 阈值只用校准集正常图；缺陷标签只用于事后计算召回/AUROC。

用法
----
    python scripts/pipeline_patchcore.py --categories bottle --limit-images 40   # 冒烟
    python scripts/pipeline_patchcore.py                                       # 全量三类
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
import torchvision
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "logs"
FIG_DIR = ROOT / "reports" / "figures"

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


# --------------------------------------------------------------------------- #
class ImagePaths(Dataset):
    def __init__(self, paths, resize=256, imagesize=224):
        self.paths = paths
        self.tf = transforms.Compose([
            transforms.Resize(resize, interpolation=transforms.InterpolationMode.BILINEAR),
            transforms.CenterCrop(imagesize),
            transforms.ToTensor(),
        ])

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        with Image.open(self.paths[i]) as im:
            x = self.tf(im.convert("RGB"))
        return x, i


class FeatureExtractor:
    """冻结 WRN-50，取 layer2 + layer3，3x3 邻域聚合后拼接（PatchCore 风格）。"""

    def __init__(self, device="cuda"):
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        m = torchvision.models.wide_resnet50_2(weights=torchvision.models.Wide_ResNet50_2_Weights.IMAGENET1K_V1)
        m.eval()
        for p in m.parameters():
            p.requires_grad_(False)
        self.model = m.to(self.device)
        self.layer2 = torch.nn.AvgPool2d(3, 1, 1)
        self.layer3 = torch.nn.AvgPool2d(3, 1, 1)

    @torch.no_grad()
    def embed(self, batch):
        x = batch.to(self.device, non_blocking=True)
        feats = []
        for name in ("layer2", "layer3"):
            y = self.model.get_submodule(name)(x) if name == "layer2" else self.model.get_submodule(name)(x)
            feats.append(y)
        raise RuntimeError("unreachable")


def build_extractor(device):
    """用 forward hook 一次前向拿到 layer2/layer3，避免改动模型结构。"""
    model = torchvision.models.wide_resnet50_2(
        weights=torchvision.models.Wide_ResNet50_2_Weights.IMAGENET1K_V1).eval()
    for p in model.parameters():
        p.requires_grad_(False)
    model = model.to(device)
    store = {}

    def hook(name):
        def f(_m, _i, o):
            store[name] = o
        return f

    model.layer2.register_forward_hook(hook("layer2"))
    model.layer3.register_forward_hook(hook("layer3"))

    def embed(batch):
        with torch.no_grad():
            model(batch.to(device, non_blocking=True))
            l2, l3 = store["layer2"], store["layer3"]
            l3 = F.interpolate(l3, size=l2.shape[-2:], mode="bilinear", align_corners=False)
            f = torch.cat([l2, l3], dim=1)                       # (B, 1536, H, W)
            f = F.avg_pool2d(f, 3, 1, 1)                          # 局部邻域聚合
            B, C, H, W = f.shape
            return f.permute(0, 2, 3, 1).reshape(B, H * W, C)     # (B, P, C)
    return embed, model


def load_bank_and_test(args, embed, device):
    """返回 dict：bank(参考拟合正常图 patch)、calib 分数、test 正常/缺陷图分数。"""
    man = ROOT / "manifests"
    res = {}
    for cat in args.categories:
        t0 = time.perf_counter()
        if args.ref_mode == "all":
            ref = [str(p) for p in sorted((ROOT / "data" / "mvtec_ad" / cat / "train" / "good").glob("*.png"))]
        else:
            ref = [str(ROOT / "data" / "mvtec_ad" / r["relative_path"])
                   for r in _read_csv(man / f"{cat}_reference_fit.csv")]
        cal = [str(ROOT / "data" / "mvtec_ad" / r["relative_path"])
               for r in _read_csv(man / f"{cat}_calibration.csv")]
        test_good_dir = ROOT / "data" / "mvtec_ad" / cat / "test" / "good"
        test_bad = sorted((ROOT / "data" / "mvtec_ad" / cat / "test").glob("*/*.png"))
        test_bad = [p for p in test_bad if p.parent.name != "good"]
        test_good = sorted(test_good_dir.glob("*.png"))

        if args.limit_images:
            ref = ref[:args.limit_images]
            cal = cal[:args.limit_images]
            test_good = test_good[:args.limit_images]
            test_bad = test_bad[:args.limit_images]

        bank = _embed_paths(ref, embed, device, args)
        s_cal = _image_scores(cal, embed, device, args, bank)
        s_good = _image_scores(test_good, embed, device, args, bank)
        s_bad = _image_scores(test_bad, embed, device, args, bank)
        res[cat] = dict(bank=bank, s_cal=s_cal, s_good=s_good, s_bad=s_bad,
                        n_ref=len(ref), n_cal=len(cal),
                        n_good=len(test_good), n_bad=len(test_bad),
                        seconds=time.perf_counter() - t0)
        print(f"  [{cat}] bank={bank.shape[0]:,} patches | calib={len(cal)} "
              f"test_good={len(test_good)} test_defect={len(test_bad)}  "
              f"({res[cat]['seconds']:.0f}s)")
    return res


def _read_csv(p: Path):
    import csv
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _embed_paths(paths, embed, device, args):
    ds = ImagePaths(paths, args.resize, args.imagesize)
    dl = DataLoader(ds, batch_size=args.batch, shuffle=False, num_workers=0)
    chunks = []
    for x, _ in dl:
        chunks.append(embed(x).cpu())
    F_all = torch.cat(chunks, dim=0)                     # (N, P, C)
    P = F_all.shape[1]
    flat = F_all.reshape(-1, F_all.shape[-1])            # (N*P, C)
    if flat.shape[0] > args.max_bank:
        g = torch.Generator().manual_seed(0)
        idx = torch.randperm(flat.shape[0], generator=g)[:args.max_bank]
        flat = flat[idx]
    return flat.contiguous()


def _image_scores(paths, embed, device, args, bank):
    """图像分数 = max over patches of 最近邻距离。"""
    ds = ImagePaths(paths, args.resize, args.imagesize)
    dl = DataLoader(ds, batch_size=args.batch, shuffle=False, num_workers=0)
    bank_d = bank.to(device)
    bn = bank_d.norm(dim=1) ** 2
    out = []
    with torch.no_grad():
        for x, _ in dl:
            f = embed(x)                                  # (B, P, C)
            B, P, C = f.shape
            q = f.reshape(-1, C)
            # 分块算最近距离，避免 (B*P, N) 爆显存
            dmin = []
            for i in range(0, q.shape[0], 4096):
                qq = q[i:i + 4096]
                d2 = qq.norm(dim=1, keepdim=True) ** 2 + bn[None, :] - 2 * qq @ bank_d.T
                dmin.append(d2.clamp_min_(0).min(dim=1).values)
            d = torch.cat(dmin).sqrt().reshape(B, P).max(dim=1).values
            out.append(d.cpu())
    return torch.cat(out).numpy()


def greedy_coreset(bank: torch.Tensor, k: int, device):
    """贪心 k-中心（GPU 上做，等价于 PatchCore 的核心集思想）。"""
    n = bank.shape[0]
    b = bank.to(device)
    g = torch.Generator().manual_seed(0)
    first = int(torch.randint(0, n, (1,), generator=g))
    chosen = [first]
    dmin = (b - b[first]).norm(dim=1)
    for _ in range(k - 1):
        idx = int(torch.argmax(dmin))
        if idx in chosen:
            break
        chosen.append(idx)
        dmin = torch.minimum(dmin, (b - b[idx]).norm(dim=1))
    return torch.tensor(sorted(set(chosen)), dtype=torch.long)


def cell_radii(bank: torch.Tensor, centers_idx: torch.Tensor, device):
    b = bank.to(device)
    C = b[centers_idx]
    assign = torch.empty(b.shape[0], dtype=torch.long, device=device)
    dist = torch.empty(b.shape[0], device=device)
    for i in range(0, b.shape[0], 8192):
        m = b[i:i + 8192]
        d = torch.cdist(m, C)
        v, j = d.min(dim=1)
        assign[i:i + 8192] = j
        dist[i:i + 8192] = v
    radii = torch.zeros(len(C), device=device)
    for j in range(len(C)):
        s = assign == j
        if s.any():
            radii[j] = dist[s].max()
    return C, radii


def screen_scores(paths, embed, device, args, C, radii, t):
    """逐图算 L_x = max_patch L, U_x = max_patch U，并给出筛查结论。"""
    ds = ImagePaths(paths, args.resize, args.imagesize)
    dl = DataLoader(ds, batch_size=args.batch, shuffle=False, num_workers=0)
    Ls, Us = [], []
    with torch.no_grad():
        for x, _ in dl:
            f = embed(x)
            B, P, Cc = f.shape
            q = f.reshape(-1, Cc)
            d = torch.cdist(q, C)
            L = (d - radii[None, :]).clamp_min_(0).min(dim=1).values
            U = d.min(dim=1).values
            Ls.append(L.reshape(B, P).max(dim=1).values.cpu())
            Us.append(U.reshape(B, P).max(dim=1).values.cpu())
    L = torch.cat(Ls).numpy()
    U = torch.cat(Us).numpy()
    dec = np.where(U <= t, "normal", np.where(L > t, "alarm", "escalate"))
    return dec, L, U


def auroc(scores_pos, scores_neg):
    s = np.concatenate([scores_pos, scores_neg])
    y = np.concatenate([np.ones(len(scores_pos)), np.zeros(len(scores_neg))])
    order = np.argsort(s)
    ranks = np.empty(len(s)); ranks[order] = np.arange(1, len(s) + 1)
    # 处理并列：平均秩
    from scipy.stats import rankdata
    ranks = rankdata(s)
    n_pos, n_neg = len(scores_pos), len(scores_neg)
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def run(args):
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    print(f"device={device}  resize={args.resize} imagesize={args.imagesize} "
          f"max_bank={args.max_bank} batch={args.batch}")
    embed, model = build_extractor(device)

    data = load_bank_and_test(args, embed, device)
    results = []
    for cat, d in data.items():
        bank, s_cal, s_good, s_bad = d["bank"], d["s_cal"], d["s_good"], d["s_bad"]
        t = float(np.percentile(s_cal, 95))
        base_good, base_bad = s_good > t, s_bad > t
        au = auroc(s_bad, s_good)
        n_tot = len(s_good) + len(s_bad)
        rec = dict(category=cat, t=t, n_bank=int(bank.shape[0]), dim=int(bank.shape[1]),
                   n_ref=d["n_ref"], n_cal=d["n_cal"], n_test_good=d["n_good"], n_test_defect=d["n_bad"],
                   fullbank=dict(far_normal=float(base_good.mean()), recall=float(base_bad.mean()),
                                 auroc=au, sec=d["seconds"]),
                   compression={}, screening=None)
        print(f"\n[{cat}] t={t:.4f}  FAR={base_good.mean():.3f}  召回={base_bad.mean():.3f}  AUROC={au:.4f}")

        C10 = None
        if args.auroc_only:
            results.append(rec)
            print(f"  AUROC={au:.4f}（复现口径，库={bank.shape[0]:,} patches）")
            continue
        for ratio in args.ratios:
            k = max(2, int(round(ratio * bank.shape[0])))
            idx = greedy_coreset(bank, k, device)
            Mb = bank[idx]
            d_good = _image_scores([str(ROOT / "data" / "mvtec_ad" / cat / "test" / "good" / p.name)
                                    for p in sorted((ROOT / "data" / "mvtec_ad" / cat / "test" / "good").glob("*.png"))][:d["n_good"]],
                                   embed, device, args, Mb)
            bad_paths = [p for p in sorted((ROOT / "data" / "mvtec_ad" / cat / "test").glob("*/*.png"))
                         if p.parent.name != "good"][:d["n_bad"]]
            d_bad = _image_scores([str(p) for p in bad_paths], embed, device, args, Mb)

            dec_good, dec_bad = d_good > t, d_bad > t
            extra = float(((dec_good & ~base_good).sum() + (dec_bad & ~base_bad).sum()) / n_tot)
            missed = float(((~dec_good & base_good).sum() + (~dec_bad & base_bad).sum()) / n_tot)

            t2 = float(np.percentile(_image_scores(
                [str(ROOT / "data" / "mvtec_ad" / r["relative_path"])
                 for r in _read_csv(ROOT / "manifests" / f"{cat}_calibration.csv")][:d["n_cal"]],
                embed, device, args, Mb), 95))
            r_good, r_bad = d_good > t2, d_bad > t2
            re_extra = float(((r_good & ~base_good).sum() + (r_bad & ~base_bad).sum()) / n_tot)
            re_missed = float(((~r_good & base_good).sum() + (~r_bad & base_bad).sum()) / n_tot)

            rec["compression"][str(k)] = dict(
                k=int(k), ratio=ratio, t=t,
                far=float(dec_good.mean()), recall=float(dec_bad.mean()),
                disagree=extra + missed, extra=extra, missed=missed,
                recalibrated=dict(t=t2, far=float(r_good.mean()), recall=float(r_bad.mean()),
                                  disagree=re_extra + re_missed))
            print(f"  {ratio:5.0%} k={k:6d}  分歧={extra + missed:6.2%} "
                  f"(多报 {extra:5.2%}/漏报 {missed:5.2%})  重校准后={re_extra + re_missed:6.2%}")
            if abs(ratio - 0.10) < 1e-9:
                C10 = (idx, Mb)
        # 区间筛查（10% 库）
        if C10 is not None:
            idx, Mb = C10
            Cc, radii = cell_radii(bank, idx, device)
            good_paths = [str(ROOT / "data" / "mvtec_ad" / cat / "test" / "good" / p.name)
                          for p in sorted((ROOT / "data" / "mvtec_ad" / cat / "test" / "good").glob("*.png"))][:d["n_good"]]
            bad_paths = [str(p) for p in sorted((ROOT / "data" / "mvtec_ad" / cat / "test").glob("*/*.png"))
                         if p.parent.name != "good"][:d["n_bad"]]
            sg, Lg, Ug = screen_scores(good_paths, embed, device, args, Cc, radii, t)
            sb, Lb, Ub = screen_scores(bad_paths, embed, device, args, Cc, radii, t)
            allscr = np.concatenate([sg, sb])
            truth = np.concatenate([base_good, base_bad])
            esc = float((allscr == "escalate").mean())
            mism = int(sum(1 for s_, tr in zip(allscr, truth)
                           if (s_ == "normal" and tr) or (s_ == "alarm" and not tr)))
            rec["screening"] = dict(escalate_rate=esc, resolved=1 - esc,
                                    mismatch=mism, n=int(len(allscr)),
                                    radius_mean=float(radii.mean().item()),
                                    radius_p95=float(torch.quantile(radii, 0.95).item()),
                                    width_mean=float(((Ub - Lb).mean() + (Ug - Lg).mean()) / 2))
            print(f"  区间筛查：升级率={esc:6.1%}  本地裁决不一致={mism}  "
                  f"半径均值={rec['screening']['radius_mean']:.4f}")
        results.append(rec)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tag = "repro" if args.auroc_only else ("decision_allref" if args.ref_mode == "all" else "decision_16shot")
    out = OUT_DIR / f"w3_{tag}.json"
    out.write_text(json.dumps({"config": vars(args), "results": results},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果 -> {out}")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--categories", nargs="+", default=["bottle", "tile", "screw"])
    ap.add_argument("--ratios", nargs="+", type=float, default=[0.01, 0.05, 0.10, 0.25])
    ap.add_argument("--resize", type=int, default=256)
    ap.add_argument("--imagesize", type=int, default=224)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--max-bank", type=int, default=20000)
    ap.add_argument("--limit-images", type=int, default=0)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--ref-mode", choices=["manifest", "all"], default="manifest",
                    help="manifest=16 张 reference-fit；all=全部 train/good（复现条件，AUROC 用）")
    ap.add_argument("--auroc-only", action="store_true",
                    help="只算 AUROC（复现口径），不做阈值与压缩实验")
    args = ap.parse_args()
    run(args)


if __name__ == "__main__":
    main()
