# -*- coding: utf-8 -*-
"""Phase 7/8 图：参考数量对本地解决率的影响 + 种子方差。

输入：logs/w7_grid_shots.json、logs/w7_grid_seeds.json
输出：reports/figures/figure_7_shots_seeds.{png,pdf} + manifest
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports" / "figures"
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.25
COLORS = {"bottle": "#1f77b4", "tile": "#2ca02c", "screw": "#d62728"}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    shots = json.loads((ROOT / "logs" / "w7_grid_shots.json").read_text(encoding="utf-8"))["results"]
    seeds = json.loads((ROOT / "logs" / "w7_grid_seeds.json").read_text(encoding="utf-8"))["results"]

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.8))
    for cat, c in COLORS.items():
        rows = sorted([r for r in shots if r["category"] == cat], key=lambda r: r["shot"])
        xs = [r["shot"] for r in rows]
        ys = [r["local_rate"] * 100 for r in rows]
        axes[0].plot(xs, ys, "o-", color=c, label=cat, lw=1.8)
        for x, y, r in zip(xs, ys, rows):
            axes[0].annotate(f"{r['bytes']['total']/1024:.0f}KB", (x, y),
                             textcoords="offset points", xytext=(0, -14),
                             fontsize=7, ha="center", color=c)
    axes[0].set_xscale("log")
    axes[0].set_xticks([1, 4, 16, 40])
    axes[0].set_xticklabels(["1", "4", "16", "40"])
    axes[0].set_xlabel("参考图数量（shot，对数轴）")
    axes[0].set_ylabel("本地裁决比例（%）")
    axes[0].set_title("参考越多，筛查越省？——并非单调\n（标注为索引字节数）", fontsize=10)
    axes[0].legend(fontsize=8)
    axes[0].set_ylim(0, 100)

    cats = list(COLORS)
    data = [[r["local_rate"] * 100 for r in seeds if r["category"] == c] for c in cats]
    bp = axes[1].boxplot(data, tick_labels=cats, widths=0.5, patch_artist=True)
    for patch, c in zip(bp["boxes"], cats):
        patch.set_facecolor(COLORS[c])
        patch.set_alpha(0.35)
    for i, d in enumerate(data, start=1):
        axes[1].scatter(np.full(len(d), i) + np.linspace(-0.08, 0.08, len(d)), d,
                        color=COLORS[cats[i - 1]], s=26, zorder=3)
    axes[1].set_ylabel("本地裁决比例（%）")
    axes[1].set_title("16-shot 下 5 个随机种子的方差\n（全部条件零错判）", fontsize=10)

    fig.suptitle("真实数据：筛查效率对参考数量与参考选择的敏感性", fontsize=11.5)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    FIG.mkdir(parents=True, exist_ok=True)
    man = []
    for ext in ("png", "pdf"):
        p = FIG / f"figure_7_shots_seeds.{ext}"
        fig.savefig(p, metadata={"CreationDate": None} if ext == "pdf" else None, dpi=140)
        man.append({"figure": p.name, "sha256": sha256(p), "bytes": p.stat().st_size})
        print(f"  {p.name:34s} {p.stat().st_size//1024:5d} KB")
    plt.close(fig)

    (FIG / "manifest_figure7.json").write_text(
        json.dumps({"generated_by": "scripts/make_figures_phase7.py", "figures": man},
                   ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
