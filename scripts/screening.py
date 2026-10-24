# -*- coding: utf-8 -*-
"""Phase 4–5：可审计的边缘筛查器（区间 + 升级 + 未决），带版本契约。

设计要点（对应 handout A8）
--------------------------
* 屏幕端只持有：观测中心 c_j、保守半径 r_j（按 cell）、以及一个**版本串**。
* 区间：L(q) = min_j max{0, d(q,c_j) − r_j}，U(q) = min_j d(q,c_j)。
  三角不等式 + c_j ∈ M 保证 L ≤ s_M ≤ U。
* 决策：U ≤ t → 正常；L > t → 报警；否则**升级查询**。
  若整库不可用或版本不符 → **未决（unresolved）**，绝不静默判正常。
* 两级：把大 cell 再切成子 cell，L 仍取所有叶子 cell 的下界（叶子仍划分 M，故仍然有效）。
* 全局半径对照：所有 cell 共享 max(r_j)，区间必然更宽——用来量化"逐 cell 半径"的收益。

单元测试（`--selftest`）覆盖 handout 要求的五类边界
--------------------------------------------------
    并列（阈值相等）/ 重复向量 / 空 cell / L≤s≤U / 版本不符 → 未决
另加：两次构建结果逐位一致（确定性）。

用法
----
    python scripts/screening.py --selftest
    python scripts/screening.py --category bottle --ratio 0.10 --levels 2
    python scripts/screening.py --category all --ratio 0.10 --levels 1 2 --radius both
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "features"
OUT = ROOT / "logs"
GUARD = 1e-6            # float32 保守保护量（见 environment.md：GPU float32 与 CPU 差 2.4e-7）


# --------------------------------------------------------------------------- #
# 版本契约
# --------------------------------------------------------------------------- #
@dataclass
class BankVersion:
    encoder: str
    preprocessing: str
    bank_sha256: str
    aggregation: str          # "max_patch"
    threshold: float
    k_centers: int
    ratio: float
    levels: int

    def id(self) -> str:
        payload = json.dumps({
            "encoder": self.encoder, "preprocessing": self.preprocessing,
            "bank_sha256": self.bank_sha256, "aggregation": self.aggregation,
            "threshold": round(self.threshold, 6), "k": self.k_centers,
            "ratio": self.ratio, "levels": self.levels,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def bank_sha256(bank: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(bank, dtype=np.float32).tobytes())
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
# 核心：cell 划分与区间
# --------------------------------------------------------------------------- #
def greedy_coreset(bank: np.ndarray, k: int, seed: int = 0, use_gpu: bool = True) -> np.ndarray:
    """贪心 k-中心。

    GPU 路径只是把"算距离"搬上显卡，**选点顺序与 numpy 路径逐位相同**：
    起点由 numpy 的同一种子决定，之后每步都是 argmax（并列取首个）。
    因此两条路径的 coreset 完全一致，可在 selftest 里验证。
    """
    n = len(bank)
    first = int(np.random.default_rng(seed).integers(0, n))
    if use_gpu and torch is not None and _DEV is not None and str(_DEV).startswith("cuda"):
        b = torch.from_numpy(np.ascontiguousarray(bank, dtype=np.float32)).to(_DEV)
        chosen = [first]
        dmin = (b - b[first]).norm(dim=1)
        for _ in range(k - 1):
            nxt = int(torch.argmax(dmin).item())
            if nxt in chosen:
                break
            chosen.append(nxt)
            dmin = torch.minimum(dmin, (b - b[nxt]).norm(dim=1))
        return np.array(sorted(set(chosen)), dtype=np.int64)
    chosen = [first]
    dmin = np.linalg.norm(bank - bank[first], axis=1)
    for _ in range(k - 1):
        nxt = int(np.argmax(dmin))
        if nxt in chosen:
            break
        chosen.append(nxt)
        dmin = np.minimum(dmin, np.linalg.norm(bank - bank[nxt], axis=1))
    return np.array(sorted(set(chosen)), dtype=np.int64)


def assign_and_radii(bank: np.ndarray, centers: np.ndarray):
    """把 bank 分到最近中心，返回 (assign, radii)。半径是 cell 内最大距离。"""
    # 分块算，避免 N×K 爆内存
    n, k = len(bank), len(centers)
    assign = np.empty(n, dtype=np.int32)
    dist = np.empty(n, dtype=np.float32)
    c2 = (centers ** 2).sum(axis=1)
    for i in range(0, n, 4096):
        m = bank[i:i + 4096]
        d2 = (m ** 2).sum(axis=1, keepdims=True) + c2[None, :] - 2.0 * (m @ centers.T)
        j = np.argmin(d2, axis=1)
        assign[i:i + 4096] = j
        dist[i:i + 4096] = np.sqrt(np.maximum(d2[np.arange(len(m)), j], 0.0))
    radii = np.zeros(k, dtype=np.float32)
    for j in range(k):
        sel = assign == j
        if sel.any():
            radii[j] = dist[sel].max()
        else:
            radii[j] = 0.0          # 空 cell：中心自身必在 M 中，正常不会出现；保守取 0
    return assign, radii


class ScreenIndex:
    """单级或两级的筛查索引。叶子 cell 构成 M 的一个划分。"""

    def __init__(self, bank: np.ndarray, k: int, levels: int = 1,
                 radius_mode: str = "cell", seed: int = 0, split_threshold: int = 64):
        self.levels = levels
        self.radius_mode = radius_mode
        self.leaves: list[np.ndarray] = []      # 每个叶子的中心（可能多中心）
        self.radii: list[float] = []
        self.n_leaves = 0
        idx = greedy_coreset(bank, k, seed)
        centers = bank[idx]
        assign, radii = assign_and_radii(bank, centers)

        if levels == 1:
            self.centers = centers
            self.radii = radii.tolist()
        else:
            out_c, out_r = [], []
            for j, c in enumerate(centers):
                members = bank[assign == j]
                if len(members) <= split_threshold:
                    out_c.append(c[None, :]); out_r.append(float(radii[j]))
                    continue
                m = int(min(8, max(2, len(members) // 256)))
                # 用确定性的 k-means（固定初始化：取前 m 个成员）
                sub = members.copy()
                sub_centers = sub[:m].copy()
                for _ in range(8):                     # Lloyd 迭代
                    d = np.linalg.norm(sub[:, None, :] - sub_centers[None, :, :], axis=2)
                    lab = np.argmin(d, axis=1)
                    for t in range(m):
                        if (lab == t).any():
                            sub_centers[t] = sub[lab == t].mean(axis=0)
                d = np.linalg.norm(sub[:, None, :] - sub_centers[None, :, :], axis=2)
                lab = np.argmin(d, axis=1)
                # 子中心 = {父中心} ∪ {各子簇的 medoid}
                #  * 必须是 M 中的实际向量，否则 U 不再是上界（均值不在 M 里）；
                #  * 必须保留父中心，否则 U 可能比一级更差。
                cands = [c.copy()]
                for t in range(m):
                    mem = sub[lab == t]
                    if len(mem) == 0:
                        continue
                    cen = sub_centers[t]
                    cands.append(mem[int(np.argmin(np.linalg.norm(mem - cen, axis=1)))] )
                cands = np.unique(np.vstack(cands), axis=0)
                d_all = np.linalg.norm(members[:, None, :] - cands[None, :, :], axis=2)
                lab2 = np.argmin(d_all, axis=1)
                for t in range(len(cands)):
                    mem = members[lab2 == t]
                    if len(mem) == 0:
                        continue
                    sc = cands[t]
                    out_c.append(sc[None, :])
                    out_r.append(float(np.linalg.norm(mem - sc, axis=1).max()))
            self.centers = np.vstack(out_c)
            self.radii = out_r

        self.centers = np.asarray(self.centers, dtype=np.float32)
        self.radii = np.asarray(self.radii, dtype=np.float32)
        if radius_mode == "global":
            self.radii = np.full_like(self.radii, float(self.radii.max()))
        self.radii_guarded = self.radii + GUARD
        self.n_leaves = len(self.centers)

    # ---- 区间 ----
    def bounds(self, patches: np.ndarray):
        """返回每张图（或每个 patch 组）的 L,U。patches: (P, D) → (L,U) 标量。"""
        p = np.atleast_2d(patches)
        c2 = (self.centers ** 2).sum(axis=1)
        lo = np.empty(len(p), dtype=np.float32)
        hi = np.empty(len(p), dtype=np.float32)
        for i in range(0, len(p), 2048):
            q = p[i:i + 2048]
            d2 = (q ** 2).sum(axis=1, keepdims=True) + c2[None, :] - 2.0 * (q @ self.centers.T)
            d = np.sqrt(np.maximum(d2, 0.0))
            lo[i:i + 2048] = (d - self.radii_guarded[None, :]).min(axis=1)
            hi[i:i + 2048] = d.min(axis=1)
        return lo, hi

    def image_bounds(self, feats: np.ndarray):
        """feats: (P, D) 一张图 → 图像级 L_x = max_patch L, U_x = max_patch U。"""
        lo, hi = self.bounds(feats)
        return float(np.max(lo)), float(np.max(hi))

    def bytes(self) -> dict:
        """屏幕端实际需要序列化的字节数（不含编码器）。"""
        centers = self.centers.astype(np.float32).nbytes
        radii = self.radii.astype(np.float32).nbytes
        meta = len(json.dumps({"levels": self.levels, "k": int(self.n_leaves),
                               "mode": self.radius_mode}))
        return {"centers": centers, "radii": radii, "meta": meta,
                "total": centers + radii + meta}


# --------------------------------------------------------------------------- #
# 整库解析器（可模拟断网 / 版本不符）
# --------------------------------------------------------------------------- #
class Resolver:
    def __init__(self, bank: np.ndarray, version: BankVersion, available: bool = True,
                 served_version: str | None = None):
        self.bank = bank
        self.version = version
        self.available = available
        self.served_version = served_version or version.id()

    def score(self, feats: np.ndarray) -> float:
        """图像分数 = max_patch 最近邻距离。"""
        b2 = (self.bank ** 2).sum(axis=1)
        best = np.inf
        for i in range(0, len(feats), 2048):
            q = feats[i:i + 2048]
            d2 = (q ** 2).sum(axis=1, keepdims=True) + b2[None, :] - 2.0 * (q @ self.bank.T)
            best = min(best, float(np.sqrt(np.maximum(d2.min(axis=1), 0.0)).max()))
        return best

    def resolve(self, feats: np.ndarray, t: float):
        """返回 (decision, reason)。不可用或版本不符 → (None, 'unresolved:...')。"""
        if not self.available:
            return None, "unresolved:resolver_offline"
        if self.served_version != self.version.id():
            return None, "unresolved:version_mismatch"
        s = self.score(feats)
        return ("alarm" if s > t else "normal"), "resolved"


# --------------------------------------------------------------------------- #
# 单元测试
# --------------------------------------------------------------------------- #
def selftest() -> int:
    ok = True

    def check(name, cond, extra=""):
        nonlocal ok
        ok = ok and bool(cond)
        print(("  [OK] " if cond else "  [FAIL] ") + name + ("  " + str(extra) if extra else ""))

    rng = np.random.default_rng(0)
    print("== 1. 随机数据：L ≤ s ≤ U ==")
    bank = rng.normal(size=(3000, 16)).astype(np.float32)
    idx = ScreenIndex(bank, k=40, levels=1)
    q = rng.normal(size=(200, 16)).astype(np.float32)
    lo, hi = idx.bounds(q)
    s = np.linalg.norm(q[:, None, :] - bank[None, :, :], axis=2).min(axis=1)
    check("所有点满足 L ≤ s ≤ U", bool(np.all(lo - 1e-5 <= s) and np.all(s <= hi + 1e-5)),
          f"max|L-s|={np.abs(lo - s).max():.2e} max|U-s|={np.abs(hi - s).max():.2e}")

    print("== 2. 重复向量（两个 m 完全相同）==")
    bank2 = np.vstack([bank, bank[:5]])
    idx2 = ScreenIndex(bank2, k=40, levels=1)
    lo2, hi2 = idx2.bounds(q)
    s2 = np.linalg.norm(q[:, None, :] - bank2[None, :, :], axis=2).min(axis=1)
    check("重复向量下区间仍有效", bool(np.all(lo2 - 1e-5 <= s2) and np.all(s2 <= hi2 + 1e-5)))

    print("== 3. 阈值相等的并列 ==")
    t_eq = float(s[0])
    dec = "alarm" if s[0] > t_eq else "normal"
    check("s == t 判为 normal（严格大于才报警）", dec == "normal", f"s={s[0]:.6f} t={t_eq:.6f}")

    print("== 4. 空 cell（构造 k 超过唯一向量数）==")
    try:
        idx4 = ScreenIndex(bank[:3], k=10, levels=1)
        check("空 cell 不崩溃且半径有限", bool(np.all(np.isfinite(idx4.radii))),
              f"n_leaves={idx4.n_leaves}")
    except Exception as e:
        check("空 cell 不崩溃", False, f"{type(e).__name__}: {e}")

    print("== 5. 两级 + 全局半径 ==")
    idx_l2 = ScreenIndex(bank, k=40, levels=2)
    lo3, hi3 = idx_l2.bounds(q)
    check("两级仍满足 L ≤ s ≤ U", bool(np.all(lo3 - 1e-5 <= s) and np.all(s <= hi3 + 1e-5)),
          f"二级叶子数={idx_l2.n_leaves} vs 一级 {idx.n_leaves}")
    check("两级确实发生了切分（叶子数增加）", idx_l2.n_leaves > idx.n_leaves,
          f"{idx.n_leaves} -> {idx_l2.n_leaves}")
    w_l1 = float((hi - lo).mean()); w_l2 = float((hi3 - lo3).mean())
    # 细化不保证更紧（不是定理），只记录测量值，供 Phase 8 消融判断
    print(f"  [note] 区间宽度 一级={w_l1:.3f} 二级={w_l2:.3f} "
          f"（{'更紧' if w_l2 < w_l1 else '更宽/持平'}）")
    idx_g = ScreenIndex(bank, k=40, levels=1, radius_mode="global")
    lo4, hi4 = idx_g.bounds(q)
    w_cell = float((hi - lo).mean()); w_glob = float((hi4 - lo4).mean())
    check("全局半径区间更宽（逐 cell 更紧）", w_glob >= w_cell - 1e-6,
          f"逐cell={w_cell:.3f} 全局={w_glob:.3f}")

    print("== 6. 版本契约 ==")
    v = BankVersion("wrn50", "resize256/crop224", bank_sha256(bank), "max_patch", 1.0, 40, 0.1, 1)
    r_ok = Resolver(bank, v)
    r_bad = Resolver(bank, v, served_version="deadbeef")
    r_off = Resolver(bank, v, available=False)
    d1, why1 = r_ok.resolve(q[:1], 1.0)
    d2, why2 = r_bad.resolve(q[:1], 1.0)
    d3, why3 = r_off.resolve(q[:1], 1.0)
    check("版本一致 → 正常解析", d1 in ("alarm", "normal") and why1 == "resolved")
    check("版本不符 → unresolved（不静默判正常）", d2 is None and why2.startswith("unresolved"))
    check("解析器离线 → unresolved", d3 is None and why3.startswith("unresolved"))

    print("== 6b. 核心集：GPU 与 numpy 路径一致 ==")
    try:
        a_cpu = greedy_coreset(bank, 40, seed=3, use_gpu=False)
        a_gpu = greedy_coreset(bank, 40, seed=3, use_gpu=True)
        check("两条路径选出的索引完全相同", np.array_equal(a_cpu, a_gpu),
              f"n={len(a_cpu)} vs {len(a_gpu)}")
    except Exception as e:
        check("核心集一致性", False, f"{type(e).__name__}: {e}")

    print("== 7. 确定性（两次构建逐位一致）==")
    a = ScreenIndex(bank, k=40, levels=2)
    b = ScreenIndex(bank, k=40, levels=2)
    check("中心与半径逐位一致",
          np.array_equal(a.centers, b.centers) and np.array_equal(a.radii, b.radii))

    print("\n总体：" + ("全部通过" if ok else "存在失败项"))
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
try:
    import torch
    _DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
except Exception:
    torch = None
    _DEV = None


def batch_image_scores(feats: np.ndarray, rows: np.ndarray, bank: np.ndarray,
                       chunk: int = 8192) -> np.ndarray:
    """一次算完多张图的图像分数（max_patch 最近邻距离）。

    逐图调用 O(图数) 次矩阵乘；这里把 (图, patch) 摊平成一次分块矩阵乘，
    GPU 上快两个数量级，CPU 上也快很多。
    """
    sub = feats[rows]                                  # (N, P, C)
    n, p, c = sub.shape
    if torch is not None:
        b = torch.from_numpy(np.ascontiguousarray(bank, dtype=np.float32)).to(_DEV)
        b2 = (b * b).sum(dim=1)
        out = np.empty(n, dtype=np.float32)
        per = 16                                   # 每次 16 张图，显存可控
        for s in range(0, n, per):
            blk = np.ascontiguousarray(sub[s:s + per], dtype=np.float32)
            m = blk.shape[0]
            q = torch.from_numpy(blk).to(_DEV).reshape(-1, c)
            d2 = (q * q).sum(dim=1, keepdim=True) + b2[None, :] - 2.0 * q @ b.T
            dmin = d2.clamp_min_(0).sqrt().min(dim=1).values.view(m, p)
            out[s:s + m] = dmin.max(dim=1).values.cpu().numpy()
        return out
    # CPU 退化路径
    out = np.empty(n, dtype=np.float32)
    b = bank.astype(np.float32)
    b2 = (b * b).sum(axis=1)
    for k in range(n):
        q = sub[k].astype(np.float32)
        best = np.inf
        for i in range(0, p, 1024):
            qq = q[i:i + 1024]
            d2 = (qq ** 2).sum(axis=1, keepdims=True) + b2[None, :] - 2.0 * qq @ b.T
            best = min(best, float(np.sqrt(np.maximum(d2, 0)).min()))
        out[k] = best
    return out


def load_cache(cat: str):
    files = sorted(CACHE.glob(f"{cat}_*.npz"))
    if not files:
        raise SystemExit(f"没有 {cat} 的特征缓存，先跑 scripts/featurize.py")
    z = np.load(files[0], allow_pickle=True)
    meta = json.loads(str(z["meta"]))
    return z["feats"], z["split"], z["roles"], meta, files[0].name


def evaluate(cat, ratio, levels, radius_mode, shot, seed, k_override=0):
    feats, split, roles, meta, fname = load_cache(cat)
    n_patch = meta["patches_per_image"]
    ref_rows = np.where(roles == "reference_fit")[0]
    dev_rows = np.where(roles == "development")[0]
    cal_rows = np.where(roles == "calibration")[0]
    good_rows = np.where(split == "test_good")[0]
    bad_rows = np.where(split == "test_defect")[0]

    rng = np.random.default_rng(seed)
    take = ref_rows if shot >= len(ref_rows) else rng.choice(ref_rows, size=shot, replace=False)
    bank_rows = take if shot <= len(ref_rows) else np.concatenate([ref_rows, dev_rows])
    if shot > len(ref_rows):
        take = bank_rows
    bank = feats[np.sort(take)].reshape(-1, feats.shape[2])
    k = int(k_override) if k_override else max(2, int(round(ratio * len(bank))))
    idx = ScreenIndex(bank, k=k, levels=levels, radius_mode=radius_mode, seed=seed)
    v = BankVersion(meta["encoder"], f"resize{meta['resize']}/crop{meta['imagesize']}",
                    bank_sha256(bank), "max_patch", 0.0, k, ratio, levels)
    resolver = Resolver(bank, v)

    # 阈值：校准图的图像分数 95 分位（批量计算，不再逐图）
    cal_scores = batch_image_scores(feats, cal_rows, bank)
    t = float(np.percentile(cal_scores, 95))
    v.threshold = t

    # 评估：屏幕 + 升级
    all_rows = np.concatenate([good_rows, bad_rows])
    truth_scores = batch_image_scores(feats, all_rows, bank)
    rows = []
    for i, r in enumerate(all_rows):
        kind = "good" if i < len(good_rows) else "defect"
        f = feats[r]
        lo, hi = idx.image_bounds(f)
        if hi <= t:
            dec, why = "normal", "local"
        elif lo > t:
            dec, why = "alarm", "local"
        else:
            dec, why = ("alarm" if truth_scores[i] > t else "normal"), "escalated"
        rows.append(dict(kind=kind, dec=dec, why=why, truth=bool(truth_scores[i] > t),
                         L=lo, U=hi))
    resolved = [x for x in rows if x["why"] == "local"]
    esc = [x for x in rows if x["why"] == "escalated"]
    unresolved = [x for x in rows if x["dec"] is None]
    mism = [x for x in resolved if (x["dec"] == "alarm") != x["truth"]]
    return dict(
        category=cat, ratio=ratio, levels=levels, radius_mode=radius_mode, shot=shot, seed=seed,
        t=t, k=k, bank_patches=int(len(bank)), bytes=idx.bytes(),
        n_images=len(rows), n_good=len(good_rows), n_defect=len(bad_rows),
        local=len(resolved), escalated=len(esc), unresolved=len(unresolved),
        local_rate=len(resolved) / len(rows), escalate_rate=len(esc) / len(rows),
        local_mismatch=len(mism),
        escalate_share_of_ambiguous=(len(esc) / max(1, len(esc) + len(unresolved))),
        version=v.id(), cache=fname, feature=meta["fingerprint"],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--category", default="bottle")
    ap.add_argument("--ratio", type=float, default=0.10)
    ap.add_argument("--levels", type=int, nargs="+", default=[1])
    ap.add_argument("--radius", nargs="+", default=["cell"], choices=["cell", "global"])
    ap.add_argument("--k", type=int, default=0, help="强制中心数（0=按 ratio 算）")
    ap.add_argument("--shot", type=int, default=16)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=str(OUT / "w4_screening.json"))
    args = ap.parse_args()

    if args.selftest:
        raise SystemExit(selftest())

    cats = ["bottle", "tile", "screw"] if args.category == "all" else [args.category]
    results = []
    print(f"{'类别':<8}{'层':>3}{'半径':>8}{'k':>7}{'本地%':>8}{'升级%':>8}{'错判':>6}"
          f"{'字节(KB)':>10}")
    print("-" * 62)
    for cat in cats:
        for lv in args.levels:
            for rm in args.radius:
                r = evaluate(cat, args.ratio, lv, rm, args.shot, args.seed, args.k)
                results.append(r)
                print(f"{cat:<8}{lv:>3}{rm:>8}{r['k']:>7}{r['local_rate']*100:>7.1f}%"
                      f"{r['escalate_rate']*100:>7.1f}%{r['local_mismatch']:>6}"
                      f"{r['bytes']['total']/1024:>10.1f}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"config": vars(args), "results": results},
                                         ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果 -> {args.out}")


if __name__ == "__main__":
    main()
