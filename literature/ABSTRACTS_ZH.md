# A5 阅读清单：摘要双语对照与要点翻译

**读者**：吴源泰 · **目的**：把 A5 六篇必读 + 正文引用的 R8–R11 的**摘要与要点**译成中文，作为精读前的导航
**生成**：2026-10-10 · **原文来源**：见 `literature/SOURCES.md`（含每篇的官方链接与 sha256）
**原文抽取**：`scripts/lit_extract.py` → `literature/txt/*.txt`（可直接在本地检索英文原文）

> **本文件的范围（请先看这条）**
> 这 9 篇合计 **183 页**，一次性全文精译不现实。本文件翻译的是**每篇的摘要（完整）+ 核心贡献 + 方法要点 + 与你项目的关系**，
> 并标出 handout 指定的精读章节。**需要全文精译的，告诉我编号，我逐篇做**（建议从 R7 开始，13 页且是数学地基）。
>
> 文中「原文」段是 PDF 抽取的英文原句（可能有个别 OCR/换行瑕疵）；「中译」段为我的翻译；
> 「我的归纳」段是我的提炼，**不是论文原话**，引用时请回到原文核对。

---

## 通用术语表（先记这些，读起来会快很多）

| 英文 | 中译 | 说明 |
|---|---|---|
| anomaly detection | 异常检测 | 本项目只做**无监督单类**设定 |
| nominal / normal | 正常（样本） | 只给正常图，不给缺陷图训练 |
| cold-start | 冷启动 | 只有正常样本就要能工作 |
| memory bank | 记忆库 / 参考库 | 存正常 patch 特征，检索用 |
| patch / patch-level | 小块 / 小块级 | 特征图上的一个空间位置 |
| coreset / greedy coreset | 核心集 / 贪心核心集 | 从全部正常 patch 里选代表性子集 |
| nearest neighbor (NN) | 最近邻 | 本项目用欧氏距离 |
| AUROC | 受试者工作特征曲线下面积 | 排序指标，**阈值无关** |
| AU-PRO | 区域重叠曲线下面积（按 FPR 归一） | 像素级定位指标 |
| few-shot / one-shot | 小样本 / 单样本 | 只用 1/4/16 张正常参考图 |
| training-free | 免训练 | 不更新任何权重 |
| distribution shift | 分布位移 | 光照、夹具位置、传感器变化 |
| student–teacher | 学生—教师 | 学生学预测教师的正常特征 |
| conformal prediction | 符合预测 | 给出有限样本覆盖保证 |
| calibration set | 校准集 | 用来定阈值/分位数的正常样本 |
| operational threshold | 运行阈值 | 报警判定用的那个 t |
| branch-and-bound | 分支定界 | 精确检索的剪枝算法 |
| expansion constant | 扩张常数 | 度量空间的维数式复杂度参数 |

---

# 一、A5 六篇必读

## R7 · Cover Trees for Nearest Neighbor（最近邻的覆盖树）

**作者**：Alina Beygelzimer, Sham Kakade, John Langford ｜ **出处**：ICML 2006, pp. 97–104 ｜ **本地**：`R7_cover_trees_ICML2006.pdf`（13 页）

**原文（摘要）**
> We present a tree data structure for fast nearest neighbor operations in general n-point metric spaces. The data structure requires O(n) space regardless of the metric's structure. If the point set has an expansion constant c > 2 in the sense of Karger and Ruhl [KR02], the data structure can be constructed in O(c⁶n log n) time. Nearest neighbor queries obeying the expansion bound require O(c¹² log n) time. In addition, the nearest neighbor of O(n) points can be queried in O(c¹⁶n) time. We experimentally test the algorithm showing speedups over the brute force search varying between 1 and 2000 on natural machine learning datasets.

**中译**
> 我们提出一种树形数据结构，用于在一般的 n 点**度量空间**中做快速最近邻操作。无论度量本身的结构如何，该结构都只需要 **O(n) 空间**。如果点集在 Karger 与 Ruhl [KR02] 意义下具有**扩张常数 c > 2**，则该结构可在 O(c⁶n log n) 时间内构建；满足扩张界定的最近邻查询需要 O(c¹²log n) 时间。此外，O(n) 个点的最近邻可以在 O(c¹⁶n) 时间内查询完。我们在自然机器学习数据集上做了实验，相对**暴力搜索**的加速比在 1 到 2000 之间。

