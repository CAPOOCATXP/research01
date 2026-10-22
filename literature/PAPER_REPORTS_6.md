# 论文报告（A5 六篇必读 · 中英文）

**读者**：导师 / 组会 · **目的**：每篇给出「问题—方法—结果—局限—与本项目关系」的结构化报告（英文 + 中文）
**依据**：`literature/SOURCES.md`（来源与哈希）、`literature/txt/`（抽取原文，可 grep 核对）

> 英文段是与原文一致的要点归纳（非逐句翻译）；中文段是同一结构的报告体。
> 逐句译文见 `literature/ABSTRACTS_ZH.pdf`。

---

## R7 · Cover Trees for Nearest Neighbor (ICML 2006)

**Authors**: A. Beygelzimer, S. Kakade, J. Langford ｜ **Pages**: 13 ｜ **File**: `R7_cover_trees_ICML2006.pdf`

**Report (EN)**
- **Problem.** Exact nearest-neighbour search in general n-point metric spaces, where no vector-space structure is available, so worst-case linear scan is the only general baseline.
- **Method.** A levelled tree in which each node "covers" its children within a geometrically shrinking radius; the level assignment guarantees that nodes at the same level are separated by a factor of two, which makes triangle-inequality pruning effective.
- **Results.** O(n) space independent of the metric; construction O(c⁶ n log n) and query O(c¹² log n) under an expansion constant c > 2; measured 1–2000× speed-up over brute force on ML datasets.
- **Limits.** The complexity bounds are conditional on the expansion constant and the original proofs were later shown to contain a gap (see R10); the speed-ups are empirical, not guaranteed.
- **Relevance.** Supplies the metric argument behind our interval: a ball containing reference points yields a *lower* bound on the distance to the reference set. It is also the source of the warning against borrowing logarithmic complexity without checking assumptions.

**报告（中）**
- **问题**：一般 n 点度量空间中的精确最近邻搜索；没有向量空间结构可用，通用基线只有线性扫描。
- **方法**：分层树，每个节点在几何收缩的半径内「覆盖」子节点；层间距离保证同层点相隔两倍因子，使三角不等式剪枝有效。
- **结果**：空间 O(n)、与度量无关；在扩张常数 c>2 时构建 O(c⁶n log n)、查询 O(c¹²log n)；在机器学习数据集上相对暴力搜索实测 1–2000× 加速。
- **局限**：复杂度依赖扩张常数；原始证明后来被发现存在缺口（见 R10）；加速是经验性的，不是保证。
- **与本项目关系**：提供区间论证的度量几何依据——「球内含参考点 ⇒ 参考集距离的下界」。同时是「不验证假设就不要借用对数复杂度」这一警告的出处。

---

## R1 · Towards Total Recall in Industrial Anomaly Detection (CVPR 2022)

**Authors**: K. Roth, L. Pemula, J. Zepeda, B. Schölkopf, T. Brox, P. Gehler ｜ **Pages**: 11 ｜ **File**: `R1_patchcore_CVPR2022.pdf`

**Report (EN)**
- **Problem.** Cold-start industrial inspection: fit a detector from nominal images only, and generalise across many categories without per-class handcrafting.
- **Method.** Frozen ImageNet backbone → patch embeddings → a *maximally representative memory bank* of nominal patches (greedy coreset, p = 0.1) → nearest-neighbour distance as the patch score; image score is the maximum patch score, with an optional re-weighting by the softmax over nearest neighbours.
- **Results.** Up to 99.6% image-level AUROC on MVTec AD (more than halving the error of the next best method), competitive inference time, competitive few-shot behaviour.
- **Limits.** The bank grows with the number of nominal patches; the re-weighting makes the image score a non-monotone function of individual patch distances; the protocol is AUROC-based, i.e. threshold-free.
- **Relevance.** Our first baseline and the origin of the "compression" action (coreset to 10%). Critically, the re-weighted score is **not** covered by our max-score interval argument, so our reference detector is named separately as a max-score reference detector.

**报告（中）**
- **问题**：冷启动工业检测——只用正常图像拟合，并要求跨多个类别通用而不做逐类手工设计。
- **方法**：冻结的 ImageNet 骨干 → 小块嵌入 → **具代表性的正常小块记忆库**（贪心核心集，p=0.1）→ 用最近邻距离作小块分数；图像分数取小块最大值，可选地按最近邻的 softmax 重加权。
- **结果**：MVTec AD 图像级 AUROC 最高 99.6%（把次优方法的误差减少一半以上），推理时间有竞争力，小样本情形同样有竞争力。
- **局限**：库随正常小块数增长；重加权会让图像分数不再是各小块距离的单调函数；协议是 AUROC 口径，即**与阈值无关**。
- **与本项目关系**：本项目的第一个基线，也是"压缩"这个动作的来源（核心集到 10%）。**关键**：重加权分数**不被**我们的最大分数区间论证覆盖，因此参考检测器另行命名为 max-score reference detector。

