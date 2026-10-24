# -*- coding: utf-8 -*-
"""Phase 5 + Phase 8：端到端未决演示 + 失败图库。

两件事
------
1. **未决路径的端到端验证**（不是单元测试，是真数据上的整条链路）：
   正常 / 断网 / 版本不符 三种解析器状态，各自跑一遍全部测试图，统计
   本地裁决、升级、未决的数量，并断言"断网与版本不符时绝不产生正常判决"。

2. **失败图库**：把三类样本挑出来并叠上真值掩码
   * 必须升级的（区间横跨阈值）——筛查的代价来源；
   * 本地裁决但离阈值最近的——最脆弱的那批；
   * 真值面积最小的缺陷——小缺陷是否被漏（handout A11 要求分层）。

输出：`reports/figures/gallery_<cat>.png/.pdf` + `logs/w8_gallery.json`

用法
----
    python scripts/failure_gallery.py --category bottle --shot 16 --ratio 0.10
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "mvtec_ad"
CACHE = ROOT / "cache" / "features"
FIG = ROOT / "reports" / "figures"
OUT = ROOT / "logs"

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def load(cat):
    f = sorted(CACHE.glob(f"{cat}_*.npz"))[0]
    z = np.load(f, allow_pickle=True)
    return z["feats"], z["paths"], z["split"], z["roles"], json.loads(str(z["meta"]))


def mask_of(path: str) -> Path | None:
    p = Path(path)
    parts = p.parts
    try:
        i = parts.index("test")
    except ValueError:
        return None
    if parts[i + 1] == "good":
        return None
    m = Path(*parts[:i]) / "ground_truth" / parts[i + 1] / (p.stem + "_mask.png")
    return m if m.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", default="bottle")
    ap.add_argument("--shot", type=int, default=16)
    ap.add_argument("--ratio", type=float, default=0.10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--topn", type=int, default=4)
    args = ap.parse_args()

    sys.path.insert(0, str(ROOT / "scripts"))
    from screening import (ScreenIndex, Resolver, BankVersion, bank_sha256,
                           batch_image_scores)

    cat = args.category
    feats, paths, split, roles, meta = load(cat)
    ref = np.where(roles == "reference_fit")[0]
    rng = np.random.default_rng(args.seed)
    take = np.sort(rng.choice(ref, size=min(args.shot, len(ref)), replace=False))
    bank = feats[take].reshape(-1, feats.shape[2])
    k = max(2, int(round(args.ratio * len(bank))))
    idx = ScreenIndex(bank, k=k, levels=1, seed=args.seed)
    v = BankVersion(meta["encoder"], f"resize{meta['resize']}/crop{meta['imagesize']}",
                    bank_sha256(bank), "max_patch", 0.0, k, args.ratio, 1)

    cal = np.where(roles == "calibration")[0]
    t = float(np.percentile(batch_image_scores(feats, cal, bank), 95))
    v.threshold = t
    test_rows = np.where((split == "test_good") | (split == "test_defect"))[0]
    truth_scores = batch_image_scores(feats, test_rows, bank)

    # ---------- 1. 端到端未决演示 ----------
    print(f"[{cat}] t={t:.4f}  库={len(bank):,} patch  k={k}")
    demo = {}
    for name, kwargs in (("normal", {}),
                         ("offline", {"available": False}),
                         ("version_mismatch", {"served_version": "deadbeef"})):
        res = Resolver(bank, v, **kwargs)
        counts = {"local": 0, "escalated": 0, "unresolved": 0,
                  "normal_decisions": 0, "alarm_decisions": 0}
        for i, r in enumerate(test_rows):
            lo, hi = idx.image_bounds(feats[r])
            if hi <= t:
                dec, why = "normal", "local"
            elif lo > t:
                dec, why = "alarm", "local"
            else:
                dec, why = res.resolve(feats[r], t)
                why = "escalated" if dec is not None else why
            if why == "local":
                counts["local"] += 1
            elif why == "escalated":
                counts["escalated"] += 1
            elif str(why).startswith("unresolved"):
                counts["unresolved"] += 1
            else:
                raise RuntimeError(f"未知的裁决来源：{why}")
            if dec == "normal":
                counts["normal_decisions"] += 1
            elif dec == "alarm":
                counts["alarm_decisions"] += 1
        if name != "normal":
            assert counts["escalated"] == 0, "解析器不可用时不应有'升级'"
            counts["never_normal_without_resolver"] = counts["normal_decisions"] > 0
        demo[name] = counts
        print(f"  {name:<18} 本地={counts['local']:>3} 升级={counts['escalated']:>3} "
              f"未决={counts['unresolved']:>3} 正常判决={counts['normal_decisions']:>3} "
              f"报警判决={counts['alarm_decisions']:>3}")

    # ---------- 2. 失败图库 ----------
    info = []
    for i, r in enumerate(test_rows):
        lo, hi = idx.image_bounds(feats[r])
        s = float(truth_scores[i])
        amb = (lo <= t < hi)
        if amb:
            kind = "escalated"
        elif s > t:
            kind = "alarm_local"
        else:
            kind = "normal_local"
        m = mask_of(str(paths[r]))
        area = 0
        if m is not None:
            with Image.open(m) as im:
                area = int((np.array(im.convert("L")) > 127).sum())
        info.append(dict(row=int(r), path=str(paths[r]), kind=kind, L=lo, U=hi,
                         s=s, margin=abs(s - t), mask_area=area,
                         is_defect=bool(split[r] == "test_defect")))

    esc = sorted([x for x in info if x["kind"] == "escalated"], key=lambda x: -x["margin"])
    near = sorted([x for x in info if x["kind"] != "escalated"], key=lambda x: x["margin"])
    tiny = sorted([x for x in info if x["is_defect"] and x["mask_area"] > 0],
                  key=lambda x: x["mask_area"])

    picks = [("必须升级（区间横跨阈值）", x) for x in esc[:args.topn]]
    picks += [("本地裁决但最贴近阈值", x) for x in near[:args.topn]]
    picks += [("真值面积最小的缺陷", x) for x in tiny[:args.topn]]

    ncol = 3
    nrow = int(np.ceil(len(picks) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(13.5, 3.6 * nrow))
    axes = np.atleast_1d(axes).ravel()
    for ax, (title, x) in zip(axes, picks):
        with Image.open(x["path"]) as im:
            ax.imshow(np.array(im.convert("RGB")))
        m = mask_of(x["path"])
        if m is not None:
            with Image.open(m) as im:
                mk = np.array(im.convert("L")) > 127
            if mk.any():
                ys, xs = np.where(mk)
                ax.contour(mk, levels=[0.5], colors="yellow", linewidths=1.4)
        ax.set_title(f"{title}\n{k}: L={x['L']:.2f} U={x['U']:.2f} s={x['s']:.2f} t={t:.2f}",
                     fontsize=8.5)
        ax.axis("off")
    for ax in axes[len(picks):]:
        ax.axis("off")
    fig.suptitle(f"{cat}：失败图库（16-shot，{args.ratio:.0%} 库，阈值 {t:.3f}，"
                 f"升级 {len(esc)}/{len(info)}）", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    FIG.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        p = FIG / f"gallery_{cat}.{ext}"
        fig.savefig(p, metadata={"CreationDate": None} if ext == "pdf" else None, dpi=140)
        print(f"  -> {p.name} ({p.stat().st_size//1024} KB)")
    plt.close(fig)

    payload = dict(category=cat, threshold=t, k=k, shot=args.shot, ratio=args.ratio,
                   end_to_end=demo,
                   counts={kk: sum(1 for x in info if x["kind"] == kk)
                           for kk in ("escalated", "alarm_local", "normal_local")},
                   picks=[{**x, "why": w} for w, x in picks],
                   smallest_defect_area=min([x["mask_area"] for x in tiny] or [0]))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"w8_gallery_{cat}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  记录 -> logs/w8_gallery_{cat}.json")


if __name__ == "__main__":
    main()
