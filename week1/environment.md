# 环境清单 environment.md

| 项 | 值 |
|---|---|
| 项目 | When Memory Compression Changes Industrial Alarms（暂定名）· Phase 0 |
| 负责人 | 吴源泰 |
| 主机 | 笔记本 `laptop-csp8hpp8` |
| 初版探测 | 2026-10-07 16:00 (+08:00) |
| **本版更新** | **2026-10-10（Phase 0 收尾：环境建成、显存上限实测、源码锚定完成）** |
| 状态图例 | ✅ 实测（有命令与输出）· ⚠️ 需复核 · ❌ 缺失 · ⬜ 待填（不得猜测） |

**一句话结论**：环境已建成并验证可用（conda 两个环境 + torch 2.6.0+cu124 + GPU 冒烟通过）；源码全部按 commit 锚定；**唯一未解决的是数据集访问**（MVTec AD / AD 2 官网需填表，尚未获批），因此所有依赖真实数据的检查仍然待做。另有三条实测资源事实必须记住：显存"不 OOM"不等于"没溢出"、`git clone` 在本机阻塞、两个官方仓库的 numpy 要求互相冲突。

---

## 1. 硬件

| 项目 | 实测值 | 状态 | 来源 / 备注 |
|---|---|---|---|
| 操作系统 | Windows 11 25H2，build **26200.9457** | ⚠️ | 注册表 `ProductName` 仍写 "Windows 10 Home China"（Win11 遗留字段）；`os.release()`=`10.0.26200`；`EditionID`=`CoreCountrySpecific`。待你在"设置→关于"复核 |
| 机型 | 笔记本电脑 | ✅ | 移动版 GPU，受功耗墙/温度影响 |
| CPU | Intel Core i7-14700HX，**28 个逻辑处理器** | ✅ | 注册表 `HKLM:\HARDWARE\DESCRIPTION\System\CentralProcessor\0` |
| 内存总量 | **31.8 GB** | ✅ | `node -e "os.totalmem()"` |
| 内存（探测瞬间空闲） | 12.8 GB | ✅ | 同上 |
| GPU | NVIDIA GeForce RTX 4070 Laptop GPU | ✅ | `nvidia-smi` |
| 显存总量 | **8187.5 MiB** | ✅ | `torch.cuda.get_device_properties(0)` |
| 驱动 / 算力 | 591.74 / sm_89 | ✅ | `nvidia-smi` |
| CUDA（驱动报告） | 13.1 | ✅ | `nvidia-smi` 表头，仅代表驱动支持上限 |
| CUDA Toolkit / nvcc | **未安装** | ❌ | 不需要：PyTorch wheel 自带 CUDA 12.4 runtime |
| **GPU 功耗墙** | **Current / Requested = 80 W，Default = 55 W**，Min = 5 W | ✅ | `nvidia-smi -q -d POWER`。**80 W 不是 55 W**，说明机器当前处于性能档；跑第 7 周 latency 时必须连同该档位一起报告 |
| 空闲功耗 / 温度 | 4.0 W / 53 °C | ✅ | 探测瞬间，供对照 |

### 1.1 实测显存上限（本次新增，Phase 0 的必填项）

判据说明：**只看"是否 OOM"是错的**。本机 Windows 驱动允许显存静默溢出到主机内存
（shared GPU memory）——探测中观测到峰值 **14355 MiB，达物理显存的 175%**，全程没有报 OOM，
只是慢（512px/batch256 耗时 71.7 s，而 batch128 只要 3.7 s）。因此判据取两条：

- **安全上限** = 峰值 ≤ 80% 物理显存（6550 MiB）
- **溢出警戒** = 峰值 > 100% 物理显存

骨干：`wide_resnet50_2(weights=None)`（与 PatchCore 同架构），冻结权重常驻**265.1 MiB**，
单次前向，每配置前清缓存并重置峰值统计；**两轮结果一致**。

| 分辨率 | 已验证安全 batch | 该点峰值显存 | 占物理显存 | 次一档 | 溢出起点 | 首次 OOM |
|---|---|---|---|---|---|---|---|
| 256×256 | **256** | 3787 MiB | 46.3% | — | 未观测到 | 未观测到 |
| 384×384 | **192** | 6215 MiB | 75.9% | 256 → 8195 MiB（100.1%，已溢出） | 256 | 未观测到 |
| 512×512 | **112** | 6435 MiB | 78.6% | 128 → 7315 MiB（89.3%，超安全区） | **160** | 未观测到 |