---

## R2 · AnomalyDINO (WACV 2025)

**Authors**: S. Damm, M. Laszkiewicz, J. Lederer, A. Fischer ｜ **Pages**: 11 ｜ **File**: `R2_anomalydino_WACV2025.pdf`

**Report (EN)**
- **Problem.** Do high-quality *visual* features alone suffice for few-shot anomaly detection, without vision-language models or fine-tuning?
- **Method.** Frozen DINOv2 features, patch-level deep nearest neighbour, training-free; supports one-shot, few-shot and batched zero-shot; image score aggregates the upper tail of patch distances (top-1% mean).
- **Results.** State of the art in one-/few-shot settings; one-shot MVTec-AD AUROC improves from 93.1% to 96.6%; simple and deployment-friendly.
- **Limits.** Requires a foundation-model encoder (ViT-S/14), which is itself large for an edge target; the top-tail aggregation is not a simple maximum, so monotonicity arguments must be re-derived.
- **Relevance.** Our second baseline with equal reference-image access. Its top-tail average is *not* automatically covered by a max-score bound; the handout requires auditing its distance transform and preprocessing before reusing our interval argument.

**报告（中）**
- **问题**：不借助视觉—语言模型、也不微调，仅靠高质量**视觉**特征能否胜任小样本异常检测？
- **方法**：冻结 DINOv2 特征 + 小块级深度最近邻，免训练；支持单样本、小样本与批量零样本；图像分数聚合小块距离的**上尾**（top-1% 均值）。
- **结果**：单样本/小样本达到最佳；MVTec-AD 单样本 AUROC 从 93.1% 提升到 96.6%；方法简单、易部署。
- **局限**：需要基础模型编码器（ViT-S/14），对边缘目标本身偏大；上尾聚合不是简单最大值，单调性论证需重新推导。
- **与本项目关系**：第二个基线（等量参考图像访问）。其 top-tail 平均**不能**直接套用最大分数的区间结论；handout 要求先审计其距离变换与预处理。

---

## R3 · EfficientAD (WACV 2024)

**Authors**: K. Batzner, L. Heckler, R. König ｜ **Pages**: 11 ｜ **File**: `R3_efficientad_WACV2024.pdf`

**Report (EN)**
- **Problem.** Real-time anomaly detection where inference latency dominates; existing student–teacher models are accurate but expensive.
- **Method.** A lightweight feature extractor (<1 ms per image on a modern GPU) plus a student–teacher scheme; a training loss prevents the student from imitating the teacher outside normal data; a small autoencoder handles logical anomalies (invalid combinations of normal local features).
- **Results.** Evaluated on 32 datasets from three industrial collections, with millisecond-level latency and accuracy competitive with far heavier models.
- **Limits.** The "<1 ms" refers to the feature extractor, not the end-to-end system; the model must be trained per category; it is a learned detector, not a retrieval system, so memory accounting differs.
- **Relevance.** The efficiency comparator in our cost frontier (A10 item g). It forces us to report encoder runtime and training cost separately, and to distinguish "small learned detector" from "small retrieval bank".

**报告（中）**
- **问题**：推理时延占主导的实时异常检测；既有学生—教师模型准确但昂贵。
- **方法**：轻量特征提取器（现代 GPU 上单图 <1 ms）+ 学生—教师结构；训练损失阻止学生在正常数据之外模仿教师；另用小型自编码器处理逻辑异常（正常局部特征的非法组合）。
- **结果**：在来自三个工业数据集集合的 32 个数据集上评估，达到毫秒级时延且精度可与重得多的模型竞争。
- **局限**："<1 ms" 指特征提取器而非端到端系统；需按类别训练；它是学习型检测器而非检索系统，内存口径不同。
- **与本项目关系**：成本前沿中的效率对照（A10 第 g 项）。它迫使我们**分别**报告编码器运行时与训练成本，并区分「小学学习型检测器」与「小检索库」。

---

## R4 · The MVTec AD 2 Dataset (IJCV 2026)

**Authors**: L. Heckler-Kram, J.-H. Neudeck, U. Scheler, R. König, C. Steger ｜ **Pages**: 32 ｜ **File**: `R4_mvtec_ad2_IJCV2026.pdf`

