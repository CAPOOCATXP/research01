# -*- coding: utf-8 -*-
"""生成组会汇报 PPT（16:9）。

原则
----
* 每一页只讲一件事；数字全部来自本仓库可复现的脚本，页脚标注证据路径。
* 模拟结果一律标红注明"机制模拟，非 MVTec 结果"——不弄虚作假。
"""
from __future__ import annotations

import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt, Emu
from pptx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "组会汇报_W2.pptx"
FIG = ROOT / "reports" / "figures"
SIM = ROOT / "logs" / "w2_sim_gap_pilot.json"

NAVY = RGBColor(0x1F, 0x38, 0x64)
ACCENT = RGBColor(0xC0, 0x00, 0x00)
GRAY = RGBColor(0x40, 0x40, 0x40)
LIGHT = RGBColor(0xF2, 0xF2, 0xF2)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x2E, 0x74, 0x35)

CJK = "微软雅黑"


def set_font(run, size=16, bold=False, color=GRAY, name=CJK):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = color
    f.name = name
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = rPr.makeelement(qn("a:ea"), {})
        rPr.append(ea)
    ea.set("typeface", name)


def textbox(slide, left, top, width, height, text, size=16, bold=False,
            color=GRAY, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.15):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    lines = text.replace("**", "").split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        set_font(p.add_run() if False else p.add_run(), size, bold, color)
        p.runs[0].text = line
    return tb


def bullets(slide, left, top, width, height, items, size=16, color=GRAY, spacing=1.25):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = spacing
        p.space_after = Pt(6)
        lvl = 0
        txt = it
        if isinstance(it, tuple):
            txt, lvl = it
        p.level = lvl
        prefix = "▪ " if lvl == 0 else "– "
        r = p.add_run()
        r.text = prefix + txt.replace("**", "")
        set_font(r, size - (2 if lvl else 0), bold=(lvl == 0 and it is items[0]), color=color)
    return tb


def rect(slide, left, top, width, height, fill, line=None):
    from pptx.enum.shapes import MSO_SHAPE
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top),
                                Inches(width), Inches(height))
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
    sh.shadow.inherit = False
    return sh


def header(slide, title, kicker=None):
    rect(slide, 0, 0, 13.333, 0.92, NAVY)
    textbox(slide, 0.45, 0.16, 12.4, 0.6, title, size=24, bold=True, color=WHITE)
    if kicker:
        textbox(slide, 0.45, 0.95, 12.4, 0.35, kicker, size=11, color=RGBColor(0x80, 0x80, 0x80))
    return slide


def footer(slide, text, page):
    textbox(slide, 0.45, 7.06, 11.4, 0.3, text, size=9, color=RGBColor(0x90, 0x90, 0x90))
    textbox(slide, 12.3, 7.06, 0.6, 0.3, str(page), size=9, color=RGBColor(0x90, 0x90, 0x90),
            align=PP_ALIGN.RIGHT)


def table(slide, left, top, width, headers, rows, col_ratios=None, size=11, row_h=0.32,
          header_fill=NAVY, first_col_bold=False, highlight_rows=None):
    nrows, ncols = len(rows) + 1, len(headers)
    height = row_h * nrows
    shape = slide.shapes.add_table(nrows, ncols, Inches(left), Inches(top),
                                   Inches(width), Inches(height))
    tbl = shape.table
    if col_ratios:
        total = sum(col_ratios)
        for i, r in enumerate(col_ratios):
            tbl.columns[i].width = Emu(int(Inches(width) * r / total))
    for j, h in enumerate(headers):
        c = tbl.cell(0, j)
        c.fill.solid()
        c.fill.fore_color.rgb = header_fill
        c.text = ""
        p = c.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = h
        set_font(run, size, True, WHITE)
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
    for i, row in enumerate(rows, start=1):
        for j, val in enumerate(row):
            c = tbl.cell(i, j)
            c.fill.solid()
            hl = highlight_rows and (i - 1) in highlight_rows
            c.fill.fore_color.rgb = RGBColor(0xFF, 0xF2, 0xF2) if hl else (
                LIGHT if i % 2 == 0 else WHITE)
            c.text = ""
            p = c.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
            run = p.add_run()
            run.text = str(val).replace("**", "")
            set_font(run, size, first_col_bold and j == 0, GRAY)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.margin_top = Emu(20000)
            c.margin_bottom = Emu(20000)
    return tbl