**我的归纳（不是原话）**
- 覆盖树是**层级化的度量树**：每一层的点集"覆盖"下一层，层间距离受 2^i 约束，因此可以用球做剪枝。
- 空间是 O(n)——**与树深度无关**；复杂度挂在扩张常数 c 上，而 c 依赖数据分布。
- **剪枝的依据就是三角不等式**：已知到某个点的距离后，可推出一整棵子树的最小可能距离。
- 实验说的是"在自然数据集上有 1–2000× 加速"，这是**经验**结论，不是保证。

**与你项目的关系（handout A5 指定）**
- 这是 `L(q) ≤ s_M(q) ≤ U(q)` 的**几何来源**：球内含参考点 ⇒ 距离下界。
- A5 要求你能说清"**精确搜索 vs 近似搜索**"和"**实证保证 vs 算法保证**"的区别。前者=剪枝不牺牲正确性；后者=对任意输入都成立。
- **不要**直接把 R7 的对数复杂度搬到你的方案上——R10 指出其证明有缺口（见下文）。

**该精读哪几节**：问题定义（§1）、度量球与层级定义、搜索剪枝条件。
**跳过**：复杂度证明（读 R10 的修正版即可）。
**要能回答**：为什么"球内含参考点"给出的是**下界**？

---

## R1 · Towards Total Recall in Industrial Anomaly Detection（PatchCore）

**作者**：Karsten Roth, Latha Pemula, Joaquin Zepeda, Bernhard Schölkopf, Thomas Brox, Peter Gehler ｜ **出处**：CVPR 2022, pp. 14318–14328 ｜ **本地**：`R1_patchcore_CVPR2022.pdf`（11 页）

**原文（摘要）**
> Being able to spot defective parts is a critical component in large-scale industrial manufacturing. A particular challenge that we address in this work is the cold-start problem: fit a model using nominal (non-defective) example images only. While handcrafted solutions per class are possible, the goal is to build systems that work well simultaneously on many different tasks automatically. The best performing approaches combine embeddings from ImageNet models with an outlier detection model. In this paper, we extend on this line of work and propose PatchCore, which uses a maximally representative memory bank of nominal patch-features. PatchCore offers competitive inference times while achieving state-of-the-art performance for both detection and localization. On the challenging, widely used MVTec AD benchmark PatchCore achieves an image-level anomaly detection AUROC score of up to 99.6%, more than halving the error compared to the next best competitor. We further report competitive results on two additional datasets and also find competitive results in the few samples regime.

**中译**
> 能够发现缺陷零件是大规模工业生产的关键环节。本文处理的一个特殊挑战是**冷启动问题**：只用正常（无缺陷）示例图像拟合模型。虽然可以为每个类别手工定制方案，但目标是构建能在许多不同任务上同时良好工作、且自动化的系统。表现最好的方法把 ImageNet 模型的嵌入与一个离群检测模型结合起来。本文沿这条路线推进，提出 **PatchCore**：它使用一个**尽可能具代表性的正常小块特征记忆库**。PatchCore 在检测与定位两方面都达到当时最佳性能，同时推理时间有竞争力。在具挑战性且广泛使用的 MVTec AD 基准上，PatchCore 取得最高 **99.6% 的图像级异常检测 AUROC**，把误差相对次优方法减少了一半以上。我们还在另外两个数据集上报告了有竞争力的结果，并在**小样本**情形下同样有竞争力。

**我的归纳**
- 三个部件：**冻结的 ImageNet 骨干**（WRN-50，取中间层）→ **小块特征** → **记忆库 + 最近邻距离**。
- 关键技巧是**核心集选择**（贪心 k-中心，`approx_greedy_coreset`，比例 p=0.1）：用 10% 的代表性 patch 近似整库检索。
- 图像分数 = 全部小块分数取**最大**；论文另有**重加权**（用最近邻的 softmax 权重）改善定位。
- 代码：`github.com/amazon-research/patchcore-inspection`（注意 README 里的仓库地址与当前 `amazon-science/patchcore-inspection` 指向同一项目）。

**与你项目的关系**
- 你的**第一个基线**，也是"压缩"这个动作的源头：核心集把库压到 10%。
- **关键区分（必须写进笔记）**：官方 PatchCore 的**重加权分数不被 max-score 的区间证明覆盖**；你的参考检测器要另起名字，例如 `max-score reference detector`（冻结特征 + 欧氏最近距离 + 最大小块分数）。两者永远不混表。

**该精读哪几节**：Method（特征提取、核心集、打分）、Experimental Protocol。
**要能回答**：为什么**丢掉参考点会让最近邻距离变大**？

---

## R2 · AnomalyDINO: Boosting Patch-based Few-shot Anomaly Detection with DINOv2

**作者**：Simon Damm, Mike Laszkiewicz, Johannes Lederer, Asja Fischer ｜ **出处**：WACV 2025 ｜ **本地**：`R2_anomalydino_WACV2025.pdf`（11 页）

