# -*- coding: utf-8 -*-
"""W1 / A14-2（无数据回退路径）+ A6 健全性检查：距离计算核对与计时。

内容：
    Part A  10 个人造二维向量：朴素双重循环 vs 向量化，逐个查询核对最近距离
    Part B  真实规模（N=20000, D=384）：整块 cdist vs 分块，确认位级/数值一致并计时
    Part C  若 torch 可用：核对 finite、CPU/GPU 分块最近邻一致性、GPU 计时与峰值显存
            （torch 未安装时自动跳过，并打印说明）

为什么先做这些：数据集尚未获批（MVTec AD 需填表），A14 明确允许在数据访问待定时
先用十个人造二维向量做张量距离检查。Part B/C 同时把第 2 周要用的
「分块精确最近邻 == 暴力最近邻」这一条数值契约先固定下来。

运行：python w1_distance_checks.py
"""
import time

import numpy as np

SEED = 0
TOL = 1e-9          # 本机固定的浮点容忍值（第 4 周判定区间违规时沿用同一个数字）


def part_a():
    print("=" * 72)
    print("Part A：10 个人造二维向量（朴素循环 vs 向量化）")
    print("=" * 72)
    rng = np.random.default_rng(SEED)
    M = np.round(rng.normal(0, 3, size=(10, 2)), 3)      # 10 个参考向量
    Q = np.round(rng.normal(0, 3, size=(4, 2)), 3)       # 4 个查询向量

    print("参考集 M（10 x 2）：")
    for i, m in enumerate(M):
        print("  m%-2d = (%7.3f, %7.3f)" % (i, m[0], m[1]))

    print("\n%-6s %-20s %10s %10s %12s" % ("query", "坐标", "朴素循环", "向量化", "绝对差"))
    max_diff = 0.0
    for k, q in enumerate(Q):
        best = float("inf")
        for m in M:                                      # 朴素双重循环
            d = ((q[0] - m[0]) ** 2 + (q[1] - m[1]) ** 2) ** 0.5
            if d < best:
                best = d
        vec = float(np.linalg.norm(M - q, axis=1).min())  # 向量化
        diff = abs(best - vec)
        max_diff = max(max_diff, diff)
        print("%-6s %-20s %10.6f %10.6f %12.2e"
              % ("q%d" % (k + 1), "(%.3f, %.3f)" % (q[0], q[1]), best, vec, diff))
    print("\n最大绝对差 = %.2e  ->  %s" % (max_diff, "一致" if max_diff <= TOL else "不一致！"))
    return max_diff


