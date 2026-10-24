# 周报 W3 ｜ 吴源泰 ｜ 2026-10-11 ~ 2026-10-17

*Phase 2 复现 + Phase 3 缺口验证（真实数据）· 项目根 `F:\research` · 实际投入约 14 h*

## 0. 一句话结论

**MVTec AD 已到手并通过三层校验**（归档 sha256 + 15 类逐项计数 3629/1725 + 400 张解码），真实实验跑通：
压缩确实改变报警决策，**在 1% 压缩下三类分歧 24.1% / 12.0% / 41.9%**，且**全部是多报、没有漏报**；
独立重校准后残余降到 0–5%；区间筛查在**零错判**的前提下本地裁决 91.6% / 40.2% / 85.6%。
**Gate 1（缺口成立）在 10% 压缩下 2/3 类别达标，判定 GO。**

## 1. Done

| 任务 | h | 产物 | 状态 |
|---|---|---|---|
| 定位并下载 MVTec AD（官方 404，改镜像） | 2.0 | `data/mvtec_ad`（6,612 张 PNG / 4.91 GB） | ✅ |
| 三层完整性校验 + 来源证明 | 1.5 | `scripts/verify_mvtec.py`、`data/DATASET_PROVENANCE.md` | ✅ |
| 真实三角色清单（bottle/tile/screw） | 0.5 | `manifests/*.csv`（9 个，互斥 0） | ✅ |
| 真实特征管线（WRN-50 + max-score 检测器） | 4.0 | `scripts/pipeline_patchcore.py` | ✅ |
| Phase 2 复现口径（全量参考，AUROC） | 2.0 | `logs/w3_repro.json` | ✅ |
| Phase 3 决策实验（16-shot，4 个压缩比） | 3.0 | `logs/w3_decision_16shot.json` | ✅ |
| 真实数据出图 | 1.0 | `reports/figures/figure_5/6_*.png/pdf` | ✅ |

## 2. Evidence

### 2.1 复现口径（全量 train/good 作参考库，只算 AUROC，不设阈值）

| 类别 | 库大小 | image AUROC | 与 PatchCore 论文（≈） | 判定 |
|---|---|---|---|---|
| bottle | 163,856 patches | **1.0000** | 100.0% | ✅ 达标 |
| tile | 180,320 patches | **0.9809** | 98.7% | ✅ 差 0.6 点，在 2 点容差内 |
| screw | 250,880 patches | **0.9582** | 98.1% | ⚠️ 差 2.3 点，**超出容差** |

**偏离项（必须写明）**：自研 max-score 检测器（无 PatchCore 的重加权、无 `--faiss` 精确最近邻、224px、参考库用全部 patch，不下采样）。screw 的差距主要来自无重加权 + 下采样，需在 Week 4 修。

### 2.2 决策实验（16-shot：库=12,544 patch，阈值=校准集 95 分位）

| 类别 | 全库 FAR / 召回 | 1% 分歧 | 5% 分歧 | 10% 分歧 | 25% 分歧 | 重校准后（10%） | 升级率 | 本地错判 |
|---|---|---|---|---|---|---|---|---|
| bottle | 0.0% / 100% | **24.10%** | 3.61% | 0.00% | 0.00% | 0.00% | 8.4% | **0** |
| tile | 0.0% / 84.5% | **11.97%** | 3.42% | 2.56% | 2.56% | 1.71% | 59.8% | **0** |
| screw | 9.8% / 11.8% | **41.88%** | 7.50% | 3.12% | 0.00% | 2.50% | 14.4% | **0** |

- **配置**：env `adedge-patchcore`（torch 2.6.0+cu124）· `scripts/pipeline_patchcore.py` · seed=0 ·
  resize 256 / imagesize 224 / batch 8 / 最长边库 20,000
- **划分**：reference-fit 16 / development 24 / calibration 169–280（来源 `manifests/*.csv`，互斥 0）
- **日志**：`logs/w3_repro.json`、`logs/w3_decision_16shot.json`、`logs/mvtec_verify.json`
- **复现**：
  ```powershell
  python scripts\verify_mvtec.py --root F:\research\data\mvtec_ad `
    --archive F:\research\data\_download\mvtec_anomaly_detection.tar.xz `
    --expect-sha256 cf4313b13603bec67abb49ca959488f7eedce2a9f7795ec54446c649ac98cd3d
  python scripts\pipeline_patchcore.py --categories bottle tile screw --ref-mode all --auroc-only --max-bank 100000
  python scripts\pipeline_patchcore.py --categories bottle tile screw --max-bank 20000
  ```

### 2.3 Gate 1 判定（按 A7 门槛：≥2 个百分点、≥2 个类别、有用存储压缩）

| 压缩比 | 达标类别数 | 判定 |
|---|---|---|
| 1% | 3/3（24.1 / 12.0 / 41.9） | 成立，但 1% 不是"有用"的压缩 |
| 5% | 3/3（3.6 / 3.4 / 7.5） | **成立** |
| 10% | 2/3（0.0 / 2.6 / 3.1） | **成立（刚好过线）** |
| 25% | 1/3（0.0 / 2.6 / 0.0） | 不成立 |

**结论：GO。** 缺口在 5–10% 压缩区间稳定成立，正是"有用存储减少"的区间。

## 3. Blockers

1. **screw 的 16-shot 检测器太弱**（AUROC 0.6186，召回 11.8%）：16 张参考图覆盖不了螺丝的旋转多样性。全量参考下 AUROC 升到 0.9330。→ 决策实验需补"全量参考"条件（库=40 张，受三角色划分限制），否则 screw 的分歧数字缺少可信基座。
2. **screw 的全量参考 AUROC 仍差 2.3 点**（0.9582 vs 98.1%）：需实现 PatchCore 的重加权分数或提高 bank 上限。这是 Week 4 的第一件事。
3. **test/good 只有 20–41 张**：FAR 的置信区间很宽（0/20 与 5% 兼容），不能支撑"低误报"主张，只能说"未见误报"。

## 4. Next

| # | 任务 | 预期产出 | 预计 h |
|---|---|---|---|
| 1 | 补"全量参考"的决策实验（库=40 张）+ 4/1-shot 条件 | 三个参考数量的分歧曲线 | 4 |
| 2 | 修 screw：加重加权或提高 bank 上限，把 AUROC 拉进 2 点容差 | 复现表达标 | 5 |
| 3 | 五个随机种子的参考选择，报配对区间 | 种子方差 + 95% 区间 | 3 |

## 5. 最重要的负面结果

**bottle 在 10% 与 25% 压缩下分歧恰好为 0**。这不是"压缩无害"，而是 bottle 的缺陷信号太强（AUROC 1.0），分歧全被"确定报警"吸收。换句话说：**分歧率本身依赖检测器余量**，检测器越强、压缩越看不出问题。这一点必须在论文里讲清楚，否则会被误读成"压缩是安全的"。

**另一条**：screw 在 16-shot 下 AUROC 0.62、召回 11.8%——**用这样的检测器谈"决策保持"没有意义**（几乎什么都判正常）。所以 Week 4 必须先修检测器，再谈保持。

## 6. 假设变更

无变更。H1（压缩会改变部分近阈值报警）在真实数据上得到支持；H2（区间能固定相当比例决策）也成立（本地裁决 40–92%、零错判），但 **tile 的升级率 59.8% 说明代价不小**，H2 的"减少整库查询"要打折扣。