**原文（摘要）**
> Recent advances in multimodal foundation models have set new standards in few-shot anomaly detection. This paper explores whether high-quality visual features alone are sufficient to rival existing state-of-the-art vision-language models. We affirm this by adapting DINOv2 for one-shot and few-shot anomaly detection, with a focus on industrial applications. We show that this approach does not only rival existing techniques but can even outmatch them in many settings. Our proposed vision-only approach, AnomalyDINO, follows the well-established patch-level deep nearest neighbor paradigm, and enables both image-level anomaly prediction and pixel-level anomaly segmentation. The approach is methodologically simple and training-free and, thus, does not require any additional data for fine-tuning or meta-learning. Despite its simplicity, AnomalyDINO achieves state-of-the-art results in one- and few-shot anomaly detection (e.g., pushing the one-shot performance on MVTec-AD from an AUROC of 93.1% to 96.6%).

**中译**
> 多模态基础模型的最新进展为小样本异常检测设定了新标准。本文探究一个更基础的问题：**仅靠高质量的视觉特征，是否足以与现有的视觉—语言模型抗衡？** 我们给出了肯定回答：把 **DINOv2** 适配到单样本与小样本异常检测，并聚焦工业应用。我们表明这种做法不仅能与现有技术匹敌，在许多设定下甚至更好。我们提出的纯视觉方法 **AnomalyDINO** 沿用成熟的**小块级深度最近邻**范式，同时支持**图像级异常预测**与**像素级异常分割**。该方法在方法学上简单且**免训练**，因此不需要额外数据做微调或元学习。即便如此简单，AnomalyDINO 在单样本与小样本异常检测上仍取得最佳结果（例如把 MVTec-AD 的单样本性能从 AUROC 93.1% 提升到 96.6%）。

**我的归纳**
- 只用**冻结的 DINOv2 特征** + 小块最近邻检索，**不训练**。
- 三种配置值得注意：one-shot / few-shot /（批量）zero-shot；handout 让你先跳过批量零样本。
- 图像分数用**顶部尾部平均**（论文里是 patch 距离的 top-1% 平均），而不是简单最大值——这一点对你的区间论证很关键。

**与你项目的关系**
- 你的**第二个基线**（等量参考图像访问的对照）。
- **区间论证的边界**：`max` 是逐坐标单调的，所以 `L ≤ s ≤ U` 可直接推到图像分数；**顶部尾部平均**要成立需要额外的单调性审计（handout A8 明确说了"其距离变换与预处理必须审计"）。

**该精读哪几节**：Method、few-shot 分类体系、预处理与分数聚合。
**要能回答**：为什么"顶部尾部平均"不能想当然地套用 max 的区间结论？

---

## R3 · EfficientAD: Accurate Visual Anomaly Detection at Millisecond-Level Latencies

**作者**：Kilian Batzner, Lars Heckler, Rebecca König ｜ **出处**：WACV 2024, pp. 128–138 ｜ **本地**：`R3_efficientad_WACV2024.pdf`（11 页）

**原文（摘要）**
> Detecting anomalies in images is an important task, especially in real-time computer vision applications. In this work, we focus on computational efficiency and propose a lightweight feature extractor that processes an image in less than a millisecond on a modern GPU. We then use a student–teacher approach to detect anomalous features. We train a student network to predict the extracted features of normal, i.e., anomaly-free training images. The detection of anomalies at test time is enabled by the student failing to predict their features. We propose a training loss that hinders the student from imitating the teacher feature extractor beyond the normal images. It allows us to drastically reduce the computational cost of the student–teacher model, while improving the detection of anomalous features. We furthermore address the detection of challenging logical anomalies that involve invalid combinations of normal local features, for example, a wrong ordering of objects. We detect these anomalies by efficiently incorporating an autoencoder that analyzes images globally. We evaluate our method, called EfficientAD, on 32 datasets from three industrial anomaly detection dataset collections.

**中译**
> 图像异常检测是一项重要任务，在实时计算机视觉应用中尤其如此。本文聚焦**计算效率**，提出一个轻量特征提取器，在现代 GPU 上处理一张图**不到 1 毫秒**。随后我们用**学生—教师**方法检测异常特征：训练学生网络去预测**正常**（无异常）训练图像被教师提取出的特征；测试时，学生"预测失败"就说明有异常。我们提出一种训练损失，**阻止学生在正常图像之外模仿教师**，这使我们能大幅降低学生—教师模型的计算开销，同时改善异常特征检测。我们进一步处理具有挑战性的**逻辑异常**——即正常局部特征的非法组合（例如物体顺序错误）：通过高效地引入一个**自编码器**做全局图像分析来检测。我们在来自三个工业异常检测数据集集合的 **32 个数据集**上评估了 EfficientAD。

