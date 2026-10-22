# -*- coding: utf-8 -*-
"""W2 / Phase 3 预演：**机制级模拟实验**——压缩记忆库是否改变固定阈值下的报警决策？

背景与边界（必须先读）
----------------------
MVTec AD 尚未获批。按用户 2026-10-10 的授权（"无法获取的可以获取等价或者模拟"），
本脚本用**受控的生成式模拟**替代真实图像，检验的是**机制**，不是数据集结论：

    * 这不是 MVTec 结果，不能写进论文的 Table 2，只能作为"方法可行性 + 实验设计"的证据；
    * 三个"类别"是**三种难度区间**的代理（紧凑/中等/困难），不代表 bottle/tile/screw 的任何数值；
    * 固定种子，结果可逐位复现。

为什么用"内在低维"而不是在 384 维里直接撒点（第一版的教训）
------------------------------------------------------------
第一版把正常 patch 直接生成在 D=384 维高斯里，结果**召回只有 5–11%**：在 384 维中，
2 万个参考点仍然非常稀疏，正常 patch 到最近邻的距离（约 sqrt(2·384)·σ）远大于缺陷位移，
于是"缺陷根本不是最大距离的那块"。这与真实深度特征的行为相反——真实 patch 特征**高度集中**
在一个低维流形上，因此相同正常样本之间的最近邻距离很小。

所以本版把数据生成在**内在维度 d_eff=24 的子空间**里（真实深度特征常见 10–40 维有效维数），
并**在该子空间内做全部计算**——因为距离在这个子空间内是精确的（矩阵乘法不改变距离），
所以这不是近似，而是等价的加速。名义特征维度仍记为 D=384。

阈值口径（严格按 handout A7）
-----------------------------
只用**校准集正常图**的图像分数 95 分位（名义 5% 误报），全程**不读任何缺陷标签**；
缺陷标签只用于事后计算"召回率"。

用法
----
    python scripts/sim_gap_pilot.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "logs" / "w2_sim_gap_pilot.json"
OUT_PNG = ROOT / "reports" / "figures" / "figure_4_sim_gap_pilot.png"

D_NOMINAL = 384          # 名义特征维度（记录用；计算在内在子空间内完成）
D_EFF = 24               # 内在维度
K_MODES = 8              # 正常外观模式数
PATCHES_PER_IMAGE = 64   # 8x8
RATIOS = [0.01, 0.05, 0.10, 0.25]
N_IMAGES = dict(calib=200, test_normal=200, test_anomalous=200)

# 缺陷位移按"正常最近邻距离尺度 d0"的倍数给，自动校准，避免手调
CATEGORIES = [
    dict(name="compact_tight", sigma=0.55, shift=(2.5, 6.0), n_defect=(1, 2)),
    dict(name="medium",        sigma=0.85, shift=(1.6, 4.0), n_defect=(1, 2)),
    dict(name="broad_hard",    sigma=1.20, shift=(1.05, 2.2), n_defect=(1, 1)),
]


# --------------------------------------------------------------------------- #
def make_modes(rng, sigma):
    scale = sigma * 3.0
    return rng.normal(0.0, scale, size=(K_MODES, D_EFF)).astype(np.float32)


def normal_patches(rng, modes, sigma, n):
    idx = rng.integers(0, len(modes), size=n)
    return (modes[idx] + rng.normal(0.0, sigma, size=(n, D_EFF))).astype(np.float32)


def images_from_patches(patches, n_images):
    return patches.reshape(n_images, PATCHES_PER_IMAGE, D_EFF)


def nearest_dist(Q, M, chunk=512):
    m2 = (M * M).sum(axis=1)
    out = np.empty(len(Q), dtype=np.float32)
    for i in range(0, len(Q), chunk):
        q = Q[i:i + chunk]
        d2 = (q * q).sum(axis=1, keepdims=True) + m2[None, :] - 2.0 * (q @ M.T)
        out[i:i + chunk] = np.sqrt(np.maximum(d2, 0.0).min(axis=1))
    return out


def image_scores(imgs, M):
    return np.array([nearest_dist(imgs[i], M).max() for i in range(len(imgs))], dtype=np.float32)


def greedy_coreset(rng, M, k):
    first = int(rng.integers(0, len(M)))
    chosen = [first]
    dmin = np.linalg.norm(M - M[first], axis=1)
    for _ in range(k - 1):
        nxt = int(np.argmax(dmin))
        chosen.append(nxt)
        dmin = np.minimum(dmin, np.linalg.norm(M - M[nxt], axis=1))
    return np.array(sorted(set(chosen)), dtype=np.int64)


def cell_radii(M, centers_idx, chunk=1024):
    C = M[centers_idx]
    c2 = (C * C).sum(axis=1)
    assign = np.empty(len(M), dtype=np.int32)
    dist = np.empty(len(M), dtype=np.float32)
    for i in range(0, len(M), chunk):
        m = M[i:i + chunk]
        d2 = (m * m).sum(axis=1, keepdims=True) + c2[None, :] - 2.0 * (m @ C.T)
        j = np.argmin(d2, axis=1)
        assign[i:i + chunk] = j
        dist[i:i + chunk] = np.sqrt(np.maximum(d2[np.arange(len(m)), j], 0.0))
    radii = np.zeros(len(C), dtype=np.float32)
    for j in range(len(C)):
        s = assign == j
        if s.any():
            radii[j] = dist[s].max()
    return C, radii


def interval_screen(imgs, C, radii, t):
    guard = 1e-6
    P = len(imgs)
    out = np.empty(P, dtype=object)
    Lx = np.empty(P, dtype=np.float32)
    Ux = np.empty(P, dtype=np.float32)
    for i in range(P):
        q = imgs[i]
        d = np.linalg.norm(q[:, None, :] - C[None, :, :], axis=2)
        L = np.maximum(0.0, d - radii[None, :]).min(axis=1) - guard
        U = d.min(axis=1) + guard
        Lx[i], Ux[i] = L.max(), U.max()
        out[i] = "normal" if Ux[i] <= t else ("alarm" if Lx[i] > t else "escalate")
    return out, Lx, Ux


def run_category(rng, cat, n_patches):
    sigma = cat["sigma"]
    modes = make_modes(rng, sigma)
    M = normal_patches(rng, modes, sigma, n_patches)

    # 用正常 patch 到全库的最近邻距离中位数作为尺度 d0，缺陷位移按 d0 的倍数给
    probe = normal_patches(rng, modes, sigma, 2000)
    d0 = float(np.median(nearest_dist(probe, M)))
    lo, hi = cat["shift"]
    shift_lo, shift_hi = lo * d0, hi * d0

    def defect(n):
        idx = rng.integers(0, len(modes), size=n)
        direction = rng.normal(size=(n, D_EFF))
        direction /= np.linalg.norm(direction, axis=1, keepdims=True)
        mag = rng.uniform(shift_lo, shift_hi, size=(n, 1))
        return (modes[idx] + direction * mag).astype(np.float32)

    calib = images_from_patches(normal_patches(rng, modes, sigma, N_IMAGES["calib"] * PATCHES_PER_IMAGE),
                                N_IMAGES["calib"])
    tn = images_from_patches(normal_patches(rng, modes, sigma, N_IMAGES["test_normal"] * PATCHES_PER_IMAGE),
                             N_IMAGES["test_normal"])
    ta = np.empty((N_IMAGES["test_anomalous"], PATCHES_PER_IMAGE, D_EFF), dtype=np.float32)
    for i in range(len(ta)):
        img = modes[rng.integers(0, len(modes))] + rng.normal(0.0, sigma, size=(PATCHES_PER_IMAGE, D_EFF))
        n_bad = int(rng.integers(cat["n_defect"][0], cat["n_defect"][1] + 1))
        pos = rng.choice(PATCHES_PER_IMAGE, size=n_bad, replace=False)
        img[pos] = defect(n_bad)
        ta[i] = img

    s_calib = image_scores(calib, M)
    t = float(np.percentile(s_calib, 95))
    s_tn, s_ta = image_scores(tn, M), image_scores(ta, M)
    base_tn, base_ta = s_tn > t, s_ta > t

    res = dict(category=cat["name"], sigma=sigma, d0=d0, N=int(len(M)), t=t,
               shift_abs=[shift_lo, shift_hi],
               fullbank=dict(far_normal=float(base_tn.mean()),
                             recall_anomalous=float(base_ta.mean()),
                             mean_score_normal=float(s_tn.mean()),
                             mean_score_anomalous=float(s_ta.mean()),
                             t_over_d0=float(t / d0)),
               compression={})

    n_tot = len(tn) + len(ta)
    for ratio in RATIOS:
        k = max(2, int(round(ratio * len(M))))
        idx = greedy_coreset(rng, M, k)
        Mb = M[idx]
        s_tn_c, s_ta_c = image_scores(tn, Mb), image_scores(ta, Mb)
        d_tn, d_ta = s_tn_c > t, s_ta_c > t
        extra = float(((d_tn & ~base_tn).sum() + (d_ta & ~base_ta).sum()) / n_tot)
        missed = float(((~d_tn & base_tn).sum() + (~d_ta & base_ta).sum()) / n_tot)

        t2 = float(np.percentile(image_scores(calib, Mb), 95))
        r_tn, r_ta = s_tn_c > t2, s_ta_c > t2
        re_extra = float(((r_tn & ~base_tn).sum() + (r_ta & ~base_ta).sum()) / n_tot)
        re_missed = float(((~r_tn & base_tn).sum() + (~r_ta & base_ta).sum()) / n_tot)

        entry = dict(k=k, ratio=ratio,
                     far_normal_fixed_t=float(d_tn.mean()),
                     recall_fixed_t=float(d_ta.mean()),
                     disagree=extra + missed, extra_alarms=extra, missed_alarms=missed,
                     recalibrated=dict(t_prime=t2, far_normal=float(r_tn.mean()),
                                       recall=float(r_ta.mean()),
                                       disagree=re_extra + re_missed,
                                       extra_alarms=re_extra, missed_alarms=re_missed))

        if abs(ratio - 0.10) < 1e-9:
            C, radii = cell_radii(M, idx)
            scr_n, Ln, Un = interval_screen(tn, C, radii, t)
            scr_a, La, Ua = interval_screen(ta, C, radii, t)
            allscr = np.concatenate([scr_n, scr_a])
            truth = np.concatenate([base_tn, base_ta])
            esc = float((allscr == "escalate").mean())
            mism = 0
            for s_, tr in zip(allscr, truth):
                if s_ == "normal" and tr:
                    mism += 1
                elif s_ == "alarm" and not tr:
                    mism += 1
            entry["screening"] = dict(
                escalate_rate=esc, resolved=1.0 - esc, resolved_mismatch=int(mism),
                radius_mean=float(radii.mean()), radius_p95=float(np.percentile(radii, 95)),
                width_mean=float((Un - Ln).mean()), cell_count=int(len(C)),
                note="逐 cell 半径在内在子空间内计算；未计入元数据与编码器内存",
            )

        res["compression"][str(k)] = entry
        print(f"  {ratio:5.0%} (k={k:5d}) 分歧={extra + missed:6.2%} (多报 {extra:5.2%} / 漏报 {missed:5.2%})"
              f"  重校准后={re_extra + re_missed:6.2%}  FAR={d_tn.mean():5.1%} 召回={d_ta.mean():5.1%}")

    print(f"  全库: t={t:.3f} (t/d0={t / d0:.2f})  FAR={base_tn.mean():.1%}  召回={base_ta.mean():.1%}")
    return res


def plot(results, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.alpha"] = 0.25

    fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.9))
    colors = {"compact_tight": "#2ca02c", "medium": "#1f77b4", "broad_hard": "#d62728"}
    for r in results:
        c = colors.get(r["category"], "gray")
        xs = [v["ratio"] * 100 for v in r["compression"].values()]
        axes[0].plot(xs, [v["disagree"] * 100 for v in r["compression"].values()], "o-", color=c,
                     label=f"{r['category']}：沿用原阈值")
        axes[0].plot(xs, [v["recalibrated"]["disagree"] * 100 for v in r["compression"].values()],
                     "s--", color=c, alpha=0.6, label=f"{r['category']}：压缩库重校准")
        sc = next((v["screening"] for v in r["compression"].values() if "screening" in v), None)
        if sc:
            axes[1].bar(r["category"], sc["escalate_rate"] * 100, color=c)
            axes[1].text(r["category"], sc["escalate_rate"] * 100 + 1.2,
                         f"{sc['escalate_rate'] * 100:.1f}%", ha="center", fontsize=9)
    axes[0].axhline(2.0, color="black", ls=":", lw=1.2)
    axes[0].text(1.1, 2.3, "A7：2 个百分点门槛", fontsize=8.5)
    axes[0].set_xlabel("压缩后库大小（占全库 %）")
    axes[0].set_ylabel("与全库的二元决策分歧（%）")
    axes[0].set_title("压缩是否改变报警（固定阈值 vs 重校准）")
    axes[0].legend(fontsize=7.0, loc="upper right")
    axes[1].set_ylabel("必须升级查询的图像比例（%）")
    axes[1].set_title("区间筛查的升级率（10% 库，逐 cell 半径）")
    axes[1].set_ylim(0, 105)
    fig.suptitle("机制级模拟实验（**不是 MVTec 结果**）：压缩 → 决策分歧 → 升级代价", fontsize=11.5)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(path.with_suffix("." + ext),
                    metadata={"CreationDate": None} if ext == "pdf" else None)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    print(f"设定：D_nominal={D_NOMINAL}, 内在维 d_eff={D_EFF}, N={args.n}, "
          f"每图 {PATCHES_PER_IMAGE} patch, seed={args.seed}")
    print("声明：机制模拟，不是 MVTec AD 结果；类别为难度代理。\n")

    results = [run_category(rng, cat, args.n) for cat in CATEGORIES]
    payload = dict(kind="mechanism_simulation",
                   disclaimer="MVTec AD 未获批时的模拟实验；不能作为论文 Table 2；仅验证方法与实验设计",
                   seed=args.seed, D_nominal=D_NOMINAL, D_eff=D_EFF, N=args.n,
                   patches_per_image=PATCHES_PER_IMAGE, ratios=RATIOS, nominal_far=0.05,
                   categories=results)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    plot(results, OUT_PNG)
    print(f"\n结果 -> {OUT_JSON}\n图 -> {OUT_PNG.with_suffix('.png')} / .pdf")


if __name__ == "__main__":
    main()
