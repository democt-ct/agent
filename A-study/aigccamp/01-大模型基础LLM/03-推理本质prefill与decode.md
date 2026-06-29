# 03-推理本质：Prefill 与 Decode

> 学完这篇要知道：LLM 生成一个 token 到底发生了什么、Prefill 和 Decode 是两种完全不同的计算、KV Cache 为什么是推理优化的根基。

---

## 一次推理到底发生了什么

用户输入"今天天气真好，" → 用户看到的第一个回复字出来之前，模型内部做了两件完全不同的事。

---

## Prefill（预填充阶段）→ 读懂你的话

**做什么**：把整段 prompt 一次性扔进 Transformer，并行算出所有位置的输出 + 缓存每一层的 K 和 V。

**特点**：
- 计算量大（矩阵乘矩阵），**算力 bound**——GPU 计算单元能跑满
- 时间 ≈ prompt token 数的线性函数
- 1000 token 的 prompt，prefill 约 50-500ms（看硬件）

**输出**：prompt 最后一个位置的 hidden state（用来生成第一个字）+ 所有层的 KV Cache

---

## Decode（自回归生成）→ 一个字一个字吐

**做什么**：用上一个生成的 token + 之前攒的 KV Cache，算出下一个 token 的概率，采样→输出，循环。

**特点**：
- 计算量小（矩阵乘向量），**显存带宽 bound**——GPU 大部分时间在把权重从 HBM 搬到 SRAM
- 每生成一个 token 固定时间（约 10-50ms），与 prompt 长度几乎无关（因为 KV Cache 已算好）
- 直到生成 `EOS` 或达到 max_tokens 才停

---

## KV Cache：为什么 decode 不用每次都重算 attention

**一句话**：生成第 T 个 token 时，前 T-1 个 token 的 K 和 V 在上一轮已经算过且永远不会变——直接存起来用，别重算。

**不用的代价**：
- 生成第 100 个 token：要算 100² = 10000 次 attention
- 生成第 1000 个 token：要算 1000² = 100 万次 attention
- 用了 KV Cache：每步只算 1 次新 attention + 1000 次查表

**代价——显存**：

```
KV Cache 大小 = 2 × 层数 × KV头数 × 每头维度 × 序列长度 × 精度字节数
```

Llama-7B 例子：2 × 32层 × 8头 × 128维 × 1token × 2字节 = **每 token 占 128KB**
- 4000 token 上下文 → 512MB（一张小显卡就不行了）
- 128K token → 16GB（光 KV Cache 就一张 A100）

**这就是长上下文最痛的代价——不是算不动，是装不下。**

---

## Prefill vs Decode 一张表

| | Prefill | Decode |
|------|------|------|
| 输入 | 全部 prompt | 1 个 token |
| 计算模式 | 并行（矩阵×矩阵） | 串行（矩阵×向量） |
| 瓶颈 | 算力 | 显存带宽 |
| 出几个 token | 0 个（只准备） | 1 个 |
| 延迟 | 随 prompt 线性增长 | 固定（每 token） |
| 优化方向 | FlashAttention、分块 prefill | 量化、speculative decoding |

**关键认知**：用户感知的延迟 = Prefill 时间 + 第一个 token 出来的时间（TTFT）。prompt 越长，Prefill 占比越高。这也是为什么 system prompt 长不会拖慢每 token 速度——因为 system prompt 的 KV Cache 只算一次。

---

## 采样策略（怎么从概率变成具体字）

### Greedy（贪心）

永远选概率最高的。temp=0 时就是这个行为。确定性强但容易重复、无趣。

### Top-K

只从 K 个最高概率的词里采样，扔掉后面的。K=50 是经典值。但不管概率分布长什么样都取 K 个——概率集中的时候还取 50 个就是浪费，概率平均的时候取 50 个又丢信息。

### Top-P（核采样，主流）

概率从高到低累加，和超过 P 就截断。动态决定"取几个"——比 Top-K 智能，现在所有主流 API 默认 Top-P。

### 束搜索（Beam Search）

同时保留多个候选序列（比如 4 条），每步扩展并剪枝。适合翻译/摘要等需要全局最优的任务。**LLM 聊天几乎不用**——用户要多样性不是最优解。

---

## 容易踩的坑

1. **Prefill 时间被忽略** —— 10K token 的 prompt，prefill 可能要 5 秒，用户以为是"卡了"
2. **长 prompt 没做 prefix caching** —— system prompt 每次都重算 KV Cache，白白浪费
3. **temperature=0 以为绝对确定** —— GPU 浮点运算有微小随机性，实测重复率约 80-90%
4. **同时设 top_k 和 top_p** —— 没必要，选一个就够了，通常选 top_p