**我的归纳**
- 关键点：这是一个**小型学习型检测器**，与"小型检索库"完全不同的路线。
- 时延口径：「现代 GPU 上单图 <1 ms」指的是**特征提取器**，不是端到端系统；报效率时必须把骨干运行时与训练成本都算进去。
- 逻辑异常（部件错位/顺序错）靠自编码器全局分析。

**与你项目的关系**
- A10 的基线 (g)：**质量/效率对照**。你的成本前沿图（图 3）必须包含它。
- 陷阱：**"小检索库"与"小模型"不是一回事**。你的方案省的是**库内存与整库查询**，不省编码器；报告时必须把编码器内存单列（handout A6 明确要求）。

**该精读哪几节**：Method 与**时延测量协议**。
**要能回答**：为什么骨干网络运行时与训练成本都必须计入效率对比？

---

## R4 · The MVTec AD 2 Dataset: Advanced Scenarios for Unsupervised Anomaly Detection

**作者**：Lars Heckler-Kram, Jan-Hendrik Neudeck, Ulla Scheler, Rebecca König, Carsten Steger ｜ **出处**：IJCV 134(4), 2026 · DOI 10.1007/s11263-026-02743-0 ｜ **本地**：`R4_mvtec_ad2_IJCV2026.pdf`（32 页）

**原文（摘要）**
> In recent years, performance on existing anomaly detection benchmarks like MVTec AD and VisA has started to saturate in terms of segmentation AU-PRO, with state-of-the-art models often competing in the range of less than one percentage point. This lack of discriminatory power prevents a meaningful comparison of models and thus hinders progress of the field, especially when considering the inherent stochastic nature of machine learning results. We present the MVTec AD 2 dataset, a collection of advanced anomaly detection scenarios with more than 8000 high-resolution images from eight object categories. It comprises challenging and highly relevant industrial inspection use cases that have not been considered in previous datasets, including transparent and overlapping objects, dark-field and backlight illumination, objects with high variance in the normal data, and extremely small defects. We provide comprehensive evaluations of state-of-the-art methods and show that their performance remains below 60% average AU-PRO. Additionally, our dataset provides test scenarios with lighting condition changes to assess the robustness of methods under real-world distribution shifts.

**中译**
> 近年来，MVTec AD、VisA 等既有异常检测基准在**分割 AU-PRO** 上的性能开始**饱和**，最先进模型之间的差距常常小于一个百分点。这种区分度的缺失使模型之间无法做有意义的比较，从而阻碍领域进展——尤其在考虑机器学习结果**固有的随机性**时。我们提出 **MVTec AD 2** 数据集：它是一组进阶的异常检测场景，包含来自 8 个物体类别的 **8000 多张高分辨率图像**。它涵盖了此前数据集未考虑、但工业检测中极具挑战且高度相关的用例，包括**透明与重叠物体、暗场与背光照明、正常数据方差很大的物体，以及极小的缺陷**。我们对最先进方法做了全面评估，表明它们的性能**仍低于 60% 的平均 AU-PRO**。此外，我们的数据集提供**照明条件变化**的测试场景，用于评估方法在真实分布位移下的鲁棒性。

**我的归纳**
- 这个数据集的**卖点就是"现有基准饱和了"**：老基准上差 1 个百分点说明不了问题。
- 四类新难点：透明/重叠、暗场/背光、正常样本高方差、极小缺陷。
- 提供**真实光照变化**的测试场景（不是合成的）。
- 有公开评测服务器（handout 让你在本地协议冻结前先别碰）。

**与你项目的关系**
- **主基准**（handout A10：主结果用 AD 2 公开测试部分）。你的"≥2 个百分点分歧"判据要落在这里。
- handout 明确要求：**合成光照变化不能替代真实位移**。AD 2 的自然光照条件是你的 RQ4 的关键材料。
- 低 FPR 定位评估（AU-PRO）是官方口径，别自己换指标。

**该精读哪几节**：场景设置、train/validation/test 角色、光照变化、低 FPR 定位评估。
**要能回答**：为什么合成光照扰动不能替代 AD 2 的真实光照变化？

---

## R6 · SPARC: Subspace Position-Aware Robust Few-Shot Calibration for Distribution-Shifted Industrial Anomaly Detection

**作者**：Seokhee Han, Seungjun Chu, Mateusz Nowak, Peter Chin ｜ **出处**：arXiv:2608.18585, 2026 · CC BY 4.0 ｜ **本地**：`R6_sparc_arXiv2608.18585.pdf`（36 页）

