# -*- coding: utf-8 -*-
"""W1 / A14-4：生成 reference-fit / development / calibration 三角色图像清单。

设计要点（导师 handout A7 的硬要求）：
  1. 三种角色只从「正常样本」里划（MVTec: train/good；AD 2: train/good + validation/good）；
  2. 同一张原图绝不跨角色；
  3. 划分必须可复现 —— 用 sha256(relative_path + seed) 排序切片，而不是依赖
     random.shuffle 的实现细节；
  4. 每张图记录 sha256，因为「清单被改了一行」等于换了一份数据集；
  5. 测试集缺陷标签在协议冻结前不允许参与任何选择，因此本脚本**不读 test 目录的内容**，
     只在报告里统计其存在性（数量而已）。

用法：
    # 真实数据（需要先放好 MVTec AD）
    python make_manifests.py --data-root F:\\research\\data\\mvtec_ad --categories bottle tile screw

    # 无数据时的自检：造一棵合成目录树，验证划分逻辑与互斥检查
    python make_manifests.py --self-test
"""
import argparse
import csv
import hashlib
import shutil
import sys
from pathlib import Path

PIL_AVAILABLE = True
try:
    from PIL import Image
except Exception:
    PIL_AVAILABLE = False

DEFAULT_OUT = Path(r"F:\research\manifests")
N_REF = 16
N_DEV = 24
SEED = 0


def sha256_file(path, block=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(block)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def collect_normals(data_root: Path, category: str):
    """返回该类别所有正常样本（相对路径字符串），来自 train/good 与 validation/good。"""
    paths = []
    for sub in ("train/good", "validation/good"):
        d = data_root / category / sub
        if d.is_dir():
            for p in sorted(d.glob("*.png")):
                paths.append(p)
    return paths


def split_roles(paths, n_ref=N_REF, n_dev=N_DEV, seed=SEED):
    """确定性划分：按 sha256(相对路径 + seed) 升序切片。"""
    keyed = []
    for p in paths:
        k = hashlib.sha256(("%s|%d" % (p.name, seed)).encode("utf-8")).hexdigest()
        keyed.append((k, p))
    keyed.sort(key=lambda t: t[0])
    order = [p for _, p in keyed]
    ref = order[:n_ref]
    dev = order[n_ref:n_ref + n_dev]
    cal = order[n_ref + n_dev:]
    return {"reference_fit": ref, "development": dev, "calibration": cal}


def write_role_csv(out_dir: Path, category: str, role: str, files, data_root: Path, seed: int):
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / ("%s_%s.csv" % (category, role))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "role", "relative_path", "source_split", "orig_id",
                    "sha256", "seed", "note"])
        for p in files:
            rel = str(p.relative_to(data_root)).replace("\\", "/")
            src = "train/good" if "train" in rel else "validation/good"
            w.writerow([category, role, rel, src, p.stem,
                        sha256_file(p), seed, "normal-only role split (W1)"])
    return path


