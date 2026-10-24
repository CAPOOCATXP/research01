# -*- coding: utf-8 -*-
"""把 w3_real_experiment.json 画成两张图（真实数据，非模拟）。

figure_5_real_disagreement : 分歧 vs 压缩比（固定阈值 / 重校准后），三类各一条
figure_6_real_tradeoff     : 同一张图上叠加"升级率"与"本地解决比例"

设计沿用 make_figures.py 的规矩：只从 JSON 出图、确定性、PDF 关 CreationDate、
中文字体显式指定、双格式 + manifest。
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
SRC = ROOT / "logs" / "w3_decision_16shot.json"
OUT = ROOT / "reports" / "figures"

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


def save(fig, stem, manifest):
    for ext in ("pdf", "png"):
        p = OUT / f"{stem}.{ext}"
        fig.savefig(p, metadata={"CreationDate": None} if ext == "pdf" else None)
        manifest.append({"figure": p.name, "sha256": sha256(p), "bytes": p.stat().st_size})
        print(f"  {p.name:44s} {p.stat().st_size:8d} B")
    plt.close(fig)


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    res = data["results"]
    manifest = []
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- 图 5：分歧 vs 压缩比 ----
    fig, ax = plt.subplots(figsize=(8.6, 5.2))
    for r in res:
        cat = r["category"]
        c = COLORS.get(cat, "gray")
        ks = sorted(r["compression"].items(), key=lambda kv: kv[1]["ratio"])
        xs = [v["ratio"] * 100 for _, v in ks]
        y = [v["disagree"] * 100 for _, v in ks]
        y2 = [v["recalibrated"]["disagree"] * 100 for _, v in ks]
        ax.plot(xs, y, "o-", color=c, lw=1.8, label=f"{cat}：沿用原阈值")
        ax.plot(xs, y2, "s--", color=c, lw=1.4, alpha=0.6, label=f"{cat}：压缩库重校准")
    ax.axhline(2.0, color="black", ls=":", lw=1.2)
    ax.text(1.2, 2.6, "A7 的 2 个百分点证伪门槛", fontsize=8.5)
    ax.set_xlabel("压缩后库大小（占全库 %）")
    ax.set_ylabel("与全库的二元决策分歧（%）")
    ax.set_title("MVTec AD 真实数据：库压缩是否改变报警决策\n"
                 f"（max-score 参考检测器，WRN-50，{res[0]['dim']} 维 patch 特征，"
                 f"阈值取自校准集 95 分位）", fontsize=10.5)
    ax.legend(fontsize=8)
    save(fig, "figure_5_real_disagreement", manifest)

    # ---- 图 6：分歧 vs 升级率（代价） ----
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.9))
    cats = [r["category"] for r in res]
    esc = [r["screening"]["escalate_rate"] * 100 if r.get("screening") else np.nan for r in res]
    resv = [r["screening"]["resolved"] * 100 if r.get("screening") else np.nan for r in res]
    x = np.arange(len(cats))
    axes[0].bar(x - 0.2, esc, width=0.4, color=[COLORS.get(c, "gray") for c in cats], label="必须升级")
    axes[0].bar(x + 0.2, resv, width=0.4, color="#cccccc", label="本地裁决")
    for i, (e, v) in enumerate(zip(esc, resv)):
        axes[0].text(i - 0.2, e + 1.5, f"{e:.1f}%", ha="center", fontsize=9)
        axes[0].text(i + 0.2, v + 1.5, f"{v:.1f}%", ha="center", fontsize=9)
    axes[0].set_xticks(x); axes[0].set_xticklabels(cats)
    axes[0].set_ylabel("图像比例（%）")
    axes[0].set_ylim(0, 110)
    axes[0].set_title("区间筛查（10% 库）：升级 vs 本地裁决")
    axes[0].legend(fontsize=8)

    for r in res:
        ks = sorted(r["compression"].items(), key=lambda kv: kv[1]["ratio"])
        cat = r["category"]
        axes[1].plot([v["ratio"] * 100 for _, v in ks], [v["disagree"] * 100 for _, v in ks],
                     "o-", color=COLORS.get(cat, "gray"), label=cat)
        sc = r.get("screening")
        if sc:
            axes[1].scatter([10], [sc["escalate_rate"] * 100], marker="*", s=180,
                            color=COLORS.get(cat, "gray"), zorder=5)
    axes[1].set_xlabel("压缩后库大小（%）")
    axes[1].set_ylabel("分歧（%）／★=该类别 10% 库的升级率")
    axes[1].set_title("分歧与升级代价：两个量不是一回事")
    axes[1].legend(fontsize=8)
    fig.suptitle("真实数据：压缩的代价（决策分歧）与筛查的代价（升级查询）", fontsize=11.5)
    fig.tight_layout()
    save(fig, "figure_6_real_tradeoff", manifest)

    (OUT / "manifest_real.json").write_text(
        json.dumps({"generated_by": "scripts/make_figures_real.py", "figures": manifest},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"清单 -> {OUT / 'manifest_real.json'}")


if __name__ == "__main__":
    main()