**原文（摘要）**
> Vision-based industrial anomaly detectors are calibrated on one distribution but may be deployed on another that differs in illumination, fixture placement, or sensor characteristics, sharply degrading an otherwise accurate detector. Adapting to the incoming lot is a natural response, but labeled anomalies are scarce. We therefore consider calibration using only a handful of verified-normal images available before scoring the rest of the lot. Existing fixes require backpropagation, detector-specific tuning, or choices about feature directions that few calibration samples cannot justify. We present SPARC, a few-shot calibration method that intercepts patch features between encoder and detector and removes a closed-form, spatially indexed estimate of deployment-time nuisance through per-cell subspace projection. It needs only k ≤ 8 verified-normal images and uses the algebraic saturation rank r = k−1 on the encoder's native patch grid. The correction requires no gradient or weight updates and works with memory-bank, density, prototype, and mutual detectors.

**中译**
> 基于视觉的工业异常检测器在一个分布上完成校准，却可能被部署到另一个在**照明、夹具位置或传感器特性**上不同的分布，使原本准确的检测器性能急剧下降。**适应新到的批次**是自然反应，但带标签的异常样本很稀缺。因此我们考虑：在给该批次其余样本打分之前，**只用少量"已验证正常"的图像做校准**。已有的修正方案需要反向传播、检测器特定的调参，或涉及特征方向的选择——而这些是少量校准样本**无法支撑**的。我们提出 **SPARC**：一种小样本校准方法，它在**编码器与检测器之间拦截小块特征**，通过**逐单元子空间投影**移除对部署期干扰的**闭式、带空间索引的估计**。它只需要 **k ≤ 8 张已验证正常图**，并使用编码器原生小块网格上的**代数饱和秩 r = k−1**。该校正不需要梯度或权重更新，可用于记忆库型、密度型、原型型与互检测器。

**我的归纳**
- 定位：**在编码器与检测器之间插一层校正**，不改变检测器本身。
- 三个卖点：只需 ≤8 张已验证正常图；**闭式解、无需梯度**；与多类检测器兼容。
- `r = k−1` 是"用 k 张图能可靠估计的子空间维数上限"这一代数事实的直接用法。
- handout 说：本次检索**未确认到可归属的官方仓库**。

**与你项目的关系**
- A10 的**位移场景对照**（在数据假设与代码能对齐时）。
- **核心差别（必须写清楚）**：SPARC **改变特征**以在位移下检测得更好；你的问题是**证明与一个冻结参考系统的决策一致**。前者可以"更准"，后者回答"是否还和原来一样"——**保持一致性不等于正确性**，这正是 handout 反复强调的。
- 若你发现"位移下参考质量"是主要失效原因，A11 的退路就是在等量数据访问下评估 SPARC 风格校正（那会变成另一个研究问题，需重新做新颖性核查）。

**该精读哪几节**：Method、数据角色（k 张已验证正常图）、等量校准控制、消融。

---

# 二、正文引用的四篇（A4 / A10 要用）

## R8 · Calibration-Preserving Pruning: Compression as a Reliability Contract

**作者**：Ibne Farabi Shihab, Adria Binte Habib, Anuj Sharma ｜ **出处**：arXiv:2608.23744, 2026-08-24 · CC BY 4.0 ｜ **本地**：`R8_calibration_preserving_pruning_arXiv2608.23744.pdf`（14 页）

**原文（摘要）**
> Split conformal prediction, not the pruning rule, supplies finite-sample marginal coverage once a pruned model is fixed independently of the conformal calibration split. We study the separate efficiency problem: can pruning preserve score geometry well enough to obtain smaller valid prediction sets? Calibration-Preserving Pruning (CPP) augments a base pruning score with nonconformity-gradient saliency and uses disjoint pruning, validation-selection, conformal-calibration, and test splits. Bounded score perturbations imply bounded conformal-quantile shifts and controlled set inflation, but do not make the generic coverage theorem CPP-specific. Final five-seed Qwen2.5-1.5B results at 50% sparsity show the largest gains on large-label tasks. On DBpedia-14, CPP-SparseGPT reduces mean set size from 10.1 to 8.6 while changing accuracy from 0.347 to 0.366; CPP-Wanda reduces 11.2 to 9.0 with an accuracy trade-off from 0.310 to 0.295. Matched controls show that generic supervised gradients explain much of the gain.

