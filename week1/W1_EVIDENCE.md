# 第一周工作说明（Week 1 + A14 立即任务）

> 项目：When Memory Compression Changes Industrial Alarms（暂定名）· Phase 0
> 执行人：吴源泰 · 时间：2026-10-07 ~ 2026-10-10 · 主机：`laptop-csp8hpp8`
> 项目根：`F:\research`
> 本文件说明**每个任务具体做了什么、证据在哪、结论是什么、哪些还没做**。周报另见 `W1_WEEKLY_REPORT.pdf`。

---

## 0. 状态总表

| # | 任务（来源） | 状态 | 证据 |
|---|---|---|---|
| 1 | 项目 README + 硬件/数据清单（A14-1、Phase 0） | ✅ 完成 | `README.md`、`week1\environment.md` |
| 2 | 读 PatchCore 方法并在允许图像上跑最小示例（A14-2） | ⛔ **受阻**：数据未获批；已执行 A14 指定的替代路径 | `project\src\w1_distance_checks.py`、`logs\w1_distance_checks.log` |
| 3 | 6 向量 / 2 中心手算 `L, s_M, U`（含阈值并列与升级情形）（A14-3） | ✅ 完成，5 种边界情形全覆盖 | `project\src\w1_bounds_example.py`（下方 §3 有全部数字） |
| 4 | 三个试点类别的三种角色清单 + 互斥检查（A14-4） | ⚠️ **逻辑已验证，真实清单待数据** | `scripts\make_manifests.py`、`logs\w1_manifests_selftest.log`、`logs\w1_manifests_real.log` |
| 5 | 一页首次报告（A14-5） | ✅ | `week1\W1_WEEKLY_REPORT.pdf` |
| 6 | 环境隔离（Phase 0） | ✅ 两个 conda 环境 + GPU 冒烟通过 | `logs\env_*.json`、`logs\pip_freeze_*.txt`、§1 |
| 7 | 目录骨架（Phase 0） | ✅（骨架此前已建，本次补齐 `scripts\`、`archive\sources\`、`logs\` 内容） | `F:\research\` |
| 8 | 仓库与权重锚定（Phase 0） | ✅ 三个源按 commit 锚定 | `logs\anchors_latest.json`、`archive\sources\`、§2 |
| 9 | 一次实测计时 + 精确距离核对（Phase 0） | ✅ | `logs\w1_distance_checks.log`、`logs\w1_vram_limit.json`、§4 |
| 10 | 一次真实图像/掩码显示、按划分列出图像与标签（A6 健全性检查） | ⛔ 受阻：无数据 | — |
| 11 | 显存上限与功耗档实测（A6/Phase 0 必填项） | ✅ 且发现"溢出但不 OOM"陷阱 | §5 |
| 12 | 阅读 R7 / R1 并写 3 页笔记（Week 1 Day 3） | ⚠️ 提供了可核对的部分（三个三角不等式例子 + 要点提纲 + 5 个问题）；**原文精读仍需你本人完成** | `week1\W1_READING_NOTES.md` |

一句话：**Phase 0 里所有不依赖数据集的部分都做完了并且留下了可复现证据；唯一系统性阻塞是 MVTec AD/AD 2 的数据访问（官网要求填表，尚未获批），我没有绕开登记去用第三方镜像。**

---

## 1. 环境隔离（任务 6）

**做了什么**
1. 查了 `conda config --show envs_dirs`，发现首个 envs 目录是 `C:\Users\yuantai\.conda\envs`，不是 `E:\anaconda\envs`。
2. 建 `adedge-patchcore`（py3.10.22）并安装：torch **2.6.0+cu124**、torchvision 0.21.0、faiss-cpu 1.15.1、
   numpy 2.2.6、scipy、scikit-learn、opencv-python、pillow、matplotlib、pandas、tqdm、
   `pretrainedmodels`、`scikit-image`、`click`，外加官方 requirements 里**漏写的 `timm`**。
3. 用 `check_env.ps1` 做验收（不是"装上了"，而是"跑起来了"）：sm_89 上卷积前向+反向 `OK`，
   峰值 70 MiB，无 `no kernel image` 问题；导出 `pip freeze` 与 `pip check`。
4. 建第二个环境 `adedge-anomalydino` 并按 AnomalyDINO 的 pin 降到 `numpy==1.26.4`。

**为什么必须两个环境（实测理由，不是洁癖）**
1. AnomalyDINO `requirements.txt` 原文：`numpy==1.26 # numpy 2.0 not compatible at the moment`；
   PatchCore 侧实测 numpy 2.2.6 正常 → 两个 pin 无法共存。
