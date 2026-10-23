# 进度看板与成果查阅指南

**读者**：吴源泰 / 导师 · **目的**：一眼看清"哪周做完了、成果在哪、怎么核验" · **更新**：2026-10-11

---

## 0. 先直接回答两个问题

**问：research plan 的十周任务都完成了吗？**
**答：没有。** 目前完成 **W1 全部 + W2 的一部分**，W3–W10 **尚未开始**。具体边界见 §2 的看板。

**问：为什么看不到"每一周的总结文章"？**
**答：因为只有两周真的做过。** 我没有为 W3–W10 补写"看起来像做过"的报告——那正是导师最反感的那种造假。
W3 起的报告会在**那周真正做完之后**生成，结构已经固定在 §4，不会临时变形。

---

## 1. 一句话讲清"计划"和"已完成"的区别

- **计划**是十周的路（Phase 0–9），写在 `RESEARCH_PLAN_MASTER.pdf`。
- **已完成**是"这条路上不依赖数据集的部分 + 一次经授权的模拟预演"。
- 两者的关系：Phase 0 全通；Phase 1 材料齐；Phase 2 卡在数据；Phase 3 用模拟先跑了一遍**设计与失败边界**；Phase 4–9 未动。

---

## 2. 状态看板（W1–W10）

| 周 | 计划任务（Phase） | 状态 | 周报 | 主要证据 |
|---|---|---|---|---|
| **W1** | Phase 0 环境 | ✅ **完成**（除 3 项依赖数据的检查） | `week1/W1_WEEKLY_REPORT.pdf`（2 页） | `week1/environment.md`、`week1/W1_EVIDENCE.md`、`week1/W1_WALKTHROUGH.pdf`、`logs/anchors_latest.json`、`logs/env_*.json` |
| **W2** | Phase 1 后半 + Phase 2 前半 | 🟡 **部分**：Phase 1 材料完成；Phase 2 阻塞；Phase 3 模拟预演完成 | `week2/W2_WEEKLY_REPORT.pdf`（2 页） | `literature/ABSTRACTS_ZH.pdf`、`literature/PAPER_REPORTS_6.pdf`、`logs/w2_sim_gap_pilot.json`、`reports/组会汇报_W2.pptx` |
| W3 | Phase 2 复现 + Phase 3 缺口验证 | ⛔ 未开始（等数据） | 待生成 `week3/` | — |
| W4 | Phase 3 完成 + Phase 4 最小方法 | ⛔ 未开始 | 待生成 `week4/` | — |
| W5 | Phase 4 收尾 + Phase 5 完整设计 | ⛔ 未开始 | 待生成 `week5/` | — |
| W6 | Phase 5 收尾 + Phase 6 分析 | ⛔ 未开始 | 待生成 `week6/` | — |
| W7 | Phase 7 主实验（前半） | ⛔ 未开始 | 待生成 `week7/` | — |
| W8 | Phase 7 收尾 + Phase 8 消融/鲁棒性 | ⛔ 未开始 | 待生成 `week8/` | — |
| W9 | Phase 8 收尾 + Phase 9 写作启动 | ⛔ 未开始 | 待生成 `week9/` | — |
| W10 | Phase 9 论文与可复现清单 | ⛔ 未开始 | 待生成 `week10/` | — |

**卡住 W3 之后的唯一原因**：MVTec AD / AD 2 的官网登记未获批（明细见 `week2/W2_WEEKLY_REPORT.pdf` 第 3 节）。
**允许现在做但不能替代 W3 的**：模拟实验（已做）、权重锚定、`run.json` 模板、阅读笔记。

---

## 3. 已完成的两周：报告在哪、怎么读

### W1（Phase 0 环境）
按这个顺序读，20 分钟能读完：

1. `week1/W1_WEEKLY_REPORT.pdf`（2 页）——**先看这个**：Done 表、Evidence 主表、Blockers、Next。
2. `week1/W1_WALKTHROUGH.pdf`（12 页）——想知道"每一步具体怎么做、踩了什么坑"就看这个，含报错原文。
3. `week1/W1_EVIDENCE.md`——逐项任务的状态、证据路径、以及**明确写了"哪些没做"**。
4. `week1/environment.md`——硬件/软件/锚点/数据的实测清单（每个值都标注了来源与置信度）。
5. 原始证据：`logs/anchors_latest.json`、`logs/env_*.json`、`logs/w1_*.log`、`reports/figures/figure_1~3`。

### W2（Phase 1 材料 + Phase 3 模拟预演）
1. `week2/W2_WEEKLY_REPORT.pdf`（2 页）——同 W1 的结构。
2. `literature/ABSTRACTS_ZH.pdf`（10 页）——六篇必读 + R8–R11 的摘要双语对照与要点。
3. `literature/PAPER_REPORTS_6.pdf`（4 页）——六篇的**中英文结构化报告**（教授要的那种）。
4. `logs/w2_sim_gap_pilot.json` + `reports/figures/figure_4_*.png`——模拟实验的全部数字与图。
5. `reports/组会汇报_W2.pptx`（15 页）——组会用的版本。

---

## 4. 每周报告的统一结构（以后 W3–W10 都长这样）

一份周报**只有两页**，七个固定小节。节名不变、顺序不变，这样你（和导师）可以横向对比任意两周。