**中译**
> 一旦剪枝后的模型被固定下来，并且**独立于符合预测的校准划分**，那么提供有限样本边际覆盖的是 **split conformal prediction，而不是剪枝规则本身**。我们研究另一个问题——**效率**：剪枝能否把**分数几何**保持得足够好，从而得到更小的有效预测集？**Calibration-Preserving Pruning (CPP)** 在基础剪枝分数上加入**非一致性梯度显著性**，并使用互不相交的剪枝、验证选择、符合校准与测试四段划分。**有界的分数扰动蕴含有限的符合分位数偏移与受控的集合膨胀**，但这**不会**让通用的覆盖定理变成 CPP 专有。Qwen2.5-1.5B 在 50% 稀疏度下的五种子最终结果显示，收益主要出现在标签数多的任务上：在 DBpedia-14 上，CPP-SparseGPT 把平均集合大小从 10.1 降到 8.6（准确率 0.347→0.366）；CPP-Wanda 把 11.2 降到 9.0（准确率 0.310→0.295，有代价）。**匹配对照实验表明，通用的有监督梯度解释了大部分收益。**

**我的归纳**
- 它的"可靠性"是**符合预测的覆盖与集合大小**，不是"二元报警决策是否一致"。
- 作者自己做了**匹配对照**并承认收益大多可由通用梯度解释——这种自我限制的写法值得学。
- 它管的是**分类 + 剪枝**，不是工业视觉检索库。

**与你项目的关系**
- A4 里的"最接近工作"之一：**它已经研究了压缩与可靠性**，所以你不能声称"通过压缩保持可靠性"是无人做过的概念。
- **你的差异化必须写在这里**：CPP 关心 **符合预测集的覆盖/大小**；你关心**固定阈值下二元报警与冻结整库的一致性**，并额外要求**未决处理与端到端升级代价**。两套"可靠性"不是同一个量。

---

## R9 · Memory Pollution in Multi-Product Visual Anomaly Detection: Diagnosis and Mitigation

**作者**：Sergio Villanueva López, Emilio Soria-Olivas, Manuel Sánchez-Montañés ｜ **出处**：Machine Learning and Knowledge Extraction (MDPI) 8(7):219, 2026 · DOI 10.3390/make8070219 · CC BY 4.0
**状态**：⬜ PDF 需你在浏览器另存（MDPI 拒绝一切脚本访问）；以下摘要取自 Crossref API 登记的官方摘要

**原文（摘要）**
> Memory-bank methods such as PatchCore are widely used in industrial quality control for visual anomaly detection since they require no training, are fast to deploy and achieve strong accuracy. However, they are memory-intensive. Furthermore, a single production line typically involves different products or cameras, so using a single anomaly detection method with a shared nearest-neighbor memory bank is attractive since it simplifies deployment and makes new products easy to add. Nevertheless, embeddings from different products/cameras can interfere during retrieval, causing what we call "memory pollution". In this work, we study this effect through a new diagnostic framework, which involves: (1) a new metric, the wrong-neighbor rate (WNR), which measures how often a query's nearest neighbor belongs to a different product; (2) an empirically validated phenomenon, "oracle inversion", where querying only the product's own data can underperform the shared bank under a fixed memory budget; (3) a first-order analytical model of the WNR, which predicts how pollution grows with product count and memory budget; and (4) a minimal training-free router that removes the effect of memory pollution. Our results show that our system performs robustly across different datasets and backbones, with up to 25× memory reduction.

**中译**
> 像 PatchCore 这样的**记忆库方法**在工业质检的视觉异常检测中被广泛使用，因为它们无需训练、部署快、精度高；但它们**内存开销大**。而且一条产线通常涉及不同的产品或相机，因此"用单一异常检测方法 + 一个共享的最近邻记忆库"很有吸引力——它简化部署，也让新增产品更容易。然而，来自不同产品/相机的嵌入**在检索时会互相干扰**，造成我们称之为"**记忆污染**"的现象。本文通过一个新的诊断框架研究该效应，包含四部分：(1) 一个新指标 **wrong-neighbor rate (WNR)**，衡量查询的最近邻**属于另一个产品**的频率；(2) 一个经经验验证的现象"**oracle inversion**"——在固定内存预算下，只用产品自身数据查询的性能**可能低于**共享库；(3) WNR 的**一阶解析模型**，预测污染如何随产品数量与内存预算增长；(4) 一个极简的**免训练路由器**，消除记忆污染的影响。结果表明我们的系统在不同数据集与骨干网络上表现稳健，最高实现 **25× 内存缩减**。

**我的归纳**
- 它和你的题目**最像**：同样是"压缩检索库 + 出问题时路由/回退"。
- 但它的问题设定是**多产品共享一个库**导致的**跨产品污染**（检索到别的产品的邻居），并用路由器把查询分派到产品自己的库。
- 它的核心量是 **WNR**（检索层面的错误率），不是**报警决策层面的分歧**。