线性外推（峰值 ≈ 常驻 + k × batch，k 由实测拟合，已验证：384px 预测 202 vs 实测 ≥192；512px 预测 114 vs 实测 112）：

- 256px：k ≈ 13.8 MiB/张 → 安全上限约 **456**
- 384px：k ≈ 31.0 MiB/张 → 安全上限约 **202**
- 512px：k ≈ 55.0 MiB/张 → 安全上限约 **114**

> 用途：PatchCore 官方默认 `--resize 256 --imagesize 224`，落在 256px 行；第 7 周做高分辨率
> 对比时，512px 只能取 batch ≤112，否则测出来的时延是"主机内存回退"的时延，不可比。
> 这是**单帧前向**的上限，不含库内存、特征缓存与优化器状态（本项目不做训练，暂无后者）。

### 磁盘（GB，free / total）

| 盘符 | 空闲 | 总量 | 用途 |
|---|---|---|---|
| C: | 116.7 | 299.9 | 系统；**conda 环境实际落在这里**（见 §2.1） |
| E: | 121.1 | 346.5 | Anaconda / Git / Python 3.12 |
| **F:** | **160.2** | 200.0 | **项目根 `F:\research`**（代码、数据、缓存、清单、日志） |
| **G:** | **522.5** | 1907.7 | 备选大容量盘（若 F: 空间吃紧，把 data/cache 联接过来） |
| D: / H: | 14.1 / 0.1 | 105.2 / 0.1 | 勿用 |

目录约定（已建成，见 `F:\research\README.md`）：`repos\` 与 `data\` 只读，`cache\` 放权重与特征，
`manifests\` 放角色清单，`runs\` 每次运行一个子目录，`logs\` 放锚点与环境报告，`archive\sources\` 放源码归档。

---

## 2. 软件

### 2.1 conda 环境（本次建成）

**重要实测事实**：`conda create -n X` 没有建在 `E:\anaconda\envs`，而是建在
**`C:\Users\yuantai\.conda\envs\X`**——因为 `conda config --show envs_dirs` 的第一项就是它。
后果：`scripts\check_env.ps1` 的默认搜索路径（`E:\anaconda\envs`）**找不到这个环境**，
必须显式传 `-Python <绝对路径>`。本清单里的所有结果都是用绝对路径跑出来的。

| 环境 | 解释器 | python | numpy | opencv | torch | freeze sha256 |
|---|---|---|---|---|---|---|
| `adedge-patchcore` | `C:\Users\yuantai\.conda\envs\adedge-patchcore\python.exe` | 3.10.22 | 2.2.6 | 5.0.0 | 2.6.0+cu124 | `70612E24...DAB6` |
| `adedge-anomalydino` | `C:\Users\yuantai\.conda\envs\adedge-anomalydino\python.exe` | 3.10.22 | **1.26.4** | **4.10.0.84** | 2.6.0+cu124 | `2E1C8823...9A8E` |

**为什么必须是两个环境**：AnomalyDINO 的 `requirements.txt` 明确写着
`numpy==1.26 # numpy 2.0 not compatible at the moment`，而 PatchCore 侧实测 numpy 2.2.6 正常。
两个 pin 无法共存，混装必然破坏其中一个基线。

**只钉 numpy 还不够（本次新增发现）**：把 numpy 降到 1.26.4 后，`pip check` 立刻报
`opencv-python 5.0.0.93 requires numpy>=2`；把 opencv 降到 4.14，pip 又**把 numpy 拉回 2.2.6**。
最终只有**同时钉住** `numpy==1.26.4` + `opencv-python==4.10.0.84` 才得到一致解。
→ 结论：依赖隔离要按「互相牵制的包组」做，不是按单个包做。
两个环境最终都通过 GPU 冒烟（sm_89，峰值 70 MiB），`pip check` 均为 No broken requirements found。

这就是 Phase 0 要求"隔离依赖"的直接理由。

### 2.2 `adedge-patchcore` 已安装版本（对照 PatchCore 官方 requirements.txt）

