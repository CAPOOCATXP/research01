# -*- coding: utf-8 -*-
"""把 literature/pdf 下的论文抽取成纯文本，便于翻译与引用核查。

用法
----
    python scripts/lit_extract.py                # 每篇抽前 3 页
    python scripts/lit_extract.py --pages 0 12   # 指定页范围（0 基）
    python scripts/lit_extract.py --all          # 全文抽取

输出
----
    literature/txt/<论文名>.txt
    literature/txt/_index.json   每篇的页数、抽取字符数、疑似摘要起点

设计说明：抽取文本只用于**阅读与翻译**，不改变任何证据链；
PDF 本体与抽取文本都不进 git（见 .gitignore），随时可用脚本重建。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "literature" / "pdf"
TXT_DIR = ROOT / "literature" / "txt"


def extract(path: Path, pages: list[int] | None) -> tuple[str, int]:
    doc = pymupdf.open(path)
    n = doc.page_count
    idxs = range(n) if pages is None else [p for p in pages if 0 <= p < n]
    parts = []
    for i in idxs:
        parts.append(f"\n<<< PAGE {i + 1}/{n} >>>\n")
        parts.append(doc[i].get_text("text"))
    doc.close()
    return "".join(parts), n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", nargs=2, type=int, default=None, metavar=("START", "END"))
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    TXT_DIR.mkdir(parents=True, exist_ok=True)
    index = []
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"没有找到 PDF：{PDF_DIR}")
        return 2

    for p in pdfs:
        doc = pymupdf.open(p)
        n = doc.page_count
        doc.close()
        if args.all:
            pages = None
        elif args.pages:
            pages = list(range(args.pages[0], min(args.pages[1], n)))
        else:
            pages = list(range(min(3, n)))
        text, npages = extract(p, pages)
        out = TXT_DIR / (p.stem + ".txt")
        out.write_text(text, encoding="utf-8")
        # 粗略定位摘要：找 "Abstract" 之后的 200 字
        low = text.lower()
        k = low.find("abstract")
        snippet = ""
        if k >= 0:
            snippet = " ".join(text[k:k + 260].split())
        index.append({
            "file": p.name, "pages_total": npages,
            "pages_extracted": (len(pages) if pages is not None else npages),
            "chars": len(text), "txt": out.name, "abstract_head": snippet,
        })
        print(f"{p.name:54s} 抽 {len(pages) if pages is not None else npages:>3}/{npages:>3} 页  {len(text):>8,} 字符")

    (TXT_DIR / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n索引 -> {TXT_DIR / '_index.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