**与你项目的关系（Gate 5 新颖性复查的关键弹药）**
- 你必须能一句话说清区别：**"它测的是最近邻是否跨产品（检索正确性），我测的是固定阈值下的二元报警是否与冻结整库一致（决策一致性），并要求未决时不得静默降级。"**
- 它的 25× 内存缩减是你**资源维度上的对照数字**，但注意它没有报告"报警一致性"，所以不能直接对比。

---

## R10 · A new near-linear time algorithm for k-nearest neighbor search using a compressed cover tree

**作者**：Yury Elkin, Vitaliy Kurlin ｜ **出处**：ICML 2023, PMLR 202:9267–9311 ｜ **本地**：`R10_elkin_kurlin_compressed_cover_tree_ICML2023.pdf`（45 页）

**原文（摘要）**
> Given a reference set R of n points and a query set Q of m points in a metric space, this paper studies an important problem of finding k-nearest neighbors of every point q ∈ Q in the set R in a near-linear time. In the paper at ICML 2006, Beygelzimer, Kakade, and Langford introduced a cover tree on R and attempted to prove that this tree can be built in O(n log n) time while the nearest neighbor search can be done in O(n log m) time with a hidden dimensionality factor. This paper fills a substantial gap in the past proofs of time complexity by defining a simpler compressed cover tree on the reference set R. The first new algorithm constructs a compressed cover tree in O(n log n) time. The second new algorithm finds all k-nearest neighbors of all points from Q using a compressed cover tree in time O(m(k + log n) log k) with a hidden dimensionality factor depending on point distributions of the given sets R, Q but not on their sizes.

**中译**
> 给定度量空间中的参考集 R（n 个点）与查询集 Q（m 个点），本文研究一个重要问题：在**近线性时间**内为 Q 中每个点 q 找到其在 R 中的 k 个最近邻。在 ICML 2006 的论文中，Beygelzimer、Kakade 与 Langford 在 R 上引入了**覆盖树**，并试图证明该树可在 O(n log n) 时间内构建、最近邻搜索可在 O(n log m) 时间内完成（含一个隐藏的维数因子）。本文通过在被引用的集合 R 上定义一个更简单的**压缩覆盖树**，**填补了以往时间复杂度证明中的一个实质性缺口**。第一个新算法在 O(n log n) 时间内构建压缩覆盖树；第二个新算法用压缩覆盖树在 O(m(k+log n)log k) 时间内找出 Q 中所有点的全部 k 个最近邻，其隐藏维数因子**只依赖给定集合 R、Q 的点分布，而不依赖它们的规模**。

**我在 PMLR 页面核实的背景（这段与 handout 的说法一致）**
> 2015 年 Curtin 的博士论文第 5.3 节指出，后一个主张（查询复杂度）的证明可能存在严重缺口；TopoInVis 2022 的一篇论文报告了这两个主张证明中关键步骤的**显式反例**。

**与你项目的关系**
- **不要借用 R7 的对数复杂度**：handout A9 明确要求"在没有验证假设的情况下不要借用树的复杂度"，出处就是这里。
- 第 6 周你要对比"精确树基线"时，**引用 R10 而不是 R7**，并说明你的对照是**可执行的实现**，不是理论复杂度。

---

## R11 · FastRef: Fast Prototype Refinement for Few-shot Industrial Anomaly Detection

**作者**：Yufei Li, Long Tian, Yuyang Dai, Wenchao Chen, Liang Bao, Xiyang Liu ｜ **出处**：CVPR 2026, pp. 43040–43049 ｜ **本地**：`R11_fastref_CVPR2026.pdf`（10 页）

**原文（摘要）**
> Few-shot industrial anomaly detection (FS-IAD) presents a critical challenge for practical automated inspection systems operating in data-scarce environments. While existing approaches predominantly focus on obtaining prototypes from limited normal images, they neglect to systematically incorporate statistics of query image to enhance prototype representativeness. To address this issue, we propose FastRef, a novel and efficient prototype refinement framework for FS-IAD. Our method operates through an iterative two-stage process during inference: (1) characteristic transfer from query features to the enhanced prototypes, and (2) anomaly suppression by aligning the enhanced prototypes with their normal counterparts. The characteristic transfer is achieved through linear reconstruction of query features from prototypes with an optimizable transport matrix, while the anomaly suppression addresses a key observation in FS-IAD that unlike conventional IAD with abundant normal images, the limited-sample setting makes anomaly reconstruction more probable in characteristic transfer. Therefore, we employ optimal transport to measure while minimize the gap between prototypes and their enhanced counterparts.

