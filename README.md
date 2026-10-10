# adedge — 项目代码仓库

> 一句话目标：检验「正常参考库被压缩后，工业异常报警的二元决策是否仍然一致」，
> 并用保守距离区间做「确定正常 / 确定报警 / 升级查询」的可审计筛查。

## 路径约定（不要随意更改）

| 用途 | 路径 | 读写规则 |
|---|---|---|
| 官方基线仓库 | `F:\research\repos\` | **只读**。任何修补导出为 `project\patches\*.patch` |
| 数据集 | `F:\research\data\` | **只读**。下载后不再改动 |
| 权重 / 特征缓存 | `F:\research\cache\` | TORCH_HOME / HF_HOME 指向这里 |
| 角色清单 | `F:\research\manifests\` | reference-fit / development / calibration，同一原图不跨角色 |
| 运行输出 | `F:\research\runs\<日期>_<实验名>\` | 每次运行一个目录，含 run.json |
| 日志与锚点 | `F:\research\logs\` | anchors_*.json / env_*.json |

## 复现一份运行需要什么

`run.json` 必须记录：env 名 + `pip freeze` 哈希、仓库 commit、权重 sha256、
数据清单 sha256、阈值与聚合方式、随机种子、命令原文。

## 本周（W1）不包含

任何模型改进、剪枝/量化/蒸馏、扩散增强、多模态融合。