2. **只钉 numpy 不够**：降 numpy 到 1.26.4 后 `pip check` 立刻报
   `opencv-python 5.0.0.93 requires numpy>=2`；再把 opencv 降到 4.14，pip 又**把 numpy 拉回 2.2.6**。
   只有**同时钉住** `numpy==1.26.4` + `opencv-python==4.10.0.84` 才得到一致解。
   → 依赖隔离要按"互相牵制的包组"做，不是按单个包做。
3. 最终状态：两个环境各自 `pip check` = **No broken requirements found**，且都通过 GPU 冒烟：

| 环境 | numpy | opencv | torch | GPU 冒烟 | freeze sha256 |
|---|---|---|---|---|---|
| `adedge-patchcore` | 2.2.6 | 5.0.0 | 2.6.0+cu124 | OK（70 MiB） | `70612E24…DAB6` |
| `adedge-anomalydino` | **1.26.4** | **4.10.0.84** | 2.6.0+cu124 | OK（70 MiB） | `2E1C8823…9A8E` |

**两个真实依赖缺口**（官方仓库自己没写全）
- PatchCore：`src/patchcore/backbones.py` 第 1 行 `import timm`，但 `requirements.txt` 里没有 timm。
- AnomalyDINO：`run_anomalydino.py` 第 4 行 `import yaml`，需要 `PyYAML`。

**偏离项（必须写进报告，不能当作"复现成功"）**
- Python 3.10（论文用 3.8）；torch 2.6（论文时代 1.x）。原因：本机是 sm_89 (Ada)，只有 CUDA ≥ 11.8
  的构建才带对应 kernel，即 torch ≥ 2.0 的 cu118+ wheel。老 pin 的 cu111 wheel 在 4070 上会直接报
  `no kernel image is available`。
- 结论：本环境产出的是"**现代环境下的自研参考实现**"，**不是**论文的 canonical 复现。
  canonical 复现若要做，需要另开 py3.8 + 原 pin 的 CPU 环境（Week 2 再决定）。

**证据**：`logs\env_adedge-patchcore_20261010-102504.json`、
`logs\pip_freeze_adedge-patchcore_20261010-102504.txt`（sha256 `70612E24...DAB6`）、`logs\pip_check_*.txt`。

---

## 2. 目录骨架与仓库锚定（任务 7、8）