**中译**
> 小样本工业异常检测（FS-IAD）对在**数据稀缺环境**中运行的实际自动检测系统是一个关键挑战。现有方法主要关注"如何从有限的正常图像得到原型"，却**忽视了系统性地利用查询图像本身的统计量来提升原型的代表性**。为此我们提出 **FastRef**：一个面向 FS-IAD 的新颖且高效的原型精化框架。我们的方法在**推理期**通过一个迭代的两阶段过程运行：(1) 把查询特征**迁移**到增强原型上；(2) 通过把增强原型与其**正常对应物对齐**来**抑制异常**。特征迁移通过"用原型对查询特征做线性重构"实现，其中含一个**可优化的传输矩阵**；而异常抑制针对 FS-IAD 中的一个关键观察：与传统拥有充足正常图像的 IAD 不同，**样本极少时特征迁移更容易把异常也重构进去**。因此我们用**最优传输**度量并最小化原型与其增强对应物之间的差距。

**我的归纳**
- 关键区别：**传统小样本方法只从正常图造原型；FastRef 在推理时把测试图的统计量也吸收进去**——这就是"查询自适应"。
- 它把自己插在 PatchCore / WinCLIP / AnomalyDINO 之上，在 MVTec / VisA / MPDD / RealIAD 的 1/2/4-shot 上评估。

**与你项目的关系（A10 明确警告过）**
- FastRef 提供的是**质量背景**；**它的查询自适应会改变固定参考**，因此**不能悄悄塞进你的区间证明**。
- 引用它的正确姿势："在相同参考预算下，它的小样本质量高于我们复现的固定参考检测器；但它改变了参考系统，因此不适用于'与冻结整库一致'这个问题。"

---

# 三、读懂 A5 的路线图（把六篇串起来）

```
R7  为什么"球内含参考点"能给出距离下界          ← 你的区间论证的几何地基
 │   （但它的复杂度证明有缺口，见 R10）
 ▼
R1  PatchCore：正常小块记忆库 + 核心集压缩 + 最近邻距离 + 最大分数
 │   ← 你的第一个基线；也是"压缩"这个动作的来源
 ▼
R2  AnomalyDINO：同一个检索范式，换成冻结 DINOv2，免训练，小样本 SOTA
 │   ← 第二个基线；它的"顶部尾部平均"需要单独的单调性审计
 ▼
R3  EfficientAD：完全不同的路线（小学学习型检测器 <1ms）
 │   ← 效率对照；提醒你"小库"≠"小模型"，编码器内存必须单列
 ▼
R4  MVTec AD 2：老基准饱和了，新场景包含光照变化与极小缺陷
 │   ← 你的主基准；也是"为什么还要做这个题"的现实理由
 ▼
R6  SPARC：位移下用 ≤8 张已验证正常图做闭式特征校正
 │   ← 位移对照；它让检测"更准"，你问的是"是否还与冻结参考一致"
 ▼
R8/R9  最接近的两个工作：压缩↔可靠性(R8)、压缩检索↔路由回退(R9)
        ← Gate 5 新颖性复查时必须逐条说明差别
```

**读完这六篇后你应该能回答（handout A5 的学习产出）**
1. 什么是**正常参考**？——一组从正常图提取的 patch 特征及其检索结构。
2. **压缩改变了什么**？——丢掉了参考点，最近邻距离**只会变大**，因此靠近阈值的样本可能被推过阈值。
3. **界限究竟保证了什么**？——保证真值落在 `[L, U]` 内，**不保证**区间一定给出结论；跨阈值就必须升级。
4. **为什么报警阈值 ≠ AUROC**？——AUROC 是全局排序指标，与阈值无关；部署关心的是**某一个固定阈值下的二元决策**。
5. 如何在不使用留出缺陷标签的前提下检验系统主张？——阈值只用校准正常样本定；缺陷标签只在协议冻结后用于**报告**。

---

## 附：我怎么核对原文的（可复现）

```powershell
# 1) 抽取文本（默认前 3 页；--all 抽全文）
python scripts\lit_extract.py
# 2) 英文原文就在 literature\txt\*.txt，可直接检索某个概念的出处
Select-String -Path F:\research\literature\txt\R1_patchcore_CVPR2022.txt -Pattern 'coreset'
# 3) 引用登记与哈希
type F:\research\literature\SOURCES.md
```

**引用纪律**：本文档的「中译」段可放心引用（逐句对应原文）；「我的归纳」段是提炼，写进论文前请回到 `literature/txt/` 核对原句。