| 包 | 官方要求 | 本机实际 | 状态 |
|---|---|---|---|
| torch | >= 1.10.0 | **2.6.0+cu124** | ✅（升到 2.x 的原因见 §2.3） |
| torchvision | >= 0.11.1 | 0.21.0+cu124 | ✅ |
| faiss-cpu | （requirements 列出） | **1.15.1（Windows 有 wheel）** | ✅ 修正我先前的顾虑 |
| matplotlib | >= 3.5.0 | 3.10.9 | ✅ |
| pillow | >= 8.4.0 | 12.3.0 | ✅ |
| pretrainedmodels | >= 0.7.4 | 0.7.4 | ✅ |
| scikit-image | >= 0.18.3 | 0.25.2 | ✅ |
| scikit-learn | >= 1.0.1 | 1.7.2 | ✅ |
| scipy | >= 1.7.1 | 1.15.3 | ✅ |
| tqdm | >= 4.62.3 | 4.70.1 | ✅ |
| click | >= 8.0.3 | 8.5.0 | ✅ |
| **timm** | **requirements.txt 里没有！** | 1.0.30（另行安装） | ⚠️ 官方仓库的依赖缺口：`src/patchcore/backbones.py` 第一行就 `import timm` |
| **PyYAML** | （AnomalyDINO 侧需要） | 6.0.3（另行安装） | ⚠️ 同上，`run_anomalydino.py` 第 4 行 `import yaml` |

- `pip freeze`：`logs\pip_freeze_adedge-patchcore_20261010-102504.txt`
  **sha256 = `70612E24C396006099B60B79CA47ABBA32EAC0F54BE6A2A6CC53F5E6D1F2DAB6`**（写进每次运行的 run.json）
- `pip check`：`logs\pip_check_adedge-patchcore_20261010-102504.txt`（无输出＝无冲突）
- 环境 JSON：`logs\env_adedge-patchcore_20261010-102504.json`
- cudnn：90100

**已实测可用**（不是"装上了"，而是"跑起来了"）：
- GPU 冒烟 `OK`：卷积前向+反向在 sm_89 上正常，峰值 70 MiB（无 `no kernel image` 问题）
- 官方 CLI 可加载：`run_patchcore.py --help` 与 `run_anomalydino.py --help` 都能打印参数表
- 有限性：随机特征与最近邻距离全部 `isfinite`

### 2.3 为什么用 torch 2.6 而不是仓库原始 pin

PatchCore 官方 requirements 只要求 `torch>=1.10.0`；README 注明其结果是用 **Python 3.8** 得到的。
但本机 GPU 是 **sm_89 (Ada)**，只有 **CUDA ≥ 11.8** 的构建才带 sm_89 kernel，即 **torch ≥ 2.0 的
cu118/cu121/cu124 wheel**。因此采用「现代环境」路线（py3.10 + torch 2.6 + cu124），
代价是**与论文原始环境不一致**，必须在报告中作为**偏离项**记录：

- 偏离 1：Python 3.10（论文 3.8）
- 偏离 2：torch 2.6（论文时代的 1.x）
- 偏离 3：本机 CPU 推理/GPU 推理的数值路径与论文不同（GPU float32 与 CPU 的最大绝对差实测 **2.38e-07**）

> 数值提醒：我在距离核对里固定的容忍值 `TOL = 1e-9` 适用于 **float64 / numpy** 比较；
> **GPU float32 的 CPU↔GPU 差异约 2.4e-07，比它大两个数量级**。第 4–6 周设计区间保护量时，
> 必须按实际计算路径取 guard（float32 路径建议从 1e-6 量级起算），否则"区间违规"会被误判。
> 这条直接进入 A9 的"数值有效性"一节。

### 2.4 其他工具

| 工具 | 状态 | 备注 |
|---|---|---|
| conda | 24.7.1（`E:\anaconda`，base python 3.12.4） | `envs_dirs` 首项在 C: |
| git | 2.53.0.windows.2 | **只能 `ls-remote`，不能 `clone`**，见 §5 |
| **gh (GitHub CLI)** | **未安装** | 因此无法用 `gh` 克隆/建仓库；公开仓库用 ZIP 快照 |
| 默认 python | `E:\python\python.exe` 3.12.3（numpy 2.4.6） | 只用于纯 numpy/文档脚本，**不装项目依赖** |
| PowerShell | **没有 PowerShell 7，只有 5.1**（5.1.26100.9444） | `.ps1` 含中文必须存成 UTF-8 **带 BOM**，否则语法报错 |
| tar | 可用（bsdtar） | 用于解 `.tar.xz` |

