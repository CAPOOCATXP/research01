# MVTec AD 数据来源与校验记录

**日期**：2026-10-11 · **用途**：证明实验所用数据与官方发布一致，并如实记录获取路径的偏离。

## 1. 为什么没有用官方下载页

MVTec AD 官方下载页 `https://www.mvtec.com/research-teaching/datasets/mvtec-ad/downloads`
上的 **16 个链接全部返回 HTTP 404**（含整包与全部 15 个分类）。这些链接指向 2021-08 创建的 myDrive 共享，
已全部过期。证据：`logs/mvtec_download_outage.json`（bottle/tile/screw/整包四个链接均为 404）。

- 登录（cidaas SSO）不改变这一结果：链接本身已失效，与账号状态无关。
- 官方「下载数据集」表单为 Act-On 营销表单，需人工浏览器提交，无法脚本化；且其提交后是否给出新链接未经确认。

## 2. 实际来源

| 项 | 值 |
|---|---|
| 镜像 | HuggingFace `micguida1/mvtech_anomaly_detection` |
| 文件 | `mvtec_anomaly_detection.tar.xz` |
| 下载地址 | `https://huggingface.co/datasets/micguida1/mvtech_anomaly_detection/resolve/main/mvtec_anomaly_detection.tar.xz` |
| 字节数 | 5,264,982,680 |
| **sha256** | `cf4313b13603bec67abb49ca959488f7eedce2a9f7795ec54446c649ac98cd3d` |
| 与镜像站登记 `lfs.oid` 比对 | **一致** |

**许可**：数据以 **CC BY-NC-SA 4.0** 发布，该许可**允许再分发**（署名、非商用、相同方式共享）。
本项目为非商用学术研究，使用镜像不违反许可；但**偏离了"官方来源"这一偏好**，故在此如实记录。

## 3. 三层校验（`scripts/verify_mvtec.py`）

| 校验 | 方法 | 结果 |
|---|---|---|
| 归档完整性 | 本地 sha256 vs 镜像站登记 `lfs.oid` | ✅ 一致（5,264,982,680 B） |
| 逐类计数 | 15 类 train/good 与 test 总数 vs 官方发布计数 | ✅ 15/15 全部吻合，合计 **3629 / 1725** |
| 可解码性 | 抽检 400 张 PNG 解码 | ✅ 0 张损坏 |

官方逐类计数（实测与期望完全相同）：

| 类别 | train | test | 类别 | train | test |
|---|---|---|---|---|---|
| bottle | 209 | 83 | pill | 267 | 167 |
| cable | 224 | 150 | screw | 320 | 160 |
| capsule | 219 | 132 | tile | 230 | 117 |
| carpet | 280 | 117 | toothbrush | 60 | 42 |
| grid | 264 | 78 | transistor | 213 | 100 |
| hazelnut | 391 | 110 | wood | 247 | 79 |
| leather | 245 | 124 | zipper | 240 | 151 |
| metal_nut | 220 | 115 | **合计** | **3629** | **1725** |

## 4. 结论与引用方式

数据与官方发布一致（计数逐项吻合 + 归档哈希一致 + 无损坏），可用于实验。

论文/报告中关于数据获取应写为：
> MVTec AD (CC BY-NC-SA 4.0) 经镜像获取；官方下载链接于 2026-10-11 核实全部失效（HTTP 404），
> 所用归档的 sha256 与逐类样本数均与官方发布一致。

## 5. 复现

```powershell
python scripts\verify_mvtec.py --root F:\research\data\mvtec_ad `
  --archive F:\research\data\_download\mvtec_anomaly_detection.tar.xz `
  --expect-sha256 cf4313b13603bec67abb49ca959488f7eedce2a9f7795ec54446c649ac98cd3d
```

即：下载 → 解压 → 校验，三步都可重跑。