### 2.1 骨架
`F:\research\` 下已有：`repos\ data\ cache\{weights,features,torch,hf} manifests\ configs\ runs\ logs\ scripts\ reports\ archive\ tmp\ project\{src,configs,patches}\ week1\`，
根目录已 `git init`（main，尚无 commit），`README.md` 写明六条路径约定（repos/data 只读等），`.gitignore` 排除
`.idea/ data/ cache/ runs/ archive/ repos/ tmp/`。

### 2.2 锚定方式被迫改变（重要）
**实测**：`git ls-remote` 正常（<1 s，返回 `fcaa92f1...`），但 **`git clone` 在 pack 传输阶段阻塞**——
试过默认参数、`--depth 1`、`http.version=HTTP/1.1`、`credential.helper=`、`GIT_TERMINAL_PROMPT=0`，
均在 5 分钟无输出后放弃。`Invoke-WebRequest` 走 .NET/schannel 通道下载 **codeload ZIP 则 1–2 s 完成**。

**因此改用：ZIP 快照 + commit SHA 钉在 URL 里 + 树指纹**。已获取并锚定：

| 名称 | commit / 来源 | 上游日期 | 归档 sha256（前缀） | 文件数 | 树指纹（前缀） |
|---|---|---|---|---|---|
| patchcore-inspection | `fcaa92f124fb1ad74a7acf56726decd4b27cbcad` | 2023-03-06 | `7FDBA8B2` | 401 | `419fbc57` |
| AnomalyDINO | `b9d1c2648e3a5247437d4d953d907a8f3d994457` | 2025-12-17 | `975643A4` | 14 | `d23f5352` |
| mvtec_ad_evaluation（官方评测码，公开直链） | — | 2022-10-13 | `DFCDA7D6` | 11 | `74059be4` |

- **树指纹** = sha256 over 排序后的「相对路径|文件sha256」列表。它比 commit 号更硬：重取源码后比对指纹，
  就能确认用的还是不是同一个 commit。完整值见 `logs\anchors_latest.json`。
- 副作用：ZIP 快照**没有 git 历史**，所以补丁不能用 `git diff` 生成，改用
  `git diff --no-index 原文件 改后文件 > project\patches\xxx.patch`（该命令不需要仓库）。
- 关键文件自检全部存在：`requirements.txt`、`bin\run_patchcore.py`、`run_anomalydino.py`、`src\detection.py`。
- 两个官方 CLI 都能在本环境加载并打印参数表（`--help` 通过）。
- 权重 sha256：⬜ 尚无权重文件（PatchCore 的 WRN-50 权重要到 Week 2 跑基线时才会下载，届时用
  `Get-FileHash` 补录；DINOv2 ViT-S/14 同理）。

**证据**：`logs\anchors_20261010-101914.md`、`logs\anchors_latest.json`、`archive\sources\`。

---

## 3. A14-3：六向量 / 两中心的边界手算（任务 3）——本周最核心的数学动作

**构造**（二维，便于手算；`alarm ⇔ s_M(q) > t`，严格大于）

```
M = [ (0,0), (1,0), (0,1), (2,0), (10,0), (10,0) ]      ← 最后两个完全相同（重复向量）
观测中心 c0 = m0 = (0,0)， c1 = m4 = (10,0)              ← 中心取自 M 本身
cell0 = {m0,m1,m2,m3} → r0 = 2        cell1 = {m4,m5} → r1 = 0
阈值 t = 1.5
```

**手算与程序输出完全一致**（`project\src\w1_bounds_example.py`）：

| query | 坐标 | s_M(q) | L(q) | U(q) | 完整库真值 | 筛查结果 | L≤s≤U | 覆盖的情形 |
|---|---|---|---|---|---|---|---|---|
| q1 | (0.5, 0) | 0.5000 | 0 | 0.5000 | normal | **normal（本地）** | ✅ | (a) U ≤ t |
| q2 | (0, 10) | 9.0000 | 8.0000 | 10.0000 | alarm | **alarm（本地）** | ✅ | (b) L > t |
| q3 | (3, 0) | 1.0000 | 1.0000 | 3.0000 | normal | escalate → normal | ✅ | (c) 跨阈值 |
| q4 | (0, 3) | 2.0000 | 1.0000 | 3.0000 | **alarm** | escalate → alarm | ✅ | (c) 跨阈值 |
| q5 | (2, 1.5) | **1.5000** | 0.5000 | 2.5000 | normal | escalate → normal | ✅ | (d) s_M = t 并列 |

- 区间违规数 **0**；本地已解决项与真值不一致 **0**；本地解决比例 2/5 = 40%。
- **三角不等式的平实解释**：三角形任意一边不超过另外两边之和。取参考点 m 与中心 c（都在集合里），
  对任意查询 q 有 `d(q,c) ≤ d(q,m) + d(m,c)`，移项得 `d(q,c) − d(m,c) ≤ d(q,m)`。
  因为 cell 里所有 m 都满足 `d(m,c) ≤ r`，所以 `d(q,c) − r` 是"从 q 到本 cell 任意参考点的距离"的
  **下界**（负数按 0 处理）。同时 `d(q,c)` 本身就是某个参考点（中心）到 q 的距离，所以它是**上界**。
  对所有 cell 取下确界，就得到 `L(q) ≤ s_M(q) ≤ U(q)`。
- **为什么要 q4**：它证明"靠近中心"**不等于**"正常"。若图省事用 `U ≤ t` 之外还允许"距离小于半径就当正常"，
  q4 这种在半径外、真值却是 alarm 的样本就会被误判。区间必须整体落在阈值一侧才能下结论。

**证据**：`project\src\w1_bounds_example.py`（可重跑）、`bounds_check.py`（DSH 工作区版，供对照）。

---

## 4. A14-2：数据待定时的距离检查 + Phase 0 的实测计时（任务 2、9）

**为什么这样做**：A14 原文写明「If data access is pending, run tensor-distance checks on ten artificial 2-D vectors」。
数据集未获批，所以走了这条被明确许可的替代路径，并把 A6 要求的数值契约一起固定下来。

**Part A —— 十个人造二维向量**（朴素双重循环 vs 向量化）：4 个查询逐个核对，最大绝对差 **0.00e+00**。

**Part B —— 分块 vs 暴力精确最近邻**
- B0 资源事实：整块物化 `(P=512, N=20000, D=384)` 的 float64 距离矩阵需要 **29.3 GiB** →
  本机 32 GB 内存下不可行。**所以分块不是优化，是必需。**（第一次跑这个检查时真的 OOM 了，这就是证据。）
- B1 小规模（N=2000, D=384, P=64）：整块 0.194 s vs 分块 0.194 s，最大绝对差 **0.00e+00**，分数全部有限。
- B2 真实规模（N=20000, D=384, P=512）：块大小 bs ∈ {34, 32, 16, 8} 的**结果最大绝对差 0.00e+00**，
  用时均约 **16.6 s**（16.58 / 16.71 / 16.66 / 16.75 s）。
  → **更正说明**：这里原本写的是「bs=256 → 92.7 s，bs=32 → 26.0 s，bs=32 快 3.5 倍」。该结论**不可复现**：
  bs=256 的单块中间张量需要 **14.6 GiB**，当时只是内存恰好够；同一条命令第二次运行直接 `ArrayMemoryError`。
  现已改为**按内存预算反推块大小**（预算 2 GiB → 上限 34）；代价是"块大小的速度差"也随之消失（都约 16.6 s），
  说明原先那 3.5 倍其实是内存压力伪影。
  → **教训（已写进脚本注释）：一次跑通 ≠ 可复现。凡是"靠当时机器状态才成立"的数字，都不能进结论。**

**Part C —— torch 版（本机 GPU）**
- CPU 分块 0.0245 s vs **GPU 分块 0.0077 s**，加速 **3.2×**（库已在显存内，不含编码器前向）。
  注意：同一项加速比两次运行分别给出 **7.4×** 与 **3.2×**，**随机器负载波动**；
  第 7 周报时延必须在固定功耗档、空载条件下重测，不得引用这里的数字。
- **GPU(float32) 与 CPU 的最近距离最大绝对差 = 2.38e-07**

**这最后一个数字很重要**：我在距离核对里固定的容忍值 `TOL = 1e-9` 是针对 **float64/numpy** 的；
GPU float32 的路径差异比它大**两个数量级**。第 4–6 周为区间设计浮点保护量时，若直接沿用 1e-9，
会把正常的浮点噪声误判成"区间违规"。按 A9 的要求，保护量必须按实际计算路径取（float32 建议从 1e-6 量级起算）。

**证据**：`logs\w1_distance_checks.log`、`logs\w1_distance_checks_torch.log`、`logs\w1_vram_limit.json`。

---

## 5. 显存上限与功耗档实测（任务 11）——本次最有价值的一条方法学发现

**第一次探测是错的**：我原本以为"跑到 OOM 前一位"就是上限。实测发现 512px / batch 192 的
`max_memory_allocated()` 达到 **10835 MiB**，而物理显存只有 **8187 MiB** ——
**Windows 驱动允许显存静默溢出到主机内存（shared GPU memory），全程不报 OOM**。
它只是把时延拖慢：512px/batch256 耗时 71.7 s，而同分辨率 batch128 只要 3.7 s（约 20 倍）。

**修正后的判据**：安全上限 = 峰值 ≤ 80% 物理显存（6550 MiB）；溢出警戒 = 峰值 > 100% 物理显存。

| 分辨率 | 安全 batch | 峰值 | 占物理显存 | 溢出起点 | 线性外推安全上限 |
|---|---|---|---|---|---|
| 256×256 | **256** | 3787 MiB | 46.3% | 未观测到 | ≈456（k≈13.8 MiB/张） |
| 384×384 | **192** | 6215 MiB | 75.9% | 256（100.1%） | ≈202（k≈31.0 MiB/张） |
| 512×512 | **112** | 6435 MiB | 78.6% | **160** | ≈114（k≈55.0 MiB/张） |

- 外推模型的验证：384px 预测 202 vs 实测 ≥192 ✓；512px 预测 114 vs 实测 112 ✓。
- 骨干权重常驻 265.1 MiB；**两轮扫描结果一致**（可复现）。
- 功耗档：**Current / Requested = 80 W，Default = 55 W**，Min 5 W → 机器当前在性能档。
  第 7 周报时延必须连同该档位报告，否则数字不可比（插拔电源会变）。

**为什么这条重要**：如果只按 OOM 判定并据此设定实验 batch，第 7 周会得到一组
"看起来能跑、实际在主机内存里跑"的时延数字，而且无法从表面看出来。

---

## 6. A14-4：三种角色清单（任务 4）

**做了什么**：写了 `scripts\make_manifests.py`，规则与 handout A7 对齐：
- 三种角色只从正常样本划分（`train/good`，AD 2 再加 `validation/good`）；
- **确定性划分**：按 `sha256(文件名 + seed)` 排序切片，而不是依赖 `random.shuffle` 的实现细节；
- 建议规模 reference-fit 16 / development 24 / calibration 其余全部；
- 每张图记录 sha256（清单改一行＝换了一份数据集）；
- **不读 test 目录内容**，只统计文件数量——缺陷标签在协议冻结前不许参与任何选择；
- 写完清单后**读回 CSV 复查**互斥性。

**自检结果（合成数据，用于验证逻辑，不是 MVTec）**：
- 3 类 × 100 张正常样本 → 16 / 24 / 60 划分成功
- 跨角色共享同一 sha256 = **0**；共享同一路径 = **0**；样本总数 300，无遗漏
- 两次运行生成的清单**逐字节一致**（复现性通过）

**真实数据模式结果**：bottle / tile / screw 全部 `[MISS]`，未生成任何真实清单 —— 因为
`F:\research\data\mvtec_ad\` 还是空的。数据一到，同一条命令即可产出真实清单。

**诚实说明**：`[WARN] calibration 只有 60 张` 是合成数据只有 100 张正常样本导致的；真实 MVTec
每类正常样本更多，但**具体数量我没有编造**，等数据到位由脚本自动列出。同理，我没有凭记忆写
"bottle 有 209 张训练图"之类的数字进清单。

**证据**：`logs\w1_manifests_selftest.log`、`logs\w1_manifests_real.log`。

---

## 7. 阅读任务（Week 1 Day 3，任务 12）—— 部分完成，边界明确

- 我产出了**可核对的部分**：三个二维三角不等式例子（含数字）、R7 与 R1 的要点提纲（供你比对原文）、
  以及 A12 Phase 1 要求的**五个未决问题**。见 `week1\W1_READING_NOTES.md`。
- 我**没有**代替你读原文，也**不会**声称"已完成精读"。3 页笔记里"我的理解 → 论文说的 → 差异 →
  对第 4 周区间的影响"这四栏必须由你填；A12 要求的口头/录屏讲解也只能你来讲。

---

## 8. 本周**没有**做的事（边界，防止越界）

- ❌ 没有做任何 PatchCore/AnomalyDINO 的**复现**（那是 Week 2 Phase 2，且需要数据）
- ❌ 没有在真实 MVTec 图像上跑任何东西（数据未获批）
- ❌ 没有设计或实现筛查方法（那是 Week 4 Phase 4）；本周只有"手算 + 单元级校验"
- ❌ 没有做 YOLO 剪枝 / 扩散增强 / 多模态（handout 明令在试点问题验证前不许开始）
- ❌ 没有调任何阈值、预算或超参（连一个真实分数都还没有）
- ❌ 没有绕开 MVTec 的登记表去用第三方镜像
- ❌ 没有对油气现场做任何泛化声明

---

## 9. 下一步（Week 2 的第一批动作，需要你确认后再做）

1. **拿到数据**：去 mvtec.com 填 MVTec AD 的下载表（AD 2 可一并申请）。拿到后放进
   `F:\research\data\mvtec_ad\<category>\train\good\`，然后立刻跑
   `make_manifests.py` 生成真实清单并复查互斥性。
2. **补上被阻塞的检查**：按划分列出图像与标签、显示图像/掩码、跑一个 batch、
   跑 PatchCore 最小文档示例（保存配置、分数、patch map）。
3. **AnomalyDINO 冒烟**：在新环境里按文档默认设置跑 1-shot（本周环境已建好，只差数据）。
4. **权重的 sha256**：跑基线时下载 WRN-50 / DINOv2 权重后立即 `Get-FileHash` 补进 `environment.md` §3。
5. **决策点**：是否要做 canonical（py3.8 + 原 pin + CPU）复现作为对照。若做，需要另开一个环境，
   并接受"只能 CPU、很慢"的代价。

---

## 10. 附：本周产出的文件清单

| 路径 | 说明 |
|---|---|
| `week1\environment.md` | 环境清单（已填入全部实测值） |
| `week1\W1_EVIDENCE.md` | 本文件 |
| `week1\W1_WEEKLY_REPORT.md` / `.pdf` | 一页周报（md 为源，pdf 为交付） |
| `week1\W1_READING_NOTES.md` | 阅读提纲 + 三个三角不等式例子 + 五个问题 |
| `scripts\fetch_sources.ps1` | 源码锚定（ZIP + commit + 树指纹） |
| `scripts\check_env.ps1` | 环境验收（GPU 冒烟 + 分辨率上限 + freeze 留档） |
| `scripts\make_manifests.py` | 三角色清单生成与互斥复查（含自检模式） |
| `project\src\w1_bounds_example.py` | A14-3 的手算例子（可重跑） |
| `project\src\w1_distance_checks.py` | A14-2 回退路径 + 分块/暴力核对 + GPU 计时 |
| `project\src\w1_vram_limit.py` | 显存安全上限与溢出警戒实测 |
| `logs\anchors_latest.json`、`anchors_*.md` | 锚点报告 |
| `logs\env_*.json`、`pip_freeze_*.txt`、`pip_check_*.txt` | 环境证据 |
| `logs\w1_*.log`、`w1_vram_limit.json` | 本周各项运行的原始输出 |
| `archive\sources\` | 三个上游源码归档（含 sha256 记录） |
