# -*- coding: utf-8 -*-
"""生成项目图表（Figure pipeline）。

设计原则
--------
1. **只从机器可读的证据出图**：图的数据源必须是 JSON（例如 logs/w1_vram_limit.json），
   不允许用正则从文本日志里抓数字。文本日志只用于人读和留证。
   （从 W1 起，每个检查脚本都要顺手写 JSON；否则数据不可复核、不可重绘。）
2. **确定性**：不使用任何随机数；同一份输入必须产出逐字节相同的图。
3. **双格式**：同时输出 PDF（矢量，给论文/报告）与 PNG（200 dpi，给快速查看）。
4. **路径可移植**：所有路径都相对脚本所在仓库计算，因此从 GitHub 克隆后可直接重跑。
5. **留指纹**：输出 figures/manifest.json，记录每张图的 sha256 与数据源。

用法
----
    python scripts/make_figures.py                 # 输出到 <repo>/reports/figures
    python scripts/make_figures.py --out D:\\figs   # 指定输出目录

当前三张图（都不依赖数据集）
----------------------------
figure_1_vram_limits     显存峰值 vs batch：安全区 / 溢出警戒（数据源 logs/w1_vram_limit.json）
figure_2_bounds_geometry 六向量两中心例子的几何与区间（与 project/src/w1_bounds_example.py 同一组常数）
figure_3_decision_map    L/U 区间筛查在平面上的决策图：升级查询带有多宽
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Patch
from matplotlib.colors import ListedColormap

# 中文必须显式指定字体，否则 Windows 上会渲染成方框
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 110
plt.rcParams["savefig.bbox"] = "tight"
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.25

ROOT = Path(__file__).resolve().parents[1]        # <repo>
LOGS = ROOT / "logs"

# 与 project/src/w1_bounds_example.py 完全一致的常数（改一处必须改两处）
M = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [2.0, 0.0], [10.0, 0.0], [10.0, 0.0]])
CENTERS = [0, 4]
T = 1.5


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save(fig, out_dir: Path, stem: str, manifest: list, sources: list, note: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext in ("pdf", "png"):
        p = out_dir / f"{stem}.{ext}"
        # PDF 默认会写入 CreationDate，导致同样的数据产出不同的文件哈希；
        # 置空后 PDF 才能做到位级可复现（"图可重现"才不是空话）。
        meta = {"CreationDate": None} if ext == "pdf" else None
        fig.savefig(p, metadata=meta)
        paths.append(p)
    plt.close(fig)
    for p in paths:
        manifest.append({
            "figure": p.name, "sha256": sha256_file(p),
            "bytes": p.stat().st_size, "sources": sources, "note": note,
        })
        print(f"  {p.name:42s} {p.stat().st_size:8d} B  {sha256_file(p)[:16]}…")


# --------------------------------------------------------------------------- #
# Figure 1: 显存峰值 vs batch
# --------------------------------------------------------------------------- #
def figure_1(out_dir: Path, manifest: list):
    src = LOGS / "w1_vram_limit.json"
    if not src.exists():
        print(f"  [skip] 缺少数据源 {src}")
        return
    d = json.loads(src.read_text(encoding="utf-8"))
    total = d["total_MiB"]
    resident = d["backbone_resident_MiB"]
    safe_frac = d.get("safe_fraction", 0.80)
    results = d["results"]

    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    colors = {"256": "#1f77b4", "384": "#2ca02c", "512": "#d62728"}
    offsets = {"256": (8, 9), "384": (8, 11), "512": (8, -20)}
    xs = np.linspace(16, 768, 200)
    for res, r in sorted(results.items()):
        c = colors.get(res, "gray")
        rows = [row for row in r["rows"] if row["status"] == "ok"]
        if not rows:
            continue
        bx = np.array([row["batch"] for row in rows], dtype=float)
        by = np.array([row["peak_MiB"] for row in rows], dtype=float)
        # 线性模型 peak = 常驻 + k * batch，k 由最大实测点拟合
        k = (by.max() - resident) / bx[by.argmax()]
        ax.plot(bx, by, "o", color=c, ms=7, zorder=3,
                label=f"{res}×{res} 实测点")
        ax.plot(xs, resident + k * xs, "-", color=c, lw=1.6, alpha=0.85,
                label=f"{res}×{res} 线性拟合 (k={k:.1f} MiB/张)")
        if r.get("safe_batch"):
            ax.plot([r["safe_batch"]], [resident + k * r["safe_batch"]], "o",
                    mfc="none", mec=c, ms=13, mew=1.6, zorder=4)

    ax.axhline(total, color="black", ls="-", lw=1.3)
    ax.axhline(total * safe_frac, color="black", ls="--", lw=1.3)
    ax.axhspan(total, ax.get_ylim()[1], color="red", alpha=0.07)
    ax.text(16, total + 320, f"物理显存 {total:.0f} MiB —— 超过它就是驱动在用主机内存（不报 OOM）",
            fontsize=8.8, color="darkred")
    ax.text(16, total * safe_frac - 900, f"安全线 = {safe_frac:.0%} 物理显存（{total*safe_frac:.0f} MiB）",
            fontsize=8.8, color="black")

    # 把「安全上限」集中成一个信息框，避免多点标注互相遮挡
    lines = ["安全上限（峰值 ≤ %d%% 物理显存）" % round(safe_frac * 100)]
    for res, r in sorted(results.items()):
        if r.get("safe_batch"):
            lines.append(f"  {res}×{res}  →  batch {r['safe_batch']}")

    ax.text(0.985, 0.035, "\n".join(lines), transform=ax.transAxes,
            fontsize=9, ha="right", va="bottom",
            bbox=dict(boxstyle="round,pad=0.45", fc="white", ec="0.4", alpha=0.95))
    ax.set_xlabel("batch size（张/次前向）")
    ax.set_ylabel("峰值显存（MiB，torch.cuda.max_memory_allocated）")
    ax.set_title("本机显存上限实测：峰值随 batch 线性增长，溢出时不报 OOM\n"
                 f"骨干 wide_resnet50_2 冻结，常驻 {resident:.1f} MiB；"
                 f"设备 {d['device']}；两轮结果一致={d.get('reproducible')}",
                 fontsize=10)
    ax.set_xlim(0, 780)
    ax.legend(fontsize=7.6, loc="upper left", ncol=1, framealpha=0.9)
    save(fig, out_dir, "figure_1_vram_limits", manifest,
         sources=["logs/w1_vram_limit.json"],
         note="实测点来自显存扫描；直线是由实测点拟合的线性模型（peak = 常驻 + k×batch）")


# --------------------------------------------------------------------------- #
# Figure 2: 边界例子的几何 + 区间
# --------------------------------------------------------------------------- #
def _cells():
    C = M[CENTERS]
    d = np.linalg.norm(M[:, None, :] - C[None, :, :], axis=2)
    assign = np.argmin(d, axis=1)
    radii = np.array([d[assign == j, j].max() for j in range(len(C))])
    return C, assign, radii


def _bounds(Q):
    C, _, radii = _cells()
    dM = np.linalg.norm(Q[:, None, :] - M[None, :, :], axis=2)
    s = dM.min(axis=1)
    dc = np.linalg.norm(Q[:, None, :] - C[None, :, :], axis=2)
    L = np.maximum(0.0, dc - radii[None, :]).min(axis=1)
    U = dc.min(axis=1)
    return s, L, U


def figure_2(out_dir: Path, manifest: list):
    C, assign, radii = _cells()
    Q = np.array([[0.5, 0.0], [0.0, 10.0], [3.0, 0.0], [0.0, 3.0], [2.0, 1.5]])
    labels = ["q1", "q2", "q3", "q4", "q5"]
    s, L, U = _bounds(Q)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.0, 5.6),
                                   gridspec_kw={"width_ratios": [1.05, 1.25]})

    # 左：几何
    for j, c in enumerate(C):
        ax1.add_patch(Circle(c, radii[j], fill=False, ls="--",
                             color="tab:orange" if j == 0 else "tab:purple", lw=1.4,
                             label=f"cell{j} 覆盖球 r={radii[j]:.0f}"))
    ax1.scatter(M[:, 0], M[:, 1], s=55, marker="s", color="tab:blue",
                label="参考向量 M（6 个，含一对重复）", zorder=4)
    ax1.scatter(C[:, 0], C[:, 1], s=140, marker="*", color="tab:red",
                label="观测中心 c0, c1", zorder=5)
    for i, q in enumerate(Q):
        ax1.scatter(q[0], q[1], s=70, marker="o", facecolor="none",
                    edgecolor="black", lw=1.4, zorder=6)
        ax1.annotate(labels[i], q, xytext=(5, 5), textcoords="offset points", fontsize=9)
    ax1.annotate("cell1 的两个成员重合于 (10,0)\n→ r1 = 0（半径退化为一点）",
                 xy=(10, 0), xytext=(-150, 60), textcoords="offset points", fontsize=8,
                 arrowprops=dict(arrowstyle="->", lw=0.8))
    ax1.set_aspect("equal")
    ax1.set_xlim(-1.2, 11.6)
    ax1.set_ylim(-1.2, 11.0)
    ax1.set_xlabel("x"); ax1.set_ylabel("y")
    ax1.set_title("(a) 参考集、观测中心与覆盖球", fontsize=10)
    ax1.legend(fontsize=7.4, loc="lower right", framealpha=0.9)

    # 右：区间
    y = np.arange(len(Q))[::-1]
    for i in range(len(Q)):
        ax2.plot([L[i], U[i]], [y[i], y[i]], "-", color="tab:gray", lw=7, alpha=0.55,
                 solid_capstyle="butt", zorder=2)
        ax2.plot([s[i]], [y[i]], "D", color="tab:blue", ms=8, zorder=4,
                 label="s_M(q) 完整库真值" if i == 0 else None)
        ax2.plot([L[i]], [y[i]], "|", color="black", ms=14, mew=2, zorder=5,
                 label="L(q) 下界" if i == 0 else None)
        ax2.plot([U[i]], [y[i]], "|", color="black", ms=14, mew=2, zorder=5,
                 label="U(q) 上界" if i == 0 else None)
    ax2.axvline(T, color="tab:red", ls="--", lw=1.6, label=f"阈值 t = {T}")
    for i in range(len(Q)):
        resolved = "本地解决" if (U[i] <= T or L[i] > T) else "→ 升级查询"
        truth = "alarm" if s[i] > T else "normal"
        ax2.annotate(f"{labels[i]}  真值={truth}  {resolved}",
                     xy=(U[i] + 0.15, y[i]), fontsize=8.4, va="center")
    ax2.set_yticks(y)
    ax2.set_yticklabels(labels)
    ax2.set_xlabel("到参考集的距离")
    ax2.set_xlim(-0.3, max(U.max(), T) + 4.2)
    ax2.set_title("(b) 区间 [L, U] 是否跨过阈值决定能否本地裁决", fontsize=10)
    ax2.legend(fontsize=8, loc="lower right")

    fig.suptitle("六向量 / 两中心边界例子：L(q) ≤ s_M(q) ≤ U(q)（与 w1_bounds_example.py 同一组常数）",
                 fontsize=11.5)
    fig.tight_layout()
    save(fig, out_dir, "figure_2_bounds_geometry", manifest,
         sources=["project/src/w1_bounds_example.py（同一组常数）"],
         note="确定性示意图，不含随机数；区间由 A8 的 L/U 公式直接计算")


# --------------------------------------------------------------------------- #
# Figure 3: 决策图（升级查询带有多宽）
# --------------------------------------------------------------------------- #
def figure_3(out_dir: Path, manifest: list):
    # 0=本地判 normal, 1=本地判 alarm, 2=升级查询
    xs = np.linspace(-1.5, 8.0, 460)
    ys = np.linspace(-1.5, 6.0, 340)
    XX, YY = np.meshgrid(xs, ys)
    Q = np.column_stack([XX.ravel(), YY.ravel()])
    s, L, U = _bounds(Q)
    zone = np.where(U <= T, 0, np.where(L > T, 1, 2)).reshape(XX.shape)
    truth_alarm = (s > T).reshape(XX.shape)

    cmap = ListedColormap(["#cfe8ff", "#ffd6d6", "#ffe9b0"])
    fig, ax = plt.subplots(figsize=(9.0, 6.0))
    ax.imshow(zone, origin="lower", extent=[xs[0], xs[-1], ys[0], ys[-1]],
              cmap=cmap, aspect="equal", interpolation="nearest", zorder=1)
    ax.contour(XX, YY, truth_alarm.astype(float), levels=[0.5], colors="black",
               linewidths=1.6, linestyles="--", zorder=3)
    ax.contour(XX, YY, U.reshape(XX.shape), levels=[T], colors="black",
               linewidths=0.9, linestyles=":", zorder=3)
    ax.contour(XX, YY, L.reshape(XX.shape), levels=[T], colors="black",
               linewidths=0.9, linestyles=":", zorder=3)
    ax.scatter(M[:, 0], M[:, 1], s=40, marker="s", color="tab:blue", zorder=5,
               label="参考向量 M")
    ax.scatter(M[CENTERS][:, 0], M[CENTERS][:, 1], s=130, marker="*",
               color="tab:red", zorder=6, label="观测中心")

    frac = float((zone == 2).mean())
    handles = [
        Patch(facecolor="#cfe8ff", label="本地判 normal（U ≤ t）"),
        Patch(facecolor="#ffd6d6", label="本地判 alarm（L > t）"),
        Patch(facecolor="#ffe9b0", label=f"升级查询（区间跨阈值，占该视野 {frac:.0%}）"),
        plt.Line2D([], [], color="black", ls="--", lw=1.6, label="真实决策边界 s_M(q) = t"),
        plt.Line2D([], [], color="black", ls=":", lw=0.9, label="U = t 与 L = t 的等值线"),
    ]
    ax.legend(handles=handles, fontsize=8.4, loc="upper left", framealpha=0.95)
    ax.set_xlabel("x"); ax.set_ylabel("y")
    ax.set_title("区间筛查的决策图：黄色 = 必须升级查询的区域\n"
                 "（六向量/两中心例子，t = 1.5；黄色越宽，省下的整库查询越少）",
                 fontsize=10.5)
    save(fig, out_dir, "figure_3_decision_map", manifest,
         sources=["project/src/w1_bounds_example.py（同一组常数）"],
         note="网格为确定性采样；黄色占比是该视野内的升级率，不是数据集上的升级率")


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "reports" / "figures"))
    args = ap.parse_args()
    out_dir = Path(args.out)

    print(f"仓库根目录 : {ROOT}")
    print(f"数据源     : {LOGS}")
    print(f"输出目录   : {out_dir}\n")

    manifest: list = []
    print("figure_1_vram_limits …");      figure_1(out_dir, manifest)
    print("figure_2_bounds_geometry …");  figure_2(out_dir, manifest)
    print("figure_3_decision_map …");     figure_3(out_dir, manifest)

    mf = out_dir / "manifest.json"
    mf.write_text(json.dumps({
        "generated_by": "scripts/make_figures.py",
        "repo_root": str(ROOT),
        "figures": manifest,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n清单：{mf}（{len(manifest)} 个文件）")
    print("注意：论文级图 1–3（分歧 vs 库字节、升级率 vs 位移、成本前沿）需要数据集，"
          "目前只能出上面这三张不依赖数据的图。")


if __name__ == "__main__":
    main()
