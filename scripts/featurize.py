# -*- coding: utf-8 -*-
"""把 patch 特征一次性算好并缓存，供 Phase 4–9 反复使用。

为什么必须先做这一步
--------------------
Phase 4–9 要在同一批特征上做几十次实验（不同参考数量、不同种子、不同半径结构、
精确树对照……）。每次重新跑 WRN-50 前向，一类就要几十秒到几分钟，加起来会把
实验时间全耗在重复计算上。缓存之后，后续实验只做"距离与决策"，单次几秒。

缓存内容（每类一个 .npz）
------------------------
    paths     图像路径（str 数组）
    split     train_good / test_good / test_defect
    roles     仅 train_good 有：reference_fit / development / calibration / unused
    feats     (N_images, P, C) float32 —— P=784 (28x28), C=1536 (layer2+layer3)
    meta      json 字符串：encoder、resize、imagesize、pool、torch 版本、耗时

设计约束
--------
* 特征与推理时必须完全一致（同一 encoder / 同一预处理 / 同一池化），否则区间论证失效。
* 缓存带"指纹"：encoder + 预处理 + 分辨率 + 池化方式，任一变化即视为不同缓存。
* 不写入 data/，写入 cache/features/（已被 .gitignore 排除）。

用法
----
    python scripts/featurize.py                       # 三个试点类别
    python scripts/featurize.py --categories bottle   # 单类
    python scripts/featurize.py --force               # 重新计算
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
import torchvision
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "mvtec_ad"
CACHE = ROOT / "cache" / "features"
MAN = ROOT / "manifests"

RESIZE, IMAGESIZE, POOL = 256, 224, 3


class Paths(Dataset):
    def __init__(self, paths):
        self.paths = paths
        self.tf = transforms.Compose([
            transforms.Resize(RESIZE, interpolation=transforms.InterpolationMode.BILINEAR),
            transforms.CenterCrop(IMAGESIZE),
            transforms.ToTensor(),
        ])

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        with Image.open(self.paths[i]) as im:
            return self.tf(im.convert("RGB")), i


def build_embedder(device):
    model = torchvision.models.wide_resnet50_2(
        weights=torchvision.models.Wide_ResNet50_2_Weights.IMAGENET1K_V1).eval()
    for p in model.parameters():
        p.requires_grad_(False)
    model = model.to(device)
    store = {}
    model.layer2.register_forward_hook(lambda m, i, o: store.__setitem__("l2", o))
    model.layer3.register_forward_hook(lambda m, i, o: store.__setitem__("l3", o))

    def embed(batch):
        with torch.no_grad():
            model(batch.to(device))
            l2, l3 = store["l2"], store["l3"]
            l3 = F.interpolate(l3, size=l2.shape[-2:], mode="bilinear", align_corners=False)
            f = torch.cat([l2, l3], dim=1)
            f = F.avg_pool2d(f, POOL, 1, 1)
            B, C, H, W = f.shape
            return f.permute(0, 2, 3, 1).reshape(B, H * W, C).cpu()
    return embed, model


def fingerprint() -> str:
    desc = {
        "encoder": "wide_resnet50_2:IMAGENET1K_V1",
        "layers": ["layer2", "layer3"],
        "resize": RESIZE, "imagesize": IMAGESIZE, "pool": POOL,
        "interp": "bilinear", "dtype": "float32",
        "torch": torch.__version__,
    }
    return hashlib.sha256(json.dumps(desc, sort_keys=True).encode()).hexdigest()[:16], desc


def read_roles(cat):
    """把 manifests 里的三个角色读成 {relative_path: role}。"""
    out = {}
    for role in ("reference_fit", "development", "calibration"):
        f = MAN / f"{cat}_{role}.csv"
        if not f.exists():
            continue
        with open(f, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                out[row["relative_path"].replace("\\", "/")] = role
    return out


def collect(cat):
    cat_dir = DATA / cat
    items = []
    roles = read_roles(cat)
    for p in sorted((cat_dir / "train" / "good").glob("*.png")):
        rel = f"{cat}/train/good/{p.name}"
        items.append((str(p), "train_good", roles.get(rel, "unused")))
    for p in sorted((cat_dir / "test" / "good").glob("*.png")):
        items.append((str(p), "test_good", "-"))
    for p in sorted((cat_dir / "test").glob("*/*.png")):
        if p.parent.name != "good":
            items.append((str(p), "test_defect", "-"))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--categories", nargs="+", default=["bottle", "tile", "screw"])
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    fp, desc = fingerprint()
    print(f"device={device}  fingerprint={fp}")
    print(json.dumps(desc, ensure_ascii=False))
    CACHE.mkdir(parents=True, exist_ok=True)
    embed, _ = build_embedder(device)

    for cat in args.categories:
        out = CACHE / f"{cat}_{fp}.npz"
        if out.exists() and not args.force:
            print(f"[skip] {out.name}")
            continue
        t0 = time.perf_counter()
        items = collect(cat)
        ds = Paths([p for p, _, _ in items])
        dl = DataLoader(ds, batch_size=args.batch, shuffle=False, num_workers=0)
        chunks = [embed(x) for x, _ in dl]
        feats = torch.cat(chunks, dim=0).numpy().astype(np.float32)
        meta = dict(desc, category=cat, n_images=len(items),
                    split_counts={s: sum(1 for _, x, _ in items if x == s)
                                  for s in ("train_good", "test_good", "test_defect")},
                    role_counts={r: sum(1 for _, _, x in items if x == r)
                                 for r in ("reference_fit", "development", "calibration", "unused", "-")},
                    patches_per_image=int(feats.shape[1]), dim=int(feats.shape[2]),
                    fingerprint=fp, seconds=round(time.perf_counter() - t0, 1))
        np.savez_compressed(out,
                            paths=np.array([p for p, _, _ in items]),
                            split=np.array([s for _, s, _ in items]),
                            roles=np.array([r for _, _, r in items]),
                            feats=feats, meta=np.array(json.dumps(meta, ensure_ascii=False)))
        print(f"[ok] {cat:<10} {len(items):>4} 图  {feats.shape}  "
              f"{out.stat().st_size / 2**20:6.1f} MB  {meta['seconds']}s")
        print(f"     roles={meta['role_counts']}")

    print("\n缓存目录 ->", CACHE)


if __name__ == "__main__":
    main()