| 节 | 写什么 | 导师怎么看出"这周真的做了事" |
|---|---|---|
| **0 一句话结论** | 本周最重要的一件事 + 是否达成 | 有没有"结论"而不是"过程" |
| **1 Done** | 任务 / 计划 h / 实际 h / 产物路径 / 状态 | 产物路径必须存在；h 不能全是整数 |
| **2 Evidence** | **一个主表**（本周最关键的数字）+ 配置 + 数据划分 + 日志路径 + 复现命令 | 主表要有分母；配置要能追到 commit/哈希 |
| **3 Blockers** | 现象 / 已尝试 / 需要什么支持 | "已尝试"是不是列了具体手段 |
| **4 Next** | 3 个任务 + 预期产出 + 预计 h | 是不是可验收的产出，而不是"继续研究" |
| **5 最重要的负面结果** | 本周最让你难受的那个数字/事实 | 有没有勇气写坏的 |
| **6 假设变更** | 一句话；没有就写"无变更" | 假设有没有被数据推动过 |

**Gate 周（Gate 1–5）额外加第 8 节**：Gate 编号与问题、冻结的版本 ID、全部种子与类别、不确定性、最强反例、等资源基线对比、**GO / MODIFY / STOP** 建议。

模板文件：`templates/WEEKLY_REPORT_TEMPLATE.md`（直接复制改名即可）。

---

## 5. 每周成果怎么核验（3 分钟法）

**第一分钟——看结论**：打开当周 `W*_WEEKLY_REPORT.pdf`，只看第 0 节和第 5 节。

**第二分钟——看证据能不能对上**：周报第 2 节列出的每个路径，在仓库里是否真实存在且非空。

**第三分钟——跑一条命令复现**：

```powershell
cd F:\research
python scripts\run.py list            # 看有哪些可复现任务
python scripts\run.py figures         # 出图（应位级复现）
python scripts\sim_gap_pilot.py       # 模拟实验（约 50 秒，数字应与 JSON 一致）
```

如果这三步都对得上，这一周的成果就是**可信的**；对不上，就是我在报告里写错了或者环境变了——两种情况都需要当场指出来。

---

## 6. 文件地图（按周）

| 周 | 周报 | 逐项证据 | 图 / 日志 | 备注 |
|---|---|---|---|---|
| W1 | `week1/W1_WEEKLY_REPORT.pdf` | `week1/W1_EVIDENCE.md`、`week1/W1_WALKTHROUGH.pdf` | `logs/anchors_*`、`logs/env_*`、`logs/w1_*`、`reports/figures/figure_1~3` | 环境与数值契约 |
| W2 | `week2/W2_WEEKLY_REPORT.pdf` | `literature/ABSTRACTS_ZH.pdf`、`literature/PAPER_REPORTS_6.pdf` | `logs/w2_sim_gap_pilot.json`、`reports/figures/figure_4_*` | 阅读 + 模拟 |
| W3–W10 | `week3/` … `week10/`（未创建） | — | — | 按 §4 结构生成 |

**跨周常驻文档**

| 文件 | 作用 |
|---|---|
| `RESEARCH_PLAN_MASTER.pdf` | 总报告：问题/方法/实验设计/进度/证据/风险 |
| `literature/SOURCES.md` | 参考文献的官方来源与哈希 |
| `week1/environment.md` | 环境实测清单（每次换机器都要更新） |
| `logs/anchors_latest.json` | 源码锚点（commit + 树指纹） |
| `README.md` | 目录约定与复现要求 |

---

## 7. W3–W10 的报告会怎么写（占位，不预填结果）

每周报告的骨架一样，差别在于"那一周该填什么"。**只有等该周的工作真的发生，才会生成文件**：

| 周 | 该周报告的核心主表（预期） | 触发条件 |
|---|---|---|
| W3 | 复现表：论文 vs 本次运行（按类别 AUROC）+ 偏离项清单 | MVTec AD 到手 |
| W4 | 分歧 vs 压缩比（真实数据）+ 重校准对照 | W3 完成且 Gate 2 通过 |
| W5 | 本地解决 / 升级比例 + 区间宽度分布 | 最小方法实现 |
| W6 | 复杂度与盈亏平衡点 + 精确树对照 | 分析完成 |
| W7 | 表 1–3 的初版（多数据集、五种子） | Gate 3 通过 |
| W8 | 消融矩阵 + 失败图库 | 主实验完成 |
| W9 | 论文骨架 + 主张—证据对照表 | Gate 4 通过 |
| W10 | 投稿版草稿 + 可复现清单 | 全部冻结 |

---

## 8. 建议的每周工作节奏

| 时点 | 动作 | 产出 |
|---|---|---|
| 周一上午 | 从 §7 的表里确认本周主表是什么 | 一句话目标 |
| 周三晚 | 中期检查：主表能不能填出半张 | 半成品表（避免周五才发现做不完） |
| 周五下午 | 按 §4 七节写周报 | `weekN/W*_WEEKLY_REPORT.pdf` |
| 周五晚 | 用 §5 的 3 分钟法自检一遍 | 自检记录（贴进周报第 2 节） |

**一条纪律**：周报里的每个数字都必须能在 `logs/` 里找到出处；找不到出处的数字，删掉比留着安全。
