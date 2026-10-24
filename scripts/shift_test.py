# -*- coding: utf-8 -*-
"""Phase 8：外观变化下的代价（RQ4）。

做法
----
对测试图施加受控外观变换（亮度、对比度、gamma、模糊），**库与阈值都不动**，
重新编码后看：

  * 正常图（test/good）的误报率怎么变；
  * 缺陷图的召回怎么变；
  * 筛查的升级率怎么变（区间是否因此失效）。

这不是数据集上的"真实光照变化"，而是**受控扰动**，报告中必须标注为合成。
之所以有意义：它直接回答"同一个阈值在外观漂移下是否还能用"，
以及"筛查在漂移下是更省还是全崩"。

用法
----
    python scripts/shift_test.py --categories bottle tile screw
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torchvision
from PIL import Image, ImageEnhance, ImageFilter
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "mvtec_ad"
CACHE = ROOT / "cache" / "features"
OUT = ROOT / "logs"
RESIZE, IMAGESIZE, POOL = 256, 224, 3

TRANSFORMS = {
    "identity": lambda im: im,
    "bright+30%": lambda im: ImageEnhance.Brightness(im).enhance(1.30),
    "bright-30%": lambda im: ImageEnhance.Brightness(im).enhance(0.70),
    "contrast+30%": lambda im: ImageEnhance.Contrast(im).enhance(1.30),
    "gamma0.7": lambda im: im.point(lambda v: int(255 * (v / 255) ** 0.7)),
    "blur r=1.2": lambda im: im.filter(ImageFilter.GaussianBlur(1.2)),
}


class Shifted(Dataset):
    def __init__(self, paths, fn):
        self.paths, self.fn = paths, fn
        self.tf = transforms.Compose([
            transforms.Resize(RESIZE, interpolation=transforms.InterpolationMode.BILINEAR),
            transforms.CenterCrop(IMAGESIZE),
            transforms.ToTensor(),
        ])

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        with Image.open(self.paths[i]) as im:
            im = im.convert("RGB")
            im = self.fn(im)
            return self.tf(im), i


def build_embedder(device):
    model = torchvision.models.wide_resnet50_2(
        weights=torchvision.models.Wide_ResNet50_2_Weights.IMAGENET1K_V1).eval()
    for p in model.parameters():
        p.requires_grad_(False)
    model = model.to(device)
    store = {}
    model.layer2.register_forward_hook(lambda m, i, o: store.__setitem__("l2", o))
    model.layer3.register_forward_hook(lambda m, i, o: store.__setitem__("l3", o))

    def embed(batch):
        with torch.no_grad():
            model(batch.to(device))
            l2, l3 = store["l2"], store["l3"]
            l3 = torch.nn.functional.interpolate(l3, size=l2.shape[-2:], mode="bilinear",
                                                 align_corners=False)
            f = torch.nn.functional.avg_pool2d(torch.cat([l2, l3], dim=1), POOL, 1, 1)
            B, C, H, W = f.shape
            return f.permute(0, 2, 3, 1).reshape(B, H * W, C).cpu().numpy()
    return embed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--categories", nargs="+", default=["bottle", "tile", "screw"])
    ap.add_argument("--shot", type=int, default=16)
    ap.add_argument("--ratio", type=float, default=0.10)
    ap.add_argument("--batch", type=int, default=8)
    args = ap.parse_args()

    sys.path.insert(0, str(ROOT / "scripts"))
    from screening import ScreenIndex, batch_image_scores, bank_sha256, BankVersion, Resolver

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    embed = build_embedder(device)
    results = []

    for cat in args.categories:
        z = np.load(sorted(CACHE.glob(f"{cat}_*.npz"))[0], allow_pickle=True)
        feats, paths, split, roles, meta = z["feats"], z["paths"], z["split"], z["roles"], json.loads(str(z["meta"]))
        ref = np.where(roles == "reference_fit")[0]
        rng = np.random.default_rng(0)
        take = np.sort(rng.choice(ref, size=min(args.shot, len(ref)), replace=False))
        bank = feats[take].reshape(-1, feats.shape[2])
        k = max(2, int(round(args.ratio * len(bank))))
        idx = ScreenIndex(bank, k=k, levels=1, seed=0)
        cal = np.where(roles == "calibration")[0]
        t = float(np.percentile(batch_image_scores(feats, cal, bank), 95))

        good_rows = np.where(split == "test_good")[0]
        bad_rows = np.where(split == "test_defect")[0]
        rows = np.concatenate([good_rows, bad_rows])
        row_paths = [str(paths[r]) for r in rows]
        print(f"\n[{cat}] t={t:.4f} k={k}  正常 {len(good_rows)} / 缺陷 {len(bad_rows)}")

        base_dec = None
        for name, fn in TRANSFORMS.items():
            ds = Shifted(row_paths, fn)
            dl = DataLoader(ds, batch_size=args.batch, shuffle=False, num_workers=0)
            chunks = [embed(x) for x, _ in dl]
            f_all = np.concatenate(chunks, axis=0).astype(np.float32)
            scores = batch_image_scores(f_all, np.arange(len(f_all)), bank)
            dec = scores > t
            if base_dec is None:
                base_dec = dec
            esc = 0
            for i in range(len(f_all)):
                lo, hi = idx.image_bounds(f_all[i])
                if not (hi <= t or lo > t):
                    esc += 1
            far = float(dec[:len(good_rows)].mean())
            rec = float(dec[len(good_rows):].mean())
            flips = int((dec != base_dec).sum())
            results.append(dict(category=cat, transform=name, t=t, k=k,
                                far=far, recall=rec, escalated=esc,
                                escalate_rate=esc / len(f_all), flips_vs_identity=flips))
            print(f"  {name:<12} FAR={far:6.1%} 召回={rec:6.1%} "
                  f"升级={esc:3d}/{len(f_all)} ({esc/len(f_all):5.1%})  翻转={flips:3d}")

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "w8_shift.json"
    p.write_text(json.dumps({"config": vars(args), "results": results,
                             "note": "受控合成扰动，非真实光照变化"}, ensure_ascii=False,
                            indent=2), encoding="utf-8")
    print(f"\n结果 -> {p}")


if __name__ == "__main__":
    main()