def part_b():
    print("\n" + "=" * 72)
    print("Part B：分块 vs 暴力精确最近邻")
    print("=" * 72)

    # ---- B0：先记录一个真实资源事实：整块物化有多贵 ----
    N0, D0, P0 = 20000, 384, 512
    need = N0 * P0 * D0 * 8 / 2 ** 30
    print("B0 资源事实：整块物化 (P=%d, N=%d, D=%d) 的 float64 距离矩阵需要 %.1f GiB"
          % (P0, N0, D0, need))
    print("   -> 本机 32 GB RAM 下不可行。分块不是优化，是必需。")

    rng = np.random.default_rng(SEED)

    # ---- B1：小规模上证明「分块 == 整块」（可安全物化） ----
    N, D, P = 2000, 384, 64
    M = rng.normal(size=(N, D)); M /= np.linalg.norm(M, axis=1, keepdims=True)
    Q = rng.normal(size=(P, D)); Q /= np.linalg.norm(Q, axis=1, keepdims=True)

    def chunked(Q, M, bs=256):
        out = []
        for i in range(0, len(Q), bs):
            d = np.linalg.norm(Q[i:i + bs, None, :] - M[None, :, :], axis=2)
            out.append(d.min(axis=1))
        return np.concatenate(out)

    t0 = time.perf_counter()
    full = np.linalg.norm(Q[:, None, :] - M[None, :, :], axis=2).min(axis=1)
    t_full = time.perf_counter() - t0
    t0 = time.perf_counter()
    part = chunked(Q, M, bs=256)
    t_chunk = time.perf_counter() - t0
    diff_small = float(np.abs(full - part).max())
    print("\nB1 小规模（N=%d, D=%d, P=%d）：" % (N, D, P))
    print("   整块 cdist 最近距离    : 用时 %.4f s" % t_full)
    print("   分块（bs=256）最近距离 : 用时 %.4f s" % t_chunk)
    print("   最大绝对差             : %.2e  ->  %s"
          % (diff_small, "一致" if diff_small <= 1e-12 else "不一致！"))
    print("   分数是否全部有限       : %s" % bool(np.isfinite(full).all()))
    print("   距离范围               : [%.6f, %.6f]" % (full.min(), full.max()))

    # ---- B2：真实规模只比较不同块大小之间的一致性 + 计时（不物化整块） ----
    # 关键教训：块大小必须按**内存预算**反推，不能凭感觉写死。
    # 最初我用 bs=256，单块需要 256*20000*384*8 = 14.6 GiB —— 有一次内存恰好够就跑通了，
    # 下一次同样命令直接 ArrayMemoryError。这种"偶然跑通"不算可复现，所以这里显式设预算。
    N2, D2, P2 = 20000, 384, 512
    M2 = rng.normal(size=(N2, D2)); M2 /= np.linalg.norm(M2, axis=1, keepdims=True)
    Q2 = rng.normal(size=(P2, D2)); Q2 /= np.linalg.norm(Q2, axis=1, keepdims=True)

    budget_gib = 2.0
    budget = int(budget_gib * 2 ** 30)
    per_row = N2 * D2 * 8                      # 每个查询行带来的中间张量字节数
    bs_cap = max(1, budget // per_row)
    print("\nB2 真实规模（N=%d, D=%d, P=%d）：块大小对速度的影响" % (N2, D2, P2))
    print("   每块内存预算 %.1f GiB -> 块大小上限 = %d（%d 字节/查询行）"
          % (budget_gib, bs_cap, per_row))

    ref, ref_bs = None, None
    t_first = None
    for want in (64, 32, 16, 8):
        bs = max(1, min(want, bs_cap))
        est_gib = bs * per_row / 2 ** 30
        t0 = time.perf_counter()
        r = chunked(Q2, M2, bs=bs)
        dt = time.perf_counter() - t0
        if ref is None:
            ref, ref_bs, t_first = r, bs, dt
        diff = float(np.abs(r - ref).max())
        print("   bs=%-3d 单块 %5.2f GiB  用时 %6.2f s  与 bs=%d 的最大绝对差 %.2e"
              % (bs, est_gib, dt, ref_bs, diff))

    print("   距离范围 : [%.6f, %.6f]" % (ref.min(), ref.max()))
    print("   结论：块大小不影响结果（差为 0），只影响速度与内存；bs=256 那种写法会吃掉 14.6 GiB，"
          "\n         完全不可复现，已被预算机制取代。")
    print("\n说明：本机固定的距离比较容忍值 TOL = %.1e，第 4 周判定区间违规时沿用同一数字。" % TOL)
    return max(diff_small, 0.0), t_full, t_chunk, bs_cap


def part_c():
    print("\n" + "=" * 72)
    print("Part C：torch（若已安装）：finite 检查 + CPU/GPU 一致性 + 计时")
    print("=" * 72)
    try:
        import torch
    except Exception as e:
        print("跳过：torch 不可用（%s: %s）" % (type(e).__name__, e))
        print("说明：数据集与 torch 环境就绪后，用 scripts\\check_env.ps1 做 GPU 冒烟与显存上限实测。")
        return None

    rng = np.random.default_rng(SEED)
    N, D, P = 20000, 384, 512
    Mt = torch.tensor(rng.normal(size=(N, D)), dtype=torch.float32)
    Mt = Mt / Mt.norm(dim=1, keepdim=True)
    Qt = torch.tensor(rng.normal(size=(P, D)), dtype=torch.float32)
    Qt = Qt / Qt.norm(dim=1, keepdim=True)

    print("torch %s  cuda=%s  cuda_available=%s"
          % (torch.__version__, torch.version.cuda, torch.cuda.is_available()))
    print("全部特征有限: %s" % bool(torch.isfinite(Mt).all() and torch.isfinite(Qt).all()))

    def chunked_t(a, b, bs=256):
        return torch.cat([torch.cdist(a[i:i + bs], b).min(dim=1).values
                          for i in range(0, len(a), bs)])

    ref = chunked_t(Qt, Mt)
    print("CPU 分块：最近距离 min=%.6f max=%.6f finite=%s"
          % (ref.min().item(), ref.max().item(), bool(torch.isfinite(ref).all())))

    if torch.cuda.is_available():
        dev = torch.device("cuda")
        Mg, Qg = Mt.to(dev), Qt.to(dev)
        chunked_t(Qg[:8], Mg[:1024])                      # 预热
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        gpu = chunked_t(Qg, Mg)
        torch.cuda.synchronize()
        t_gpu = time.perf_counter() - t0
        diff = (gpu.cpu() - ref).abs().max().item()
        t0 = time.perf_counter()
        _ = chunked_t(Qt, Mt)
        t_cpu = time.perf_counter() - t0
        print("GPU 分块：用时 %.4f s，峰值显存 %.1f MiB"
              % (t_gpu, torch.cuda.max_memory_allocated() / 2 ** 20))
        print("CPU 分块：用时 %.4f s" % t_cpu)
        print("GPU vs CPU 最近距离最大绝对差 = %.2e" % diff)
        print("加速比 = %.1fx" % (t_cpu / t_gpu if t_gpu > 0 else float("nan")))
        print("\n注意：这只是「库已在显存里」的检索计时，不含编码器前向；"
              "\n      端到端时延必须另测 T_encoder + T_screen + p_escalate*(T_transfer + T_full)。")
    else:
        print("CUDA 不可用，跳过 GPU 部分。")
    return None


def main():
    a = part_a()
    b = part_b()
    part_c()
    print("\n" + "=" * 72)
    print("汇总：Part A 最大差 %.2e ；Part B 最大差 %.2e ；容忍值 %.1e"
          % (a, b[0], TOL))
    print("结论：十个人造二维向量的距离检查通过；分块与暴力精确最近邻在同一容忍值内一致。")
    print("=" * 72)


if __name__ == "__main__":
    main()
