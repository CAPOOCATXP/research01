# -*- coding: utf-8 -*-
"""MVTec AD 就地体检：确认目录结构、划分与图像可读，避免"数据看起来在了、其实不对"。

为什么需要它
------------
MVTec AD 的压缩包解压后可能多一层目录（如 mvtec_anomaly_detection/bottle/...），
也可能因为 Windows 长路径解压失败而缺文件。直接开跑会在特征提取阶段莫名其妙地
报"找不到 train/good"或数量对不上，浪费一次几十分钟的运行。

本脚本只做三件事：
  1. 定位真正的数据集根（自动剥掉多余的外层目录）；
  2. 按类别统计 train/good、test/*、ground_truth/* 的文件数；
  3. 抽读每类第一张图，确认能解码、尺寸合理，并打印尺寸分布。
不修改任何数据。

用法
----
    python scripts/prepare_mvtec.py                       # 默认查 F:\research\data\mvtec_ad
    python scripts/prepare_mvtec.py --root D:\mvtec_ad
    python scripts/prepare_mvtec.py --fix-layout          # 把多套一层的外层目录摊平
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "data" / "mvtec_ad"
REPORT = ROOT / "logs" / "mvtec_dataset_check.json"

EXPECTED_CATEGORIES = [
    "bottle", "cable", "capsule", "carpet", "grid", "hazelnut", "leather", "metal_nut",
    "pill", "screw", "tile", "toothbrush", "transistor", "wood", "zipper",
]


def find_dataset_root(root: Path) -> Path:
    """若 root 下只有一个目录且该目录里有类别文件夹，则视为多套了一层。"""
    if any((root / c / "train" / "good").is_dir() for c in EXPECTED_CATEGORIES):
        return root
    subs = [d for d in root.iterdir() if d.is_dir()] if root.is_dir() else []
    for s in subs:
        if any((s / c / "train" / "good").is_dir() for c in EXPECTED_CATEGORIES):
            return s
    return root


def count_pngs(d: Path) -> int:
    return len(list(d.rglob("*.png"))) if d.is_dir() else 0


def inspect(root: Path) -> dict:
    cats = [d.name for d in sorted(root.iterdir()) if d.is_dir()] if root.is_dir() else []
    report = {"root": str(root), "exists": root.is_dir(), "categories": {}}
    for c in cats:
        cdir = root / c
        train_good = cdir / "train" / "good"
        test = cdir / "test"
        gt = cdir / "ground_truth"
        if not train_good.is_dir() and not test.is_dir():
            continue
        rec = {
            "train_good": count_pngs(train_good),
            "test_total": count_pngs(test),
            "test_good": count_pngs(test / "good"),
            "test_defect_dirs": sorted([d.name for d in test.iterdir() if d.is_dir()])
            if test.is_dir() else [],
            "ground_truth": count_pngs(gt),
            "sizes": {},
            "readable": None,
        }
        # 抽读每类第一张正常图 + 第一张缺陷图
        probes = []
        if train_good.is_dir():
            probes.append(next(iter(sorted(train_good.glob("*.png"))), None))
        if test.is_dir():
            for sub in sorted([d for d in test.iterdir() if d.is_dir()]):
                p = next(iter(sorted(sub.glob("*.png"))), None)
                if p:
                    probes.append(p)
                    break
        ok = True
        for p in [x for x in probes if x]:
            try:
                with Image.open(p) as im:
                    im.load()
                    rec["sizes"][str(im.size)] = rec["sizes"].get(str(im.size), 0) + 1
            except Exception as e:
                ok = False
                rec[f"error_{p.name}"] = f"{type(e).__name__}: {e}"
        rec["readable"] = ok
        report["categories"][c] = rec
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--fix-layout", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    print(f"检查目录：{root}")
    if not root.is_dir():
        print("目录不存在。MVTec AD 需要先在官网填表下载（见 week2 的说明），解压到这里。")
        return 2

    real = find_dataset_root(root)
    if real != root:
        print(f"发现多套了一层目录：{real}")
        if args.fix_layout:
            for item in real.iterdir():
                shutil.move(str(item), str(root / item.name))
            real.rmdir()
            print("已摊平，重新检查。")
            real = root

    rep = inspect(real)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

    cats = rep["categories"]
    if not cats:
        print("没有识别到任何类别目录（期望 <root>/<category>/train/good）。")
        return 2

    print(f"\n{'类别':<12}{'train/good':>11}{'test 总数':>10}{'ground_truth':>14}  尺寸")
    print("-" * 66)
    bad = []
    for c, r in cats.items():
        sizes = ",".join(r["sizes"].keys()) or "-"
        print(f"{c:<12}{r['train_good']:>11}{r['test_total']:>10}{r['ground_truth']:>14}  {sizes}")
        if r["train_good"] == 0:
            bad.append(f"{c}: 没有 train/good")
        if r["readable"] is False:
            bad.append(f"{c}: 图像无法解码")
        # ground_truth 只覆盖"缺陷图"，test/good 没有掩码 —— 所以要和缺陷图数量比，
        # 而不是和 test 总数比（第一版这里是错的，会在真实数据上误报）。
        n_good = r.get("test_good", 0)
        n_defect = r["test_total"] - n_good
        if r["ground_truth"] and n_defect > 0 and r["ground_truth"] < n_defect:
            bad.append(f"{c}: ground_truth ({r['ground_truth']}) 少于缺陷图数 ({n_defect})，可能缺掩码")

    total_train = sum(r["train_good"] for r in cats.values())
    print("-" * 66)
    print(f"类别数 {len(cats)}；train/good 合计 {total_train} 张")

    pilot = [c for c in ("bottle", "tile", "screw") if c in cats]
    print(f"三个试点类别是否就位：{pilot if len(pilot) == 3 else '缺 ' + str([c for c in ('bottle','tile','screw') if c not in cats])}")

    print(f"\n报告 -> {REPORT}")
    if bad:
        print("\n需要处理的问题：")
        for b in bad:
            print(f"  - {b}")
        return 1
    print("\n结构检查通过，可以进入清单生成与特征提取。")
    print("  下一步：python scripts\\run.py manifests-real")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