---

## 3. 源码与仓库锚定（本次完成，方式已改为 ZIP 快照）

**为什么不用 `git clone`**：本机 `git ls-remote` 正常（<1 s），但 `git clone` 在 **pack 传输阶段阻塞**
（试过默认、`--depth 1`、`http.version=HTTP/1.1`、禁用 credential helper、禁用交互提示，均在 5 分钟
无输出后放弃）。改用 **codeload ZIP 快照 + 把 commit SHA 钉在 URL 里**，`Invoke-WebRequest` 走 .NET/schannel
通道，2.3 MB 用时 1–2 s，稳定可复现。

| 名称 | 类型 | commit / 来源 | 上游日期 | 归档 sha256 | 文件数 | 树指纹 |
|---|---|---|---|---|---|---|---|
| patchcore-inspection | repo | `fcaa92f124fb1ad74a7acf56726decd4b27cbcad` | 2023-03-06 | `7FDBA8B2...39F072` | 401 | `419fbc57...be7d27` |
| AnomalyDINO | repo | `b9d1c2648e3a5247437d4d953d907a8f3d994457` | 2025-12-17 | `975643A4...15D7DF` | 14 | `d23f5352...7598d` |
| mvtec_ad_evaluation | tarball | 官方评测码（公开直链，无需填表） | 2022-10-13 | `DFCDA7D6...13F220` | 11 | `74059be4...f129dae` |

- 完整记录：`logs\anchors_latest.json`、`logs\anchors_20261010-101914.md`
- 归档位置：`archive\sources\`
- **树指纹（tree_fingerprint）**是比 commit 号更硬的锚：sha256 over 排序后的 `相对路径|文件sha256` 列表。
  任何时候重取源码，比对指纹即可确认用的是不是同一个 commit。
- 关键文件自检全部通过：`patchcore-inspection\requirements.txt`、`bin\run_patchcore.py`、
  `AnomalyDINO\run_anomalydino.py`、`src\detection.py` 均存在。
- 注意：**ZIP 快照没有 git 历史**，因此补丁不能用 `git diff` 生成，改用
  `git diff --no-index 原文件 改后文件 > project\patches\xxx.patch`（该命令不需要仓库）。

---

## 4. 数据与许可

| 数据集 | 官方入口 | 许可 | 状态 | 备注 |
|---|---|---|---|---|
| MVTec AD | mvtec.com/research-teaching/datasets/mvtec-ad | CC BY-NC-SA 4.0（**非商用**） | ⬜ **未获批** | 页面为 "Fill in the form"，必须填表才能拿到下载链接。**没有绕开登记去用第三方镜像** |
| MVTec AD 2 | mvtec.com/research-teaching/datasets/mvtec-ad-2 | 同上 | ⬜ 未申请 | 含私有测试服务器，本周不接触 |
| VisA | 经 AnomalyDINO 仓库 README 指向的官方入口 | ⬜ 待抄录 | ⬜ 未获取 | 跨数据集验证用 |
| MVTec 官方评测码 | mydrive.ch 公开直链 | 随数据集条款 | ✅ **已获取** | 见 §3，`archive\sources\mvtec_ad_evaluation_extracted` |

**因此本周所有依赖真实图片的检查都没有做**（列图像与标签、显示图像/掩码、跑一个 batch、
PatchCore 最小示例、真实角色清单）。替代动作与证据见 `W1_EVIDENCE.md`。

---

## 5. 网络与传输通道（实测）

| 目标 | 结果 |
|---|---|
| github.com / pypi.org / download.pytorch.org / mvtec.com / huggingface.co（TCP 443） | ✅ 全部可达 |
| `git ls-remote https://github.com/...` | ✅ 正常，返回 `fcaa92f1...` |
| `git clone`（含 `--depth 1`、HTTP/1.1、禁凭据助手） | ❌ **阻塞**，5 分钟无输出 |
| `Invoke-WebRequest` 下载 codeload ZIP / mydrive 直链 | ✅ 正常（2.3 MB / 1–2 s） |
| `pip install torch`（约 2.5 GB，pytorch 官方 index） | ✅ 正常，全程无中断 |