**Report (EN)**
- **Problem.** Existing benchmarks (MVTec AD, VisA) have saturated: top methods differ by less than one AU-PRO point, so comparisons are no longer discriminating.
- **Method.** A new collection of >8000 high-resolution images across eight object categories, with scenarios absent from earlier datasets: transparent and overlapping objects, dark-field and backlight illumination, high variance in normal data, and extremely small defects; includes test scenarios with lighting changes and a public evaluation server.
- **Results.** State-of-the-art methods remain below 60% average AU-PRO on this benchmark, i.e. there is substantial headroom.
- **Limits.** Requires registration; the private test server means a frozen local protocol first; the non-commercial licence constrains deployment claims.
- **Relevance.** Our main harder benchmark. It is also the empirical justification for the project: because AUROC-type scores saturate, a threshold-level reliability question becomes the interesting one.

**报告（中）**
- **问题**：MVTec AD、VisA 等既有基准已饱和——最优方法之间差距不足一个 AU-PRO 点，比较失去区分度。
- **方法**：新的数据集，8 个物体类别、8000+ 高分辨率图像，包含此前数据集没有的场景：透明与重叠物体、暗场与背光照明、正常数据高方差、极小缺陷；提供光照变化的测试场景与公开评测服务器。
- **结果**：最先进方法在该基准上平均 AU-PRO **仍低于 60%**，说明仍有大量提升空间。
- **局限**：需登记；私有测试服务器要求先冻结本地协议；非商用许可限制部署主张。
- **与本项目关系**：主基准（更难的那个）。它也是本项目的现实理由：**AUROC 类指标饱和后，阈值层面的可靠性问题才变得有意义**。

---

## R6 · SPARC (arXiv 2026)

**Authors**: S. Han, S. Chu, M. Nowak, P. Chin ｜ **Pages**: 36 ｜ **File**: `R6_sparc_arXiv2608.18585.pdf`

**Report (EN)**
- **Problem.** Detectors calibrated on one distribution degrade on another (illumination, fixture placement, sensor); labelled anomalies are unavailable, so only a handful of verified-normal images from the incoming lot can be used.
- **Method.** Intercept patch features between encoder and detector; estimate deployment-time nuisance in a closed form, spatially indexed per cell, and remove it by per-cell subspace projection; uses the algebraic saturation rank r = k−1 with k ≤ 8 verified-normal images; no gradients, no weight updates.
- **Results.** Improves pooled Image AUROC and AU-PRO0.3 across seven detectors on shift-prone benchmarks, and is compatible with memory-bank, density, prototype and mutual detectors.
- **Limits.** It modifies features, so the resulting detector is no longer the frozen reference; the correction assumes the nuisance is approximately low-rank and spatially smooth; no attributable official repository was confirmed.
- **Relevance.** The shift comparator (A10). The key distinction for our novelty claim: SPARC makes the detector *more accurate* under shift, whereas we certify whether the *decisions of a frozen reference system are preserved*. Preservation is not correctness.

**报告（中）**
- **问题**：在一个分布上校准的检测器，换到另一个分布（照明、夹具、传感器）会退化；而带标签异常不可得，只能用在批次内少量「已验证正常」图像。
- **方法**：在编码器与检测器之间拦截小块特征；以**闭式、按 cell 空间索引**的方式估计部署期干扰，再用**逐 cell 子空间投影**移除；利用代数饱和秩 r = k−1，只需 k ≤ 8 张已验证正常图；不需要梯度或权重更新。
- **结果**：在易发生位移的基准上，对 7 个检测器的 pooled Image AUROC 与 AU-PRO0.3 均有提升；兼容记忆库型、密度型、原型型与互检测器。
- **局限**：它**修改特征**，因此结果不再是那个冻结参考；校正假设干扰近似低秩且空间平滑；未确认到可归属的官方仓库。
- **与本项目关系**：位移场景的对照（A10）。新颖性主张的关键区别：SPARC 让检测器**更准**，而我们证明的是**冻结参考系统的决策是否被保持**。**保持一致性不等于正确性。**

---

## 附：六篇之间的关系（一段话）

R7 给出距离下界的几何工具；R1 与 R2 是同一个「正常小块检索」范式的两个最强实例（R1 用 WRN-50 + 核心集，R2 用冻结 DINOv2 + 上尾聚合）；R3 代表完全不同的效率路线，迫使我们在成本里计入编码器；R4 说明为什么 AUROC 层面的比较已经饱和，从而把问题推到阈值层面；R6 处理位移，但改变的是特征而不是决策一致性。**本项目占据的位置**：固定检测器与阈值，测量压缩导致的二元决策分歧，并给出「确定正常 / 确定报警 / 升级查询」的可审计流程。
