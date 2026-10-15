# -*- coding: utf-8 -*-
"""为 literature/ 生成来源登记：literature/SOURCES.md 与 literature/sources.json。

设计原则（与 fetch_sources.ps1 同一套纪律）
-------------------------------------------
* **只用官方开放获取版本**：CVF Open Access、PMLR、arXiv、Springer OA；不使用任何盗版镜像。
* **每个文件留三样证据**：字节数、sha256、页数（页数同时充当"文件能否打开"的最廉价校验）。
* **PDF 本体不进 git**（见 .gitignore）：我们提交的是来源清单，不是出版方的文件；
  任何时候都能用 scripts/fetch_literature.ps1 重新拉回来。
* 引用信息以出版方为准；arXiv 预印本与正式版本可能不同，两个链接都记。

用法
----
    python scripts/lit_manifest.py
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "literature" / "pdf"
OUT_MD = ROOT / "literature" / "SOURCES.md"
OUT_JSON = ROOT / "literature" / "sources.json"

# pages_override：这两个 arXiv PDF 用了压缩对象流，正则数不出页数，
# 页数由 PDF 渲染器（pdfium）实测确认。
PAPERS = [
    dict(ref="R1", file="R1_patchcore_CVPR2022.pdf",
         title="Towards Total Recall in Industrial Anomaly Detection",
         authors="Karsten Roth, Latha Pemula, Joaquin Zepeda, Bernhard Schölkopf, Thomas Brox, Peter Gehler",
         venue="CVPR 2022, pp. 14318–14328", doi="10.1109/CVPR52688.2022.01392",
         landing="https://openaccess.thecvf.com/content/CVPR2022/html/Roth_Towards_Total_Recall_in_Industrial_Anomaly_Detection_CVPR_2022_paper.html",
         used="https://openaccess.thecvf.com/content/CVPR2022/papers/Roth_Towards_Total_Recall_in_Industrial_Anomaly_Detection_CVPR_2022_paper.pdf",
         access="CVF Open Access（免费）", role="A5 必读 #2；基线代码仓库的上游论文"),
    dict(ref="R2", file="R2_anomalydino_WACV2025.pdf",
         title="AnomalyDINO: Boosting Patch-based Few-shot Anomaly Detection with DINOv2",
         authors="Simon Damm, Mike Laszkiewicz, Johannes Lederer, Asja Fischer",
         venue="WACV 2025", doi="",
         landing="https://openaccess.thecvf.com/content/WACV2025/html/Damm_AnomalyDINO_Boosting_Patch-Based_Few-Shot_Anomaly_Detection_with_DINOv2_WACV_2025_paper.html",
         used="https://openaccess.thecvf.com/content/WACV2025/papers/Damm_AnomalyDINO_Boosting_Patch-Based_Few-Shot_Anomaly_Detection_with_DINOv2_WACV_2025_paper.pdf",
         access="CVF Open Access（免费）", role="A5 必读 #3；第二个基线仓库的上游论文"),
    dict(ref="R3", file="R3_efficientad_WACV2024.pdf",
         title="EfficientAD: Accurate Visual Anomaly Detection at Millisecond-Level Latencies",
         authors="Kilian Batzner, Lars Heckler, Rebecca König",
         venue="WACV 2024, pp. 128–138", doi="10.1109/WACV57701.2024.00020",
         landing="https://openaccess.thecvf.com/content/WACV2024/html/Batzner_EfficientAD_Accurate_Visual_Anomaly_Detection_at_Millisecond-Level_Latencies_WACV_2024_paper.html",
         used="https://openaccess.thecvf.com/content/WACV2024/papers/Batzner_EfficientAD_Accurate_Visual_Anomaly_Detection_at_Millisecond-Level_Latencies_WACV_2024_paper.pdf",
         alt="https://www.mvtec.com/fileadmin/Redaktion/mvtec.com/company/research/Batzner_accurate_visual_anomaly_detection_at_millisecond_level_latencies_2024.pdf",
         access="CVF Open Access（免费）；作者方 MVTec 亦提供副本", role="A5 必读 #4；效率对照基线"),
    dict(ref="R4", file="R4_mvtec_ad2_IJCV2026.pdf",
         title="The MVTec AD 2 Dataset: Advanced Scenarios for Unsupervised Anomaly Detection",
         authors="Lars Heckler-Kram, Jan-Hendrik Neudeck, Ulla Scheler, Rebecca König, Carsten Steger",
         venue="International Journal of Computer Vision (IJCV) 134(4), 2026", doi="10.1007/s11263-026-02743-0",
         landing="https://link.springer.com/article/10.1007/s11263-026-02743-0",
         used="https://link.springer.com/content/pdf/10.1007/s11263-026-02743-0.pdf",
         note="Springer 对脚本下载返回 HTML cookie 墙；必须用 curl 带 Referer 与 cookie 会话才能取到 PDF",
         access="Springer（开放获取）", role="A5 必读 #5；主基准数据集的论文（数据本身仍需填表登记）"),
    dict(ref="R6", file="R6_sparc_arXiv2608.18585.pdf", pages_override=36,
         title="SPARC: Subspace Position-Aware Robust Few-Shot Calibration for Distribution-Shifted Industrial Anomaly Detection",
         authors="Seokhee Han, Seungjun Chu, Mateusz Nowak, Peter Chin",
         venue="arXiv:2608.18585, 2026", doi="10.48550/arXiv.2608.18585",
         landing="https://arxiv.org/abs/2608.18585",
         used="https://arxiv.org/pdf/2608.18585",
         access="arXiv（CC BY 4.0，以 arXiv 页面标注为准）", role="A5 必读 #6；位移场景对照方法（计划未确认到官方代码仓）"),
    dict(ref="R7", file="R7_cover_trees_ICML2006.pdf",
         title="Cover Trees for Nearest Neighbor",
         authors="Alina Beygelzimer, Sham Kakade, John Langford",
         venue="ICML 2006, pp. 97–104", doi="10.1145/1143844.1143857",
         landing="https://dl.acm.org/doi/10.1145/1143844.1143857",
         used="https://hunch.net/~jl/projects/cover_tree/paper/paper.pdf",
         note="ACM DL 版本需订阅；此处用共同作者 John Langford 项目主页上的作者自存版",
         access="作者自存版（免费）；正式版在 ACM DL", role="A5 必读 #1；区间论证的度量几何来源"),
    dict(ref="R8", file="R8_calibration_preserving_pruning_arXiv2608.23744.pdf", pages_override=14,
         title="Calibration-Preserving Pruning: Compression as a Reliability Contract",
         authors="Ibne Farabi Shihab, Adria Binte Habib, Anuj Sharma",
         venue="arXiv:2608.23744, 2026-08-24", doi="10.48550/arXiv.2608.23744",
         landing="https://arxiv.org/abs/2608.23744",
         used="https://arxiv.org/pdf/2608.23744",
         access="arXiv（CC BY 4.0）", role="A4 最接近工作之一：压缩与可靠性的关系（本项目要证明的是「阈值决策一致性」，与其「符合预测集」不同）"),
    dict(ref="R9", file="R9_memory_pollution_MDPI2026.pdf", status="PENDING_BROWSER",
         title="Memory Pollution in Multi-Product Visual Anomaly Detection: Diagnosis and Mitigation",
         authors="Sergio Villanueva López, Emilio Soria-Olivas, Manuel Sánchez-Montañés",
         venue="Machine Learning and Knowledge Extraction (MDPI), 8(7):219, 2026-07-22", doi="10.3390/make8070219",
         landing="https://www.mdpi.com/2504-4990/8/7/219",
         used="https://www.mdpi.com/2504-4990/8/7/219/pdf",
         note="MDPI 对一切脚本化请求返回 HTTP 403（Invoke-WebRequest / curl / 抓取工具都试过）。"
              "元数据经 Crossref API（api.crossref.org/works/10.3390/make8070219）核实；PDF 需人工用浏览器另存",
         access="MDPI 开放获取（CC BY 4.0）", role="A4 最接近工作之一：压缩检索 + 路由回退（其 WNR 指标与「记忆污染」正是本项目要区分的现象）"),
    dict(ref="R10", file="R10_elkin_kurlin_compressed_cover_tree_ICML2023.pdf",
         title="A new near-linear time algorithm for k-nearest neighbor search using a compressed cover tree",
         authors="Yury Elkin, Vitaliy Kurlin",
         venue="ICML 2023, PMLR 202:9267–9311", doi="",
         landing="https://proceedings.mlr.press/v202/elkin23a.html",
         used="https://proceedings.mlr.press/v202/elkin23a/elkin23a.pdf",
         access="PMLR 开放获取（免费）", role="A5 指出的 R7 证明缺口之修正；第 6 周讨论树的复杂度假设时必须引用"),
    dict(ref="R11", file="R11_fastref_CVPR2026.pdf",
         title="FastRef: Fast Prototype Refinement for Few-shot Industrial Anomaly Detection",
         authors="Yufei Li, Long Tian, Yuyang Dai, Wenchao Chen, Liang Bao, Xiyang Liu",
         venue="CVPR 2026, pp. 43040–43049", doi="",
         landing="https://openaccess.thecvf.com/content/CVPR2026/html/Li_FastRef_Fast_Prototype_Refinement_for_Few-shot_Industrial_Anomaly_Detection_CVPR_2026_paper.html",
         used="https://openaccess.thecvf.com/content/CVPR2026/papers/Li_FastRef_Fast_Prototype_Refinement_for_Few-shot_Industrial_Anomaly_Detection_CVPR_2026_paper.pdf",
         alt="https://arxiv.org/pdf/2506.21398（arXiv 版本，页数与排版不同）",
         access="CVF Open Access（免费）", role="A10 提到的质量对照；注意其查询自适应会改变固定参考，不能塞进区间证明"),
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def count_pages(p: Path):
    raw = p.read_bytes().decode("latin-1", errors="ignore")
    n = len(re.findall(r"/Type\s*/Page[^s]", raw))
    if n:
        return n, "正则 /Type /Page"
    m = re.findall(r"/Count\s+(\d+)", raw)
    if m:
        return max(int(x) for x in m), "正则 /Count（对象流）"
    return None, "无法用正则判定"


def main() -> int:
    rows, missing = [], []
    for meta in PAPERS:
        rec = dict(meta)
        f = PDF_DIR / meta["file"]
        if f.exists():
            rec["bytes"] = f.stat().st_size
            rec["sha256"] = sha256_file(f)
            n, how = count_pages(f)
            if meta.get("pages_override"):
                rec["pages"] = meta["pages_override"]
                rec["pages_source"] = "PDF 渲染器（pdfium）实测"
            else:
                rec["pages"] = n
                rec["pages_source"] = how
            rec["status"] = "OK"
        else:
            rec["bytes"] = rec["sha256"] = rec["pages"] = None
            rec["status"] = meta.get("status", "MISSING")
            missing.append(meta["ref"])
        rows.append(rec)

    OUT_JSON.write_text(json.dumps(
        {"generated_by": "scripts/lit_manifest.py",
         "note": "PDF 本体不入 git；本清单记录官方来源与哈希，可用 scripts/fetch_literature.ps1 复原",
         "papers": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# A5 阅读清单来源登记", "",
          "> 由 `scripts/lit_manifest.py` 生成。**只登记官方开放获取来源**（CVF Open Access / PMLR / arXiv / Springer OA / 作者自存版），不使用任何盗版镜像。",
          "> PDF 本体不进 git（见 `.gitignore`），用 `powershell -ExecutionPolicy Bypass -File scripts\\fetch_literature.ps1` 复原。",
          "",
          "| 编号 | 论文 | 作者 | 出处 | 本地文件 | 页数 | 字节 | sha256 | 获取状态 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        st = "✅ 已下载" if r["status"] == "OK" else "⬜ **需浏览器另存**" if r["status"] == "PENDING_BROWSER" else "❌ 缺失"
        size = f"{r['bytes']:,}" if r["bytes"] else "—"
        sh = f"`{r['sha256'][:16]}…`" if r["sha256"] else "—"
        md.append(f"| **{r['ref']}** | {r['title']} | {r['authors']} | {r['venue']} | `{r['file']}` | "
                  f"{r['pages'] if r['pages'] else '—'} | {size} | {sh} | {st} |")

    md += ["", "## 逐篇详情与获取通道", ""]
    for r in rows:
        md.append(f"### {r['ref']} · {r['title']}")
        md.append("")
        md.append(f"- **作者**：{r['authors']}")
        md.append(f"- **出处**：{r['venue']}" + (f" · DOI `{r['doi']}`" if r.get("doi") else ""))
        md.append(f"- **正式页面**：{r['landing']}")
        md.append(f"- **本次实际使用的下载地址**：{r['used']}")
        if r.get("alt"):
            md.append(f"- **备用地址**：{r['alt']}")
        md.append(f"- **获取方式/许可**：{r['access']}")
        if r.get("note"):
            md.append(f"- **注意**：{r['note']}")
        if r["status"] == "OK":
            md.append(f"- **本地留证**：`{r['file']}` · {r['bytes']:,} 字节 · {r['pages']} 页（{r['pages_source']}）· "
                      f"sha256 `{r['sha256']}`")
        md.append(f"- **在本项目里的作用**：{r['role']}")
        md.append("")

    if missing:
        md += ["## 待补", "",
               f"以下编号尚未取得 PDF：{'、'.join(missing)}。"
               "R9 需人工在浏览器里打开 https://www.mdpi.com/2504-4990/8/7/219 并另存为 "
               "`literature/pdf/R9_memory_pollution_MDPI2026.pdf`（MDPI 拒绝一切脚本访问）。", ""]

    md += ["## 为什么不把 PDF 提交进仓库", "",
           "1. 版权：即使多数是开放获取，把这些文件重新分发到公开仓库并不必要；",
           "2. 体积：本篇合计约 36 MB，且与仓库内容无关；",
           "3. 可复现：有了来源 URL + sha256，任何人在任何机器上都能重新取回并校验（`fetch_literature.ps1` 会打印同一套哈希）。", ""]

    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    ok = sum(1 for r in rows if r["status"] == "OK")
    print(f"已登记 {len(rows)} 篇（成功下载 {ok} 篇）")
    print(f"  {OUT_MD}")
    print(f"  {OUT_JSON}")
    if missing:
        print(f"  待补：{', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
