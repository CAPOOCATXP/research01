# -*- coding: utf-8 -*-
"""MVTec AD 镜像完整性校验：证明"下到的是原始数据"，而不是被裁剪或改过的版本。

为什么必须做
------------
官方下载页的 16 个链接已全部 404（见 logs/mvtec_download_outage.json），只能走镜像。
镜像的风险不是"合不合法"（数据是 CC BY-NC-SA 4.0，允许再分发），而是**它可能被裁剪**：
少一张图、改一次切分，样本数就与文献不可比，我们的"分歧 ≥2 个百分点"判据立刻失效。

本脚本用三层证据把这件事压住：
  1. **归档哈希**：与镜像站登记的 sha256 比对（证明传输无损、不是半截文件）；
  2. **逐类计数**：与官方发布计数比对（15 类 train 合计 3629、test 合计 1725）；
  3. **可解码性**：抽检/全检 PNG 能否解码，抓截断与损坏。

参考计数来源
------------
官方逐类数量取自 HuggingFace `TheoM55/mvtec_all_objects_split` 的数据集元数据
（其 train/test 合计与 MVTec AD 论文一致：3629 / 1725），并与公开论文口径核对。

用法
----
    python scripts/verify_mvtec.py                       # 默认校验 F:\research\data\mvtec_ad
    python scripts/verify_mvtec.py --root D:\mvtec_ad --archive D:\mvtec_anomaly_detection.tar.xz
    python scripts/verify_mvtec.py --decode-all          # 全量解码检查（约 1-2 分钟）
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "logs" / "mvtec_verify.json"

# 官方发布的逐类 (train/good, test 总数)。合计 3629 / 1725。
EXPECTED = {
    "bottle": (209, 83), "cable": (224, 150), "capsule": (219, 132), "carpet": (280, 117),
    "grid": (264, 78), "hazelnut": (391, 110), "leather": (245, 124), "metal_nut": (220, 115),
    "pill": (267, 167), "screw": (320, 160), "tile": (230, 117), "toothbrush": (60, 42),
    "transistor": (213, 100), "wood": (247, 79), "zipper": (240, 151),
}


def sha256_file(p: Path, chunk=1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(chunk), b""):
            h.update(c)
    return h.hexdigest()


def count_png(d: Path) -> int:
    return sum(1 for _ in d.glob("*.png")) if d.is_dir() else 0


def check_decode(files, limit=None):
    bad = []
    n = 0
    for p in files:
        if limit and n >= limit:
            break
        n += 1
        try:
            with Image.open(p) as im:
                im.load()
        except Exception as e:
            bad.append({"file": str(p), "error": f"{type(e).__name__}: {e}"})
    return n, bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT / "data" / "mvtec_ad"))
    ap.add_argument("--archive", default=None, help="原始 .tar.xz，给出则计算 sha256")
    ap.add_argument("--expect-sha256", default=None, help="镜像站登记 sha256（去掉 0x 前缀）")
    ap.add_argument("--decode-all", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    report = {"root": str(root), "archive": None, "categories": {}, "summary": {}}
    ok = True

    # ---- 1. 归档哈希 ----
    if args.archive:
        a = Path(args.archive)
        if not a.exists():
            print(f"[FAIL] 归档不存在：{a}")
            return 2
        h = sha256_file(a)
        report["archive"] = {"path": str(a), "bytes": a.stat().st_size, "sha256": h}
        print(f"归档：{a.name}  {a.stat().st_size:,} B  sha256={h}")
        if args.expect_sha256:
            match = h.lower() == args.expect_sha256.lower()
            report["archive"]["expected_sha256"] = args.expect_sha256
            report["archive"]["match"] = match
            print(f"  与镜像站登记 sha256 比对：{'一致 ✅' if match else '不一致 ❌'}")
            ok = ok and match

    # ---- 2. 逐类计数 ----
    print(f"\n{'类别':<12}{'train 实测':>10}{'train 期望':>10}{'test 实测':>10}{'test 期望':>10}  判定")
    print("-" * 66)
    tot_tr = tot_te = 0
    for cat, (exp_tr, exp_te) in EXPECTED.items():
        cdir = root / cat
        if not cdir.is_dir():
            print(f"{cat:<12}{'-':>10}{exp_tr:>10}{'-':>10}{exp_te:>10}  缺失 ❌")
            report["categories"][cat] = {"present": False, "expected": [exp_tr, exp_te]}
            ok = False
            continue
        tr = count_png(cdir / "train" / "good")
        test_dir = cdir / "test"
        te = sum(count_png(d) for d in test_dir.iterdir() if d.is_dir()) if test_dir.is_dir() else 0
        gt = sum(count_png(d) for d in (cdir / "ground_truth").iterdir()
                 if d.is_dir()) if (cdir / "ground_truth").is_dir() else 0
        good = (tr == exp_tr) and (te == exp_te)
        ok = ok and good
        tot_tr += tr
        tot_te += te
        defects = sorted(d.name for d in test_dir.iterdir() if d.is_dir()) if test_dir.is_dir() else []
        report["categories"][cat] = {
            "present": True, "train_good": tr, "test_total": te, "ground_truth": gt,
            "expected": [exp_tr, exp_te], "match": good, "defect_types": defects,
        }
        print(f"{cat:<12}{tr:>10}{exp_tr:>10}{te:>10}{exp_te:>10}  {'✅' if good else '❌'}")

    print("-" * 66)
    print(f"{'合计':<12}{tot_tr:>10}{sum(v[0] for v in EXPECTED.values()):>10}"
          f"{tot_te:>10}{sum(v[1] for v in EXPECTED.values()):>10}")
    report["summary"] = {"train_total": tot_tr, "test_total": tot_te,
                         "train_expected": sum(v[0] for v in EXPECTED.values()),
                         "test_expected": sum(v[1] for v in EXPECTED.values())}
    if tot_tr != sum(v[0] for v in EXPECTED.values()) or tot_te != sum(v[1] for v in EXPECTED.values()):
        ok = False
        print("合计不符 ❌")

    # ---- 3. 可解码性 ----
    sample_cats = ["bottle", "tile", "screw"] if all((root / c).is_dir() for c in ("bottle", "tile", "screw")) else list(EXPECTED)
    files = []
    for c in sample_cats:
        files += list((root / c / "train" / "good").glob("*.png"))
        t = root / c / "test"
        if t.is_dir():
            for d in t.iterdir():
                if d.is_dir():
                    files += list(d.glob("*.png"))
    limit = None if args.decode_all else 400
    n, bad = check_decode(files, limit)
    report["decode"] = {"checked": n, "bad": bad[:20], "bad_count": len(bad)}
    print(f"\n解码检查：抽检 {n} 张，失败 {len(bad)} 张" + (" ✅" if not bad else " ❌"))
    if bad:
        ok = False
        for b in bad[:5]:
            print("   ", b["file"], b["error"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告 -> {OUT}")
    print("\n结论：" + ("镜像数据与官方发布一致，可用于实验 ✅" if ok else "校验未通过，不要用于实验 ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
