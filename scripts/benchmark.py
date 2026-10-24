# -*- coding: utf-8 -*-
"""Phase 6/8：精确树 vs 区间筛查 vs 全库暴力——字节、构建时间、查询时延、盈亏平衡。

回答三个问题
------------
1. 屏幕端真的要省多少内存？（序列化字节，含元数据，不含编码器）
2. 一次筛查 vs 一次整库查询，各要多少毫秒？（逐图，p50/p95）
3. 在什么升级比例下，筛查 + 升级 仍然比"每次都查整库"更快？（盈亏平衡）

口径
----
* 查询时延只算"检索"，不含编码器前向（编码器时延单列，来自特征缓存的实测吞吐）。
* BallTree 用 sklearn，是**精确**最近邻，用来核对我们的暴力实现，并作为树基线。
* 传输时延按受控假设给出（0/20/50/100 ms），因为本项目没有真实边缘链路；
  这属于**仿真**，报告中必须标注。

用法
----
    python scripts/benchmark.py --category bottle --k 32 128 1254
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from sklearn.neighbors import BallTree

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "features"
OUT = ROOT / "logs"


def load_cache(cat):
    files = sorted(CACHE.glob(f"{cat}_*.npz"))
    if not files:
        raise SystemExit(f"没有 {cat} 的缓存，先跑 scripts/featurize.py")
    z = np.load(files[0], allow_pickle=True)
    return z["feats"], z["split"], z["roles"], json.loads(str(z["meta"]))


def pct(a, q):
    return float(np.percentile(a, q))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", default="bottle")
    ap.add_argument("--k", nargs="+", type=int, default=[32, 128, 1254])
    ap.add_argument("--shot", type=int, default=16)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=str(OUT / "w6_benchmark.json"))
    args = ap.parse_args()

    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from screening import ScreenIndex, batch_image_scores, bank_sha256

    feats, split, roles, meta = load_cache(args.category)
    ref = np.where(roles == "reference_fit")[0]
    test_rows = np.where((split == "test_good") | (split == "test_defect"))[0]
    rng = np.random.default_rng(args.seed)
    take = np.sort(rng.choice(ref, size=min(args.shot, len(ref)), replace=False))
    bank = feats[take].reshape(-1, feats.shape[2])
    print(f"{args.category}: bank={len(bank):,} patches, test={len(test_rows)} 图, "
          f"D={feats.shape[2]}, P={feats.shape[1]}")

    # 编码器时延（来自缓存实测吞吐）
    enc_ms = 1000.0 * meta["seconds"] / meta["n_images"]
    print(f"编码器：{meta['seconds']}s / {meta['n_images']} 图 = {enc_ms:.1f} ms/图"
          f"（含读盘与解码，是上界）")

    # ---- 全库暴力（基准）----
    t0 = time.perf_counter()
    ref_scores = batch_image_scores(feats, test_rows, bank)
    brute_total = time.perf_counter() - t0
    brute_ms = 1000 * brute_total / len(test_rows)
    print(f"全库暴力：{brute_total*1000:.0f} ms 总计 = {brute_ms:.2f} ms/图")

    # ---- BallTree（精确）----
    t0 = time.perf_counter()
    tree = BallTree(bank, leaf_size=40, metric="euclidean")
    tree_build = time.perf_counter() - t0
    q_patches = feats[test_rows].reshape(-1, feats.shape[2])
    # 1536 维下树会退化成近似线性扫描，全量查询可能极慢：抽样测量再按比例外推。
    n_sample = min(4000, len(q_patches))
    rng2 = np.random.default_rng(0)
    samp = np.sort(rng2.choice(len(q_patches), size=n_sample, replace=False))
    q_s = q_patches[samp]
    t0 = time.perf_counter()
    d_tree, _ = tree.query(q_s, k=1)
    tree_q_s = time.perf_counter() - t0
    tree_ms = 1000 * tree_q_s / (n_sample / feats.shape[1])      # 折算成"每图"
    # 与暴力核对（同样只用抽样点，用矩阵乘避免物化 N×M×D）
    b2_ = (bank.astype(np.float32) ** 2).sum(axis=1)
    dmin_parts = []
    for i in range(0, len(q_s), 2048):
        qq = q_s[i:i + 2048]
        d2 = (qq ** 2).sum(axis=1, keepdims=True) + b2_[None, :] - 2.0 * qq @ bank.T
        dmin_parts.append(np.sqrt(np.maximum(d2.min(axis=1), 0.0)))
    d_brute = np.concatenate(dmin_parts)
    max_diff = float(np.abs(d_tree.ravel() - d_brute).max())
    print(f"BallTree：构建 {tree_build*1000:.0f} ms，抽样 {n_sample} patch "
          f"查询 {tree_q_s*1000:.0f} ms → 折合 {tree_ms:.2f} ms/图，与暴力最大差 {max_diff:.2e}")
    # 树的内存：每个节点存 data + radius + children 索引，这里按 sklearn 实际数据结构估
    tree_bytes = int(tree.data.nbytes + tree.idx_array.nbytes +
                     getattr(tree, "node_bounds", np.zeros(0)).nbytes)

    rows = []
    for k in args.k:
        t0 = time.perf_counter()
        idx = ScreenIndex(bank, k=k, levels=1, radius_mode="cell", seed=args.seed)
        build = time.perf_counter() - t0
        t0 = time.perf_counter()
        for r in test_rows:
            idx.image_bounds(feats[r])
        screen_ms = 1000 * (time.perf_counter() - t0) / len(test_rows)
        b = idx.bytes()
        rows.append(dict(k=k, leaves=idx.n_leaves, build_s=round(build, 2),
                         screen_ms=round(screen_ms, 3), bytes=b["total"],
                         ratio_bytes_screen=round(b["total"] / bank.nbytes, 3)))
        print(f"筛查 k={k:<5} 构建 {build*1000:6.0f} ms  查询 {screen_ms:6.2f} ms/图  "
              f"字节 {b['total']/1024:8.1f} KB  = 全库 {b['total']/bank.nbytes*100:5.2f}%")

    # ---- 盈亏平衡 ----
    # 每次筛查 + 以概率 p 升级：T = T_screen + p*(T_transfer + T_full)
    # 与"每次都查整库" T_full 比较：p* = (T_full - T_screen) / (T_transfer + T_full)
    be = []
    for r in rows:
        for transfer_ms in (0, 20, 50, 100):
            num = brute_ms - r["screen_ms"]
            den = transfer_ms + brute_ms
            p_star = num / den if den > 0 else float("nan")
            be.append(dict(k=r["k"], transfer_ms=transfer_ms,
                           p_star=max(0.0, min(1.0, p_star)),
                           profitable=(p_star > 0)))
    print("\n盈亏平衡 p*（升级比例低于此值时，筛查方案更快）")
    print(f"{'k':>6}{'transfer=0':>12}{'20ms':>10}{'50ms':>10}{'100ms':>10}")
    for k in args.k:
        cells = [format(next(x['p_star'] for x in be if x['k'] == k and x['transfer_ms'] == t), ".3f")
                 for t in (0, 20, 50, 100)]
        print(f"{k:>6}{cells[0]:>12}{cells[1]:>10}{cells[2]:>10}{cells[3]:>10}")

    payload = dict(category=args.category, shot=args.shot,
                   bank_patches=int(len(bank)), dim=int(feats.shape[2]),
                   encoder_ms_per_image=round(enc_ms, 2),
                   brute_ms_per_image=round(brute_ms, 3),
                   balltree=dict(build_ms=round(tree_build * 1000, 1),
                                 query_ms_per_image=round(tree_ms, 3),
                                 bytes=tree_bytes, max_abs_diff_vs_brute=max_diff),
                   screen=rows, breakeven=be,
                   note="传输时延为受控假设（仿真），本项目无真实边缘链路测量")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果 -> {args.out}")


if __name__ == "__main__":
    main()
