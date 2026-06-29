# 08-Embedding 嵌入

> 学完这篇要知道：token/word/sentence embedding 三种概念、contrastive learning 怎么训出来的、生产选型看什么不看什么。

---

## Embedding 解决什么

计算机不认识"苹果"和"梨"是近亲——它们是两个没关系的字符串。Embedding 把每个词/句/文档映射成 d 维稠密向量，让 **"语义相似 → 向量距离近"**。

经典例子：`v("国王") - v("男人") + v("女人") ≈ v("女王")`

---

## 三个层次别搞混

| 层次 | 指的是 | 例子 |
|------|--------|------|
| Token Embedding | LLM 内部 embedding 层，词表 × d 矩阵 | GPT 的输入层查表 |
| Word Embedding（历史） | word2vec/GloVe 每个词一个固定向量 | 不管上下文"苹果"都是一个向量 |
| Sentence Embedding（今天 RAG 用的） | 整段文本 → 一个固定向量 | BGE/E5/text-embedding-3 |

面试官最爱问："LLM 的 hidden state 能不能当 sentence embedding 用？"——答案是**不行**。decoder-only LLM 的训练目标是 next token，hidden state 偏重最后一两个词，不是全句语义。要用专门 contrastive 训出来的 BGE/E5 这类。

---

## Contrastive Learning 怎么训 embedding

核心思想：**正样本拉近、负样本推远**。

```
Loss = -log( exp(相似度(q, 正样本) / τ) / Σ exp(相似度(q, 所有候选) / τ) )
```

其中 τ 是温度（越小越"严格"，越区分正负样本）。

**负样本从哪来（质量差三倍）**：
1. **In-batch negatives**：同一 batch 里别的 query 的正样本（免费但弱）
2. **Random negatives**：随便抽（作用有限）
3. **Hard negatives**：用已有模型检索 top-K 但不相关的（质量飞跃）

Hard negative mining 是 BGE/E5 能做到 SOTA 的最核心 trick。

---

## 主流模型怎么选

| 模型 | 维度 | 中文 | 特点 | 什么时候用 |
|------|------|------|------|-----------|
| BGE-large-zh-v1.5 | 1024 | SOTA | 开源、私有部署首选 | 国内中文场景 |
| BGE-M3 | 1024 | 顶级 | dense+sparse 双模、多语言 | 复杂检索 |
| OpenAI text-embedding-3-small | 512-1536 | 良好 | API 稳定、便宜 | 海外+不在乎成本 |
| Cohere Embed v3 | 1024 | 好 | 商业 API、压缩模式 | 海外 |
| E5-mistral-7b | 4096 | 好 | 基于 7B LLM 效果最强 | 质量第一+算力够 |

**选型铁律**：自己的 eval 集跑 Recall@5，比 MTEB 榜单靠谱。

---

## Matryoshka 表示（OpenAI 的省钱大招）

训练时让前 256/512/1024/3072 维都能独立完成检索——推理时直接截到 1024 甚至 256，效果几乎不掉，存储省 3-12 倍。BGE 也支持了。

---

## 容易踩的坑

1. **A 模型编码 query，B 模型编码 doc** —— 两个向量空间不互通，余弦相似度没意义。RAG 必须同模型
2. **盲信 MTEB 榜单** —— 榜单英文通用领域，你的业务可能完全不一样
3. **维度越高越好** —— 1024→3072 效果提升不到 2%，但存储 +12 倍
4. **用 sentence embedding 搜精确 ID** —— "CVE-2024-3094" 这种编号 embedding 搜不准，要加 BM25 混合
5. **不加 normalize_embeddings** —— 生产环境默认 L2 归一化，后续用点积代替余弦，快 3 倍
