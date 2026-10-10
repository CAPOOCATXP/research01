# -*- coding: utf-8 -*-
"""W1 / A14-3：六向量参考集 + 两个观测中心的手算例子的可执行版本。

场景（全部为二维欧氏距离，便于手算核对）：
    M = 6 个参考向量（含一对重复向量）
    centers = 2 个观测中心（索引 0 与 4）
    t = 1.5，报警判定： alarm  <=>  s_M(q) > t（严格大于）

公式（导师 handout A8）：
    s_M(q) = min_{m in M} d(q, m)                    完整库分数
    L(q)   = min_j max{0, d(q, c_j) - r_j}           下界
    U(q)   = min_j d(q, c_j)                         上界
    r_j   >= max_{m in C_j} d(m, c_j)                cell C_j 的保守半径
    cell C_j = 到中心 c_j 比到其它中心更近的参考点集合

筛查规则：
    U <= t        -> normal
    L >  t        -> alarm
    否则           -> escalate（升级到完整库），若完整库不可用则 unresolved

本脚本覆盖的 5 种边界情形：
    (a) U <= t            本地判 normal
    (b) L >  t            本地判 alarm
    (c) L <= t < U        必须升级（本例给了两种：真值 normal 与真值 alarm）
    (d) s_M(q) == t       阈值相等 -> 因为 alarm 要求 s > t，所以真值是 normal
    (e) 重复向量           m4 == m5 == (10, 0)

运行：python w1_bounds_example.py
"""
import numpy as np

M = np.array([
    [0.0, 0.0],    # m0  <- 观测中心 c0
    [1.0, 0.0],    # m1
    [0.0, 1.0],    # m2
    [2.0, 0.0],    # m3
    [10.0, 0.0],   # m4  <- 观测中心 c1
    [10.0, 0.0],   # m5  ！！与 m4 完全相同（重复向量）
])
CENTERS = [0, 4]
T = 1.5

QUERIES = np.array([
    [0.5, 0.0],    # q1  情形 (a)
    [0.0, 10.0],   # q2  情形 (b)
    [3.0, 0.0],    # q3  情形 (c)，真值 normal
    [0.0, 3.0],    # q4  情形 (c)，真值 alarm
    [2.0, 1.5],    # q5  情形 (d)：s_M 恰好等于 t
])
LABELS = ["q1 (a) U<=t", "q2 (b) L>t", "q3 (c) 升级->normal",
          "q4 (c) 升级->alarm", "q5 (d) s==t (并列)"]

EPS = 1e-12   # 保守浮点保护量（把区间放大，不缩小）


def build_cells(M, centers_idx):
    C = M[centers_idx]
    d = np.linalg.norm(M[:, None, :] - C[None, :, :], axis=2)
    assign = np.argmin(d, axis=1)
    counts = [int((assign == j).sum()) for j in range(len(C))]
    radii = np.array([d[assign == j, j].max() for j in range(len(C))])
    guard = np.maximum(radii, 1.0) * EPS
    return C, assign, counts, radii, radii + guard, guard


def main():
    C, assign, counts, radii, radii_g, guard = build_cells(M, CENTERS)

    print("=" * 78)
    print("参考集 M（%d 个向量）:" % len(M))
    for i, m in enumerate(M):
        print("  m%d = (%.1f, %.1f)   -> cell %d" % (i, m[0], m[1], assign[i]))
    print("观测中心: c0 = m0 = (%.1f, %.1f),  c1 = m4 = (%.1f, %.1f)"
          % (C[0][0], C[0][1], C[1][0], C[1][1]))
    print("cell 大小 = %s   （cell1 含一对重复向量）" % counts)
    print("保守半径 r_j = %s" % list(np.round(radii, 6)))
    print("阈值 t = %.1f   （alarm <=> s_M(q) > t，严格大于）" % T)
    print("=" * 78)

    hdr = ("%-20s %9s %9s %9s %11s %11s %9s %s"
           % ("query", "s_M(q)", "L(q)", "U(q)", "完整库真值", "screening", "L<=s<=U", "情形"))
    print(hdr)
    print("-" * len(hdr))

    n_resolved = 0
    n_escalate = 0
    n_violation = 0
    n_mismatch = 0
    rows = []
    for i, q in enumerate(QUERIES):
        dM = np.linalg.norm(M - q, axis=1)
        s = float(dM.min())
        dc = np.linalg.norm(C - q, axis=1)
        L = float(np.maximum(0.0, dc - radii_g).min() - guard.min())
        U = float(dc.min() + guard.min())

        truth = "alarm" if s > T else "normal"
        if U <= T:
            scr = "normal"
        elif L > T:
            scr = "alarm"
        else:
            scr = "escalate"
        ok = (L - 1e-9) <= s <= (U + 1e-9)
        if not ok:
            n_violation += 1
        if scr == "escalate":
            n_escalate += 1
            final = truth          # 升级后由完整库决定
        else:
            n_resolved += 1
            final = scr
            if scr != truth:
                n_mismatch += 1
        rows.append((q, s, L, U, truth, scr, ok, final))
        print("%-20s %9.4f %9.4f %9.4f %11s %11s %9s %s"
              % (LABELS[i], s, L, U, truth, scr, str(ok), ""))

    print("-" * len(hdr))
    print("\n逐条核对（保留 4 位小数）：")
    for i, (q, s, L, U, truth, scr, ok, final) in enumerate(rows):
        print("  %-22s q = (%4.1f, %4.1f)   s=%7.4f  L=%7.4f  U=%7.4f  真值=%-6s screening=%-8s 最终=%s"
              % (LABELS[i], q[0], q[1], s, L, U, truth, scr, final))

    print("\n汇总：")
    print("  区间违规数（L <= s <= U 不成立）: %d   （必须为 0）" % n_violation)
    print("  本地解决 / 升级查询          : %d / %d  （本地解决比例 %.0f%%）"
          % (n_resolved, n_escalate, 100.0 * n_resolved / len(QUERIES)))
    print("  本地已解决项与真值不一致      : %d   （必须为 0）" % n_mismatch)

    print("\n覆盖检查：")
    checks = {
        "(a) U <= t": any(r[3] <= T for r in rows),
        "(b) L >  t": any(r[2] > T for r in rows),
        "(c) 需要升级": any(r[5] == "escalate" for r in rows),
        "(d) s_M == t": any(abs(r[1] - T) < 1e-12 for r in rows),
        "(e) 存在重复向量": len(np.unique(M, axis=0)) < len(M),
    }
    for k, v in checks.items():
        print("  [%s] %s" % ("x" if v else " ", k))

    print("\n结论：本地解决的决策与完整库真值完全一致；区间从不违反 L <= s <= U；"
          "\n      两个升级情形中有一个真值是 alarm —— 说明「区间跨阈值就升级」"
          "\n      不能简化为「靠近中心就正常」。")


if __name__ == "__main__":
    main()