def check_disjoint(out_dir: Path):
    """读回所有清单，检查同一 sha256 / 同一 relative_path 是否跨角色。"""
    by_hash, by_path = {}, {}
    for f in sorted(out_dir.glob("*_*.csv")):
        if f.name == "all_roles.csv":
            continue
        with open(f, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                by_hash.setdefault(row["sha256"], set()).add(row["role"])
                by_path.setdefault(row["relative_path"], set()).add(row["role"])
    bad_h = {k: sorted(v) for k, v in by_hash.items() if len(v) > 1}
    bad_p = {k: sorted(v) for k, v in by_path.items() if len(v) > 1}
    return bad_h, bad_p, len(by_path)


def run(data_root: Path, categories, out_dir: Path, seed: int, n_ref: int, n_dev: int):
    print("data_root = %s" % data_root)
    print("out_dir   = %s" % out_dir)
    print("seed = %d, reference_fit = %d, development = %d, calibration = 其余全部"
          % (seed, n_ref, n_dev))
    print("-" * 76)
    summary = []
    missing = []
    for cat in categories:
        normals = collect_normals(data_root, cat)
        if not normals:
            missing.append(cat)
            print("[MISS] %-10s 找不到正常样本（%s\\%s\\train\\good）" % (cat, data_root, cat))
            continue
        roles = split_roles(normals, n_ref, n_dev, seed)
        counts = {r: len(v) for r, v in roles.items()}
        for role, files in roles.items():
            write_role_csv(out_dir, cat, role, files, data_root, seed)
        # 只统计 test 目录的文件数，不读取内容（缺陷标签不允许参与选择）
        test_dir = data_root / cat / "test"
        n_test = len(list(test_dir.rglob("*.png"))) if test_dir.is_dir() else 0
        summary.append((cat, len(normals), counts["reference_fit"],
                        counts["development"], counts["calibration"], n_test))
        if counts["calibration"] < 100:
            print("[WARN] %-10s calibration 只有 %d 张 —— 在 5%% 名义误报率上估计分位数偏不稳"
                  % (cat, counts["calibration"]))
    print("-" * 76)
    print("%-10s %8s %12s %12s %12s %8s" %
          ("category", "normals", "reference", "development", "calibration", "test*"))
    for row in summary:
        print("%-10s %8d %12d %12d %12d %8d" % row)
    print("* test 只统计文件数，内容与标签在此阶段一律不读。")

    if missing:
        print("\n缺少数据的类别：%s" % ", ".join(missing))
        print("-> 真实清单未生成。MVTec AD 需在官网填表获取（本机尚未获批）。")

    bad_h, bad_p, n_total = check_disjoint(out_dir)
    print("\n互斥检查（读回 CSV 复查）：")
    print("  不同角色共享同一 sha256 的样本数 : %d" % len(bad_h))
    print("  不同角色共享同一路径的样本数     : %d" % len(bad_p))
    print("  清单中样本总数                   : %d" % n_total)
    if bad_h or bad_p:
        print("  !! 存在跨角色重叠，清单作废：")
        for k, v in list(bad_h.items())[:5]:
            print("     %s -> %s" % (k[:16], v))
    else:
        print("  OK：没有任何一张原图出现在一个以上的角色里。")
    return 0 if not (bad_h or bad_p) else 1


def make_synthetic(root: Path, categories, n_per_cat=100, n_test=8):
    """造一棵 MVTec 风格的合成目录树，仅用于验证划分逻辑。"""
    if root.exists():
        shutil.rmtree(root)
    for cat in categories:
        for sub, n in (("train/good", n_per_cat), ("test/good", n_test // 2),
                       ("test/broken", n_test // 2), ("ground_truth/broken", n_test // 2)):
            d = root / cat / sub
            d.mkdir(parents=True, exist_ok=True)
            for i in range(n):
                name = "%03d.png" % i
                if sub.startswith("ground_truth"):
                    name = "%03d_mask.png" % i
                p = d / name
                if PIL_AVAILABLE:
                    import numpy as np
                    from PIL import Image
                    rng = np.random.default_rng(abs(hash((cat, sub, i))) % (2 ** 32))
                    arr = (rng.random((16, 16, 3)) * 255).astype("uint8")
                    Image.fromarray(arr).save(p)
                else:
                    p.write_bytes(("synthetic %s %s %d" % (cat, sub, i)).encode())
    return root


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=r"F:\research\data\mvtec_ad")
    ap.add_argument("--categories", nargs="+", default=["bottle", "tile", "screw"])
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--n-ref", type=int, default=N_REF)
    ap.add_argument("--n-dev", type=int, default=N_DEV)
    ap.add_argument("--self-test", action="store_true",
                    help="在 tmp 下造合成数据，验证划分与互斥检查")
    args = ap.parse_args()

    if args.self_test:
        syn = Path(r"F:\research\tmp\synthetic_mvtec")
        print("=" * 76)
        print("自检模式：合成数据（**不是 MVTec AD**，只用于验证划分逻辑）")
        print("=" * 76)
        make_synthetic(syn, args.categories)
        out = Path(r"F:\research\tmp\synthetic_manifests")
        if out.exists():
            shutil.rmtree(out)
        rc1 = run(syn, args.categories, out, args.seed, args.n_ref, args.n_dev)

        # 复现性：再跑一次，比较文件哈希
        out2 = Path(r"F:\research\tmp\synthetic_manifests_rerun")
        if out2.exists():
            shutil.rmtree(out2)
        run(syn, args.categories, out2, args.seed, args.n_ref, args.n_dev)
        same = True
        for f in sorted(out.glob("*.csv")):
            g = out2 / f.name
            if not g.exists() or sha256_file(f) != sha256_file(g):
                same = False
                print("  !! 复现失败：%s" % f.name)
        print("\n复现性检查：两次运行的清单逐字节%s" % ("一致" if same else "不一致"))
        print("\n自检结论：%s" % ("通过" if (rc1 == 0 and same) else "未通过"))
        return 0 if (rc1 == 0 and same) else 1

    out = Path(args.out)
    print("=" * 76)
    print("真实数据模式")
    print("=" * 76)
    return run(Path(args.data_root), args.categories, out, args.seed, args.n_ref, args.n_dev)


if __name__ == "__main__":
    sys.exit(main())