def new_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def build():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    page = 0

    # ---------------------------------------------------------------- 1 封面
    s = new_slide(prs)
    rect(s, 0, 0, 13.333, 7.5, NAVY)
    rect(s, 0, 4.55, 13.333, 0.06, RGBColor(0xC9, 0xA2, 0x27))
    textbox(s, 0.8, 1.55, 11.8, 1.0,
            "当记忆库压缩改变工业报警", size=40, bold=True, color=WHITE)
    textbox(s, 0.8, 2.5, 11.8, 0.9,
            "When Memory Compression Changes Industrial Alarms",
            size=20, color=RGBColor(0xC9, 0xD3, 0xE6))
    textbox(s, 0.8, 3.15, 11.8, 0.6,
            "决策保持的边缘筛查及其在外观变化下的代价", size=18, color=RGBColor(0xC9, 0xD3, 0xE6))
    textbox(s, 0.8, 4.85, 11.8, 0.5,
            "第一阶段汇报 ｜ Phase 0–1 完成 + Phase 3 模拟预演", size=18, bold=True, color=WHITE)
    textbox(s, 0.8, 5.45, 11.8, 1.2,
            "汇报人：吴源泰　　日期：2026-10-11\n"
            "代码与证据：github.com/CAPOOCATXP/research01（commit 6cc5e3d 起）",
            size=13, color=RGBColor(0xC9, 0xD3, 0xE6))

    # ---------------------------------------------------------------- 2 一页看懂
    page += 1
    s = new_slide(prs); header(s, "一页看懂：研究问题与边界")
    textbox(s, 0.55, 1.15, 12.2, 0.5, "问题：库被压缩后，同一阈值下的「报警 / 不报警」还一样吗？",
            size=20, bold=True, color=NAVY)
    bullets(s, 0.55, 1.85, 6.1, 4.6, [
        "固定：编码器、预处理、图像分数聚合、阈值 t",
        "改变：参考库大小（1/5/10/25%）",
        "允许：不确定就「升级查询」，绝不允许把不确定判成正常",
        "度量：二元决策分歧（多报 / 漏报）＋升级代价",
    ], size=15)
    rect(s, 6.95, 1.85, 5.85, 4.5, LIGHT)
    textbox(s, 7.2, 2.0, 5.4, 0.4, "三条研究问题（本阶段可答的部分）", size=14, bold=True, color=NAVY)
    bullets(s, 7.2, 2.45, 5.35, 3.8, [
        "RQ1 压缩在什么条件下改变报警？重校准能救回多少？",
        "RQ2 区间筛查 + 精确回退，能否保持决策一致？",
        "RQ3 逐 cell 半径够不够？不够就是「升级代价」问题",
    ], size=13)
    textbox(s, 0.55, 6.35, 12.2, 0.45,
            "不做：YOLO 剪枝 / 扩散增强 / 多模态融合 / 任何油气现场部署主张",
            size=13, color=ACCENT)
    footer(s, "依据：研究计划 A3（工作方向）、A7（缺口验证）、A8（最小方法）", page)

    # ---------------------------------------------------------------- 3 进度矩阵
    page += 1
    s = new_slide(prs); header(s, "进度：计划书的 Phase 0–9，现在走到哪")
    rows = [
        ["Phase 0 环境", "W1", "完成", "两个 conda 环境、GPU 冒烟、源码锚定、显存上限实测"],
        ["Phase 1 学习", "W1–W2", "完成（笔记待你补）", "六篇精读提纲 + 三角不等式三例 + 五个未决问题"],
        ["Phase 3 缺口验证", "W3–W4", "模拟预演已跑", "MVTec 未获批 → 用机制模拟先验证设计与边界"],
        ["Phase 2 复现", "W2–W3", "阻塞", "需 MVTec AD；环境与 CLI 已就绪"],
        ["Phase 4–9", "W4–W10", "未开始", "依 Phase 2/3 结果而定"],
    ]
    table(s, 0.55, 1.55, 12.2, ["阶段", "计划周", "状态", "已交付 / 说明"], rows,
          col_ratios=[2.1, 1.1, 1.9, 6.2], size=12, row_h=0.62, first_col_bold=True)
    textbox(s, 0.55, 5.15, 12.2, 1.3,
            "关键判断：Phase 0 的产出是「可信的测量能力」，不是「研究结论」。\n"
            "唯一系统性阻塞是 MVTec AD 的官网登记；Phase 3 的模拟预演是在授权下做的替代验证。",
            size=14, color=NAVY)
    footer(s, "证据：week1/W1_EVIDENCE.md、week1/environment.md、logs/anchors_latest.json", page)

    # ---------------------------------------------------------------- 4 环境
    page += 1
    s = new_slide(prs); header(s, "Phase 0-① 环境隔离：两个仓库的依赖互斥",
                              "为什么要两个环境——不是洁癖，是硬冲突")
    rows = [
        ["adedge-patchcore", "3.10.22", "2.2.6", "5.0.0", "2.6.0+cu124", "干净"],
        ["adedge-anomalydino", "3.10.22", "1.26.4", "4.10.0", "2.6.0+cu124", "干净"],
    ]
    table(s, 0.55, 1.6, 12.2, ["conda 环境", "python", "numpy", "opencv", "torch", "pip check"], rows,
          col_ratios=[3.2, 1.6, 1.3, 1.4, 2.4, 1.3], size=12, row_h=0.42, first_col_bold=True)
    bullets(s, 0.55, 2.85, 12.2, 3.0, [
        "冲突一：AnomalyDINO 的 requirements 写死 numpy==1.26（“numpy 2.0 not compatible”）",
        "冲突二：只钉 numpy 不够——opencv-python 5.x 要求 numpy≥2；降 opencv 到 4.14 又把 numpy 拉回 2.2.6",
        "结论：必须**同时**钉 numpy==1.26.4 + opencv-python==4.10.0.84，因此必须两个环境",
        "验收：GPU 冒烟真跑卷积前向+反向（不是只看 is_available）；两个环境各自 pip check 干净",
    ], size=14)
    footer(s, "证据：logs/pip_freeze_*.txt、logs/env_*.json；冒烟峰值 70 MiB，sm_89 正常", page)

    # ---------------------------------------------------------------- 5 源码锚定
    page += 1
    s = new_slide(prs); header(s, "Phase 0-② 源码锚定：git clone 在这台机器上是坏的",
                              "发现 → 绕行 → 建立更硬的锚")
    rows = [
        ["patchcore-inspection", "fcaa92f1…（2023-03-06）", "401", "419fbc57…"],
        ["AnomalyDINO", "b9d1c264…（2025-12-17）", "14", "d23f5352…"],
        ["mvtec 官方评测码", "公开直链（2022-10-13）", "11", "74059be4…"],
    ]
    table(s, 0.55, 1.6, 12.2, ["来源", "commit", "文件数", "树指纹"], rows,
          col_ratios=[3.4, 4.4, 1.4, 3.0], size=12, row_h=0.42, first_col_bold=True)
    bullets(s, 0.55, 3.05, 12.2, 3.2, [
        "现象：git ls-remote 1 秒返回，但 git clone 卡在 pack 传输（试了 5 种参数组合）",
        "绕行：codeload ZIP + 把 commit SHA 钉进 URL，2.3 MB / 1–2 秒完成",
        "更硬的锚：**树指纹**（所有文件 sha256 排序后再哈希）——它校验的是磁盘上真实的字节",
        "副作用：没有 git 历史 → 补丁改用 git diff --no-index，已写进方法学",
    ], size=14)
    footer(s, "证据：logs/anchors_latest.json、scripts/fetch_sources.ps1", page)

    # ---------------------------------------------------------------- 6 显存上限
    page += 1
    s = new_slide(prs); header(s, "Phase 0-③ 显存上限：一次「测法错误」的完整记录",
                              "不 OOM ≠ 没溢出（本周最有价值的方法学发现）")
    rows = [
        ["256×256", "256", "3787 MiB", "46.3%", "未观测到"],
        ["384×384", "192", "6215 MiB", "75.9%", "256（100.1%）"],
        ["512×512", "112", "6435 MiB", "78.6%", "160（110.8%）"],
    ]
    table(s, 0.55, 1.55, 7.4, ["分辨率", "安全 batch", "峰值显存", "占 8187 MiB", "溢出起点"], rows,
          col_ratios=[1.5, 1.3, 1.6, 1.7, 2.0], size=11, row_h=0.42, first_col_bold=True)
    rect(s, 8.25, 1.55, 4.55, 3.0, RGBColor(0xFF, 0xF2, 0xF2))
    textbox(s, 8.45, 1.68, 4.2, 0.35, "错误测法演示", size=13, bold=True, color=ACCENT)
    textbox(s, 8.45, 2.05, 4.2, 2.4,
            "512px / batch 192\n峰值 10835 MiB\n而物理显存只有 8187 MiB\n\n"
            "→ Windows 驱动允许溢出到主机内存\n→ 不报错，只是慢 20 倍\n   （71.7 s vs 3.7 s）",
            size=11, color=GRAY)
    bullets(s, 0.55, 4.75, 12.2, 1.8, [
        "修正后的判据：安全上限 = 峰值 ≤ 80% 物理显存；溢出警戒 = 峰值 > 100%",
        "若按第一版测法设定 batch，第 7 周会得到「在主机内存里跑」的时延，且表面完全看不出来",
    ], size=14)
    footer(s, "证据：logs/w1_vram_limit.json、project/src/w1_vram_limit.py；功耗档 80 W（Default 55 W）", page)

    # ---------------------------------------------------------------- 7 A14-3 手算
    page += 1
    s = new_slide(prs); header(s, "Phase 0-④ A14-3：六向量 / 两中心的边界手算",
                              "L(q) ≤ s_M(q) ≤ U(q)，含阈值并列与升级情形")
    rows = [
        ["q1 (0.5,0)", "0.500", "0", "0.500", "normal", "本地判 normal"],
        ["q2 (0,10)", "9.000", "8.000", "10.000", "alarm", "本地判 alarm"],
        ["q3 (3,0)", "1.000", "1.000", "3.000", "normal", "升级 → normal"],
        ["q4 (0,3)", "2.000", "1.000", "3.000", "alarm", "升级 → alarm"],
        ["q5 (2,1.5)", "1.500", "0.500", "2.500", "normal", "升级（s = t 并列）"],
    ]
    table(s, 0.55, 1.55, 7.6, ["查询", "s_M", "L", "U", "真值", "筛查"], rows,
          col_ratios=[2.0, 1.2, 1.1, 1.1, 1.3, 2.6], size=11, row_h=0.42,
          highlight_rows=[3], first_col_bold=True)
    rect(s, 8.45, 1.55, 4.35, 3.6, LIGHT)
    textbox(s, 8.65, 1.68, 4.0, 0.35, "三角不等式的平实解释", size=13, bold=True, color=NAVY)
    textbox(s, 8.65, 2.08, 4.0, 2.9,
            "d(q,c) ≤ d(q,m) + d(m,c)\n⟹ d(q,c) − d(m,c) ≤ d(q,m)\n\n"
            "cell 内所有 m 都满足\nd(m,c) ≤ r\n\n"
            "⟹ d(q,c) − r 是「到本 cell 任意参考点」的下界\n"
            "⟹ d(q,c) 本身是上界（中心也是参考点）",
            size=11, color=GRAY)
    textbox(s, 0.55, 5.35, 12.2, 1.4,
            "结果：区间违规 0，本地已解决项与真值不一致 0，本地解决 2/5。\n"
            "q4 是关键：它在覆盖球外、真值却是 alarm —— 「离中心近就当正常」这种启发式会误判。",
            size=14, color=NAVY)
    footer(s, "证据：project/src/w1_bounds_example.py、reports/figures/figure_2_*.png", page)

    # ---------------------------------------------------------------- 8 数值契约
    page += 1
    s = new_slide(prs); header(s, "Phase 0-⑤ 数值契约：三条会影响后面所有结论的实测",
                              "这些数字决定了第 4–6 周的证明能用什么、不能用什么")
    rows = [
        ["整块物化 (512×20000×384) float64", "29.3 GiB", "本机 32 GB 内存不可行 → 分块是必需"],
        ["块大小写死 bs=256", "单块 14.6 GiB", "第一次侥幸跑通、第二次 OOM → 结论作废"],
        ["GPU(float32) vs CPU 最近距离", "2.38e-07", "比 float64 的 1e-9 容差大两个数量级"],
    ]
    table(s, 0.55, 1.6, 12.2, ["项目", "实测", "含义"], rows,
          col_ratios=[5.2, 2.0, 5.0], size=12, row_h=0.55, first_col_bold=True)
    bullets(s, 0.55, 3.85, 12.2, 2.6, [
        "分块按内存预算反推（2 GiB → 上限 34），块大小不影响结果（差 0.00e+00），只影响速度",
        "float32 路径的区间保护量必须按路径取（建议 ≥1e-6），否则浮点噪声会被误判成「区间违规」",
        "GPU 加速比两次跑出 7.4× 与 3.2× → 负载相关，第 7 周必须在固定功耗档、空载下重测",
        "教训：一次跑通 ≠ 可复现；靠当时机器状态才成立的数字不能进结论",
    ], size=14)
    footer(s, "证据：project/src/w1_distance_checks.py、logs/w1_distance_checks*.log", page)

    # ---------------------------------------------------------------- 9 阅读
    page += 1
    s = new_slide(prs); header(s, "Phase 1 学习：六篇必读，各自的「可迁移结论」")
    rows = [
        ["R7 覆盖树", "球内含参考点 ⇒ 距离下界", "区间论证的几何地基"],
        ["R1 PatchCore", "核心集 10% + 最近邻 + 最大分数", "基线；压缩动作的来源"],
        ["R2 AnomalyDINO", "冻结 DINOv2，免训练，小样本 SOTA", "第二基线；top-tail 平均需单独审计"],
        ["R3 EfficientAD", "小学学习型检测器，<1 ms 特征提取", "效率对照；小库 ≠ 小模型"],
        ["R4 MVTec AD 2", "老基准饱和；光照变化 + 极小缺陷", "主基准；为什么还要做这个题"],
        ["R6 SPARC", "≤8 张已验证正常图做闭式特征校正", "位移对照；改特征 ≠ 保持一致"],
    ]
    table(s, 0.55, 1.5, 12.2, ["论文", "方法一句话", "对本项目的作用"], rows,
          col_ratios=[2.2, 5.2, 4.8], size=11, row_h=0.52, first_col_bold=True)
    rect(s, 0.55, 5.35, 12.2, 1.45, LIGHT)
    textbox(s, 0.75, 5.45, 11.8, 0.3, "五个未决问题（下周逐个给答案）", size=12, bold=True, color=NAVY)
    textbox(s, 0.75, 5.78, 11.8, 0.95,
            "① 压缩在什么条件下越过阈值  ② 高维下半径有多大  ③ 换 top-k 平均后区间还成立吗\n"
            "④ 200 张校准图的 5% 分位有多准  ⑤ 精确树的复杂度能不能直接比",
            size=11, color=GRAY)
    footer(s, "证据：literature/ABSTRACTS_ZH.pdf（摘要双语对照）、week1/W1_READING_NOTES.md", page)

    # ---------------------------------------------------------------- 10 模拟设计
    page += 1
    s = new_slide(prs); header(s, "Phase 3 预演：MVTec 未获批时的机制模拟",
                              "先验证实验设计与边界，不冒充数据集结论")
    rect(s, 0.55, 1.45, 5.9, 4.5, RGBColor(0xFF, 0xF2, 0xF2))
    textbox(s, 0.75, 1.55, 5.5, 0.35, "声明（必须先说）", size=13, bold=True, color=ACCENT)
    textbox(s, 0.75, 1.92, 5.5, 3.9,
            "这不是 MVTec 结果。\n\n"
            "· 三个「类别」是难度代理，\n  不代表 bottle / tile / screw 的任何数值\n\n"
            "· 不能写进论文的 Table 2\n\n"
            "· 用途：验证实验设计、量级与\n  失效模式，等数据到位后同代码复跑",
            size=12, color=GRAY)
    textbox(s, 6.85, 1.45, 5.9, 0.35, "设定（尽量贴近真实，而不是随手编）", size=13, bold=True, color=NAVY)
    bullets(s, 6.85, 1.85, 5.9, 4.3, [
        "名义维度 384，内在维 24（真实深度特征的有效维数常见 10–40）",
        "全库 20000 个正常 patch；每图 64 个 patch（8×8）",
        "缺陷 = 模式中心 + 单位方向 × 位移；位移按正常最近邻尺度 d0 的倍数给",
        "阈值只用校准集正常图的 95 分位（名义 5% 误报），不读任何缺陷标签",
        "压缩：贪心 k-中心，1/5/10/25%",
        "三档难度：紧凑 / 中等 / 困难（sigma 与位移同时变化）",
    ], size=12)
    footer(s, "证据：scripts/sim_gap_pilot.py、logs/w2_sim_gap_pilot.json（seed=0，可逐位复现）", page)

    # ---------------------------------------------------------------- 11 模拟结果①
    page += 1
    s = new_slide(prs); header(s, "模拟结果 ①：压缩确实改变报警，重校准只能救回一部分",
                              "固定阈值 vs 压缩库单独重校准（分歧 = 多报 + 漏报）")
    sim = json.loads(SIM.read_text(encoding="utf-8"))
    rows = []
    for c in sim["categories"]:
        for k, v in c["compression"].items():
            if abs(v["ratio"] - 0.10) < 1e-9 or abs(v["ratio"] - 0.01) < 1e-9:
                rows.append([c["category"], f"{v['ratio'] * 100:.0f}%", f"{v['k']:,}",
                             f"{v['disagree'] * 100:.1f}%", f"{v['recalibrated']['disagree'] * 100:.1f}%",
                             f"{v['far_normal_fixed_t'] * 100:.0f}%", f"{v['recall_fixed_t'] * 100:.0f}%"])
    table(s, 0.55, 1.5, 12.2, ["难度", "压缩比", "k", "沿用原阈值", "重校准后", "FAR", "召回"], rows,
          col_ratios=[2.4, 1.3, 1.2, 2.0, 1.9, 1.3, 1.3], size=11, row_h=0.4, first_col_bold=True)
    bullets(s, 0.55, 4.35, 12.2, 2.4, [
        "沿用原阈值：分歧 26–72%，几乎全是**多报**（压缩把整个分数分布系统性右移）",
        "压缩库单独重校准后：残余分歧降到 2–19%，但**困难区间仍有 12–19%** → 重校准不能完全解决",
        "全库本身的 FAR 是 7.5–10%（名义 5%）→ 200 张校准图估 5% 分位本就不准，印证 A7 的警告",
        "结论：真正的战场是「重校准之后剩下的那段」——正是区间筛查要处理的部分",
    ], size=13)
    footer(s, "机制模拟，非 MVTec 结果；evidence: logs/w2_sim_gap_pilot.json", page)

    # ---------------------------------------------------------------- 12 模拟结果②
    page += 1
    s = new_slide(prs); header(s, "模拟结果 ②：区间筛查是对的，但代价随难度爆炸",
                              "10% 库、逐 cell 半径；升级率是最关键的资源指标")
    rows = []
    for c in sim["categories"]:
        sc = next(v["screening"] for v in c["compression"].values() if "screening" in v)
        rows.append([c["category"], f"{sc['escalate_rate'] * 100:.0f}%",
                     f"{sc['resolved'] * 100:.0f}%", str(sc["resolved_mismatch"]),
                     f"{sc['radius_mean']:.2f}", f"{sc['radius_p95']:.2f}"])
    table(s, 0.55, 1.5, 9.0, ["难度", "升级率", "本地解决", "不一致", "半径均值", "半径 p95"], rows,
          col_ratios=[2.2, 1.5, 1.7, 1.4, 1.7, 1.7], size=11, row_h=0.46, first_col_bold=True)
    if (FIG / "figure_4_sim_gap_pilot.png").exists():
        # 图宽 7.2 in -> 高约 2.80 in；放在 3.45 处，底边 6.25，不越界
        s.shapes.add_picture(str(FIG / "figure_4_sim_gap_pilot.png"), Inches(3.05), Inches(3.45),
                             width=Inches(7.2))
    textbox(s, 0.55, 6.42, 12.2, 0.5,
            "升级率 56% → 81% → 100%；本地解决的决策与全库**零不一致**。"
            "结论：正确性没问题，问题是半径太大——正是计划书预言的失效模式。",
            size=13, color=NAVY)
    footer(s, "机制模拟，非 MVTec 结果；evidence: logs/w2_sim_gap_pilot.json", page)

    # ---------------------------------------------------------------- 13 结论
    page += 1
    s = new_slide(prs); header(s, "本阶段结论")
    rect(s, 0.55, 1.45, 12.2, 0.1, RGBColor(0xC9, 0xA2, 0x27))
    bullets(s, 0.55, 1.75, 12.2, 4.6, [
        "环境与测量能力已可信：两个环境、GPU 冒烟、源码树指纹、显存安全上限，全部可复现",
        "发现并修正了一个会污染所有时延结论的坑：「不 OOM ≠ 没溢出」，峰值可达物理显存的 175%",
        "数值契约已固定：float64 用 1e-9、float32 路径必须放宽到 1e-6 量级，否则误判区间违规",
        "模拟表明：压缩改变报警是**系统性**的（26–72% 多报），重校准后仍有 2–19% 残余分歧",
        "区间筛查的**正确性成立**（0 不一致），但**单级逐 cell 半径的升级代价过高**（56–100%），"
        "这正是 RQ3 要解决的问题",
    ], size=15, spacing=1.35)
    textbox(s, 0.55, 6.25, 12.2, 0.6,
            "与计划书假设的关系：假设「压缩会改变近阈值报警」在模拟中成立；"
            "但「区间足以减少整库查询」在困难区间**未成立**。",
            size=13, color=ACCENT)
    footer(s, "以上第 1–3 条为实测；第 4–5 条为机制模拟结论，需真实数据复核", page)

    # ---------------------------------------------------------------- 14 卡点
    page += 1
    s = new_slide(prs); header(s, "卡点与需要老师拍板的三件事")
    rows = [
        ["1", "MVTec AD / AD 2 登记", "官网需填表，本机无法自行完成；未绕开登记用第三方镜像",
         "请学校/导师名义登记，或明确授权某个镜像并约定记录方式"],
        ["2", "canonical 复现要不要做", "当前是 py3.10 + torch 2.6；论文是 py3.8 + torch 1.x",
         "是否另开 py3.8 + 原 pin 的 CPU 环境做「保真对照」"],
        ["3", "Gate 2 的 2 点 AUROC 容差口径", "需事先声明，不能事后挑",
         "按类别还是按均值？image AUROC 还是 pixel？"],
    ]
    table(s, 0.55, 1.5, 12.2, ["#", "事项", "现状", "需要"], rows,
          col_ratios=[0.6, 3.0, 4.6, 4.0], size=12, row_h=0.9, first_col_bold=True)
    textbox(s, 0.55, 5.65, 12.2, 1.1,
            "另外：MVTec AD 2 带私有测试服务器、没有可用镜像，必须走官方渠道 —— "
            "这条不解决，Phase 7 的主基准无法开跑。",
            size=13, color=ACCENT)
    footer(s, "详见 week1/W1_WEEKLY_REPORT.pdf 的 Blockers 一节", page)

    # ---------------------------------------------------------------- 15 下周
    page += 1
    s = new_slide(prs); header(s, "下周（Week 2）计划")
    rows = [
        ["1", "真实三角色清单 + 互斥复查", "9 个 CSV + 计数表", "2 h", "数据到位即做"],
        ["2", "PatchCore 最小文档示例", "配置、分数、patch map", "3 h", "需数据"],
        ["3", "AnomalyDINO 1-shot 冒烟", "逐种子日志", "2 h", "需数据"],
        ["4", "权重 sha256（WRN-50 / DINOv2）", "environment.md §3 补全", "1 h", "可先做"],
        ["5", "run.json 模板 + 每次运行自动登记", "模板 + 示例", "2 h", "可先做"],
        ["6", "阅读笔记定稿 + 口述讲解", "3 页笔记", "3 h", "你本人"],
    ]
    table(s, 0.55, 1.5, 12.2, ["#", "任务", "交付物", "预计", "前置条件"], rows,
          col_ratios=[0.6, 4.6, 3.6, 1.2, 2.2], size=12, row_h=0.5, first_col_bold=True)
    textbox(s, 0.55, 5.55, 12.2, 1.2,
            "若数据仍未到位：先做 4、5 两项，并把 Phase 3 的模拟扩展到「多级半径」与「d_eff 扫描」，"
            "用模拟把 RQ3 的边界先摸清。",
            size=13, color=NAVY)
    footer(s, "汇报结束，请指正", page)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT))
    print(f"OK -> {OUT}  slides={len(prs.slides.__iter__.__self__._sldIdLst)}")
    print(f"共 {page + 1} 页")


if __name__ == "__main__":
    build()