结论：**网络不是瓶颈**；瓶颈是 (a) 数据集的登记审批，(b) git 的 HTTPS 传输在本机不可用。
工作流因此固定为：源码用 ZIP 快照锚定，Python 包用 pip，数据集等审批。

---

## 6. 三条硬结论（会直接影响后续所有实验的解释）

1. **显存上限必须按"安全区 + 溢出警戒"两条判据报，不能按 OOM 报。** 本机在 512px 下峰值可达
   物理显存的 175% 而不报错，只是把时延拖慢 20 倍。已定：256/384/512px 的安全 batch 上限为
   256 / 192 / 112，且这些数字在**同一功耗档（80 W）**下测得。
2. **两个官方仓库的依赖不可共存**（numpy 1.26 vs 2.x），且两者的 `requirements.txt` 都有缺口
   （PatchCore 缺 `timm`、AnomalyDINO 缺 `PyYAML`）。"一个仓库一个 conda 环境"不是洁癖，是必需。
3. **本机无法 `git clone`**，源码锚定改用 ZIP + commit SHA + 树指纹。这条写进方法学，
   因为它改变了"补丁如何归档"（用 `git diff --no-index`，而非仓库内 diff）。

---

## 7. 仍然未知的项（不得猜测）

- ⬜ MVTec AD / AD 2 的实际下载大小、目录与文件名清单（等审批）
- ⬜ VisA 的官方链接、许可原文、大小
- ⬜ 三个试点类别（bottle / tile / screw）的真实正常样本数量与 test 数量（脚本会在数据到位后自动列出）
- ⬜ 真实照明条件（AD 2）与合成光照扰动之间的差异量级
- ⬜ 是否存在可用的实体边缘设备（决定第 7 周是否只能报工作站数字）
- ⚠️ 操作系统名称复核（注册表遗留字段）
- ⚠️ GPU 当前的 80 W 档位是否为持久设置（若机器插拔电源会变，跑计时前必须重测）

---

## 8. 复现命令

```powershell
# 硬件
nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free,compute_cap --format=csv
nvidia-smi -q -d POWER | Select-String 'Power Limit'
[System.IO.DriveInfo]::GetDrives() | Where-Object {$_.IsReady} |
  ForEach-Object { "{0} {1:N1} GB free / {2:N1} GB total" -f $_.Name, ($_.AvailableFreeSpace/1GB), ($_.TotalSize/1GB) }

# 环境位置与版本
& E:\anaconda\Scripts\conda.exe config --show envs_dirs
& E:\anaconda\Scripts\conda.exe env list
& 'C:\Users\yuantai\.conda\envs\adedge-patchcore\python.exe' -c "import torch,torchvision,numpy;print(torch.__version__,torch.version.cuda,torch.cuda.is_available(),torchvision.__version__,numpy.__version__)"

# 环境验收（GPU 冒烟 + 分辨率上限 + freeze 留档）
powershell -NoProfile -ExecutionPolicy Bypass -File F:\research\scripts\check_env.ps1 `
  -Python 'C:\Users\yuantai\.conda\envs\adedge-patchcore\python.exe' -EnvName adedge-patchcore -Root F:\research

# 显存安全上限（真边界 + 溢出警戒）
& 'C:\Users\yuantai\.conda\envs\adedge-patchcore\python.exe' F:\research\project\src\w1_vram_limit.py

# 源码锚定（ZIP 快照 + 树指纹）
powershell -NoProfile -ExecutionPolicy Bypass -File F:\research\scripts\fetch_sources.ps1 -Force
```

---

## 9. 变更日志

| 日期 | 变更 | 触发 |
|---|---|---|
| 2026-10-07 | 首次生成（硬件/软件探测，多数环境字段为待填） | Phase 0 Day 1 侦察 |
| 2026-10-10 | 建成两个 conda 环境并通过 GPU 冒烟；实测显存安全上限与溢出警戒；源码按 commit 锚定（ZIP + 树指纹）；发现 git clone 阻塞、`timm`/`PyYAML` 依赖缺口、numpy 版本冲突；数据访问确认受阻 | Phase 0 收尾 |
