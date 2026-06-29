# 04 - Metrics & Benchmark

> 学习目标：掌握 Agent 评测的核心指标体系，学会设计 Benchmark 和基线对比

---

## 1. 指标全景

```
         ┌──────────────────────────────────┐
         │         Agent Metrics             │
         │                                   │
         │  ┌─────────┐  ┌─────────┐        │
         │  │ Quality │  │Efficiency│        │
         │  │ 质量指标  │  │ 效率指标  │        │
         │  └────┬────┘  └────┬────┘        │
         │       │            │              │
         │  Accuracy      Latency           │
         │  Groundedness  Tool Calls        │
         │  Hallucination Token Usage       │
         │  Success Rate  Cost              │
         └──────────────────────────────────┘
```

---

## 2. 每个指标的精确定义

### Accuracy（准确性）

```
Accuracy = 正确的事实陈述 / 总事实陈述

测法：人工标注输出中的每个事实是否正确。

示例：
  Agent 输出："成都有宽窄巷子（✅正确）、锦里（✅正确）和乐山大佛（❌错误，在乐山不在成都）"
  → Accuracy = 2/3 = 66.7%
```

### Groundedness（有据性）

```
Groundedness = 有出处支撑的陈述 / 总陈述

与 Accuracy 的区别：
  Accuracy：对不对（和客观事实比）
  Groundedness：有没有出处（和检索到的文档比）
  
示例：
  Agent 输出："成都7月平均气温 28°C"（来自天气 API 返回的数据）
  → Grounded ✅（有来源）
  
  Agent 输出："成都夏季较热"（没有引用具体来源，是常识推断）
  → Grounded ❌（无出处，即使是正确的）
```

```python
def measure_groundedness(output: str, retrieved_docs: list) -> float:
    """逐句检查是否有出处"""
    sentences = split_sentences(output)
    grounded = 0
    
    for sentence in sentences:
        # 用 LLM 判断这一句是否能从 retrieved_docs 中推出
        is_grounded = llm.judge(
            f"这个陈述：'{sentence}' 能否从以下文档中推出？\n"
            f"文档：{retrieved_docs}\n"
            f"回答 YES/NO"
        )
        if "YES" in is_grounded:
            grounded += 1
    
    return grounded / len(sentences)
```

### Hallucination Rate（幻觉率）

```
Hallucination Rate = 幻觉陈述数 / 总陈述数

"幻觉"定义：听起来合理但与事实不符的陈述。

常见幻觉类型：
  - 事实错误："成都有迪士尼乐园"
  - 张冠李戴：把重庆的小吃说成成都的
  - 数字错误："成都人口 5000 万"（实际约 2100 万）
  - 编造引用：引一篇不存在的论文
```

### Success Rate（成功率）— 最重要的指标

```
Success Rate = 成功完成任务数 / 总任务数

"成功"定义：
  - 输出了结构完整的结果
  - 满足了用户的核心需求
  - 没有致命错误
```

### Latency（延迟）

```
P50 Latency：50% 的请求在这个时间内完成
P95 Latency：95% 的请求在这个时间内完成
P99 Latency：99% 的请求在这个时间内完成

→ 关注 P95，不是平均值。平均值会被极端值污染。
```

### Cost per Task

```
Cost = (Input Tokens × 输入单价 + Output Tokens × 输出单价) 
     + Tool API 调用费用

可以按 user / session / task / day 聚合
```

---

## 3. Benchmark 设计

一个好的 Benchmark 需要：

```python
class AgentBenchmark:
    def __init__(self):
        self.name = "TravelAgent-Bench-v1"
        self.description = "旅游 Agent 综合评测基准"
        
        # 数据集
        self.dataset = {
            "size": 200,
            "categories": {
                "行程规划":  80,   # 40%
                "信息查询":  60,   # 30%
                "预订操作":  30,   # 15%
                "异常处理":  20,   # 10%
                "多轮对话":  10,   # 5%
            },
            "difficulty_distribution": {
                "easy":   80,   # 40%
                "medium": 80,   # 40%
                "hard":   40,   # 20%
            }
        }
        
        # 基线
        self.baselines = {
            "random":         {"success_rate": 0.05, "source": "随机输出"},
            "gpt-4o-mini":    {"success_rate": 0.72, "source": "2026-07 实测"},
            "gpt-4o":         {"success_rate": 0.85, "source": "2026-07 实测"},
            "claude-3.5":     {"success_rate": 0.83, "source": "2026-07 实测"},
            "human_expert":   {"success_rate": 0.96, "source": "人工标注"},
        }
    
    def compare_to_baseline(self, agent_score: float) -> dict:
        """与基线对比"""
        comparisons = {}
        for name, baseline in self.baselines.items():
            comparisons[name] = {
                "baseline_score": baseline["success_rate"],
                "your_score": agent_score,
                "diff": agent_score - baseline["success_rate"],
                "better": agent_score > baseline["success_rate"]
            }
        return comparisons
```

---

## 4. 统计显著性

A/B 测试中，30 条 case 的差异可能是因为运气。需要统计检验。

```python
from scipy import stats
import numpy as np

def is_significant(results_a: list, results_b: list, 
                   alpha: float = 0.05) -> dict:
    """
    results_a: Prompt A 在每条的得分 [4, 3, 5, ...]
    results_b: Prompt B 在每条的得分 [5, 4, 4, ...]
    """
    # Paired t-test（同一条 case 对比两个 Prompt）
    t_stat, p_value = stats.ttest_rel(results_a, results_b)
    
    significant = p_value < alpha
    effect_size = (np.mean(results_b) - np.mean(results_a)) / np.std(results_a)
    
    return {
        "significant": significant,
        "p_value": p_value,
        "effect_size": effect_size,
        "interpretation": (
            f"{'✅ 显著' if significant else '➡️ 不显著'} "
            f"(p={p_value:.4f}, effect={effect_size:.2f})"
        )
    }
```

---

## 5. 持续追踪

```python
class EvalTracker:
    """记录每次评测的结果，追踪趋势"""
    
    def __init__(self, db_conn):
        self.db = db_conn
    
    def record(self, version: str, results: dict):
        self.db.insert("eval_history", {
            "version": version,
            "timestamp": datetime.now().isoformat(),
            "success_rate": results["overall_success_rate"],
            "avg_quality": results["avg_quality_score"],
            "avg_latency_ms": results["avg_latency_ms"],
            "avg_tokens": results.get("avg_tokens", 0),
            "total_cases": results.get("total_cases", 0)
        })
    
    def trend(self, metric: str, last_n: int = 10) -> list:
        """查看最近 N 次评测的某个指标趋势"""
        rows = self.db.query(
            f"SELECT version, {metric}, timestamp "
            f"FROM eval_history ORDER BY timestamp DESC LIMIT {last_n}"
        )
        return list(rows)
    
    def alert_if_regression(self, current: dict, threshold: float = 0.05):
        """如果当前指标比上次下降超过阈值，发出告警"""
        last = self.db.query(
            "SELECT * FROM eval_history ORDER BY timestamp DESC LIMIT 1"
        )
        if not last:
            return
        
        drop = last[0]["success_rate"] - current["overall_success_rate"]
        if drop > threshold:
            send_alert(
                f"⚠️ Agent Success Rate 下降了 {drop:.1%}！"
                f"从 {last[0]['success_rate']:.1%} 降到 {current['overall_success_rate']:.1%}"
            )
```

---

## 实践任务

**任务1**：为你的旅游 Agent 选 4 个核心指标（建议 Success Rate + P95 Latency + Avg Cost + Groundedness），定义清楚每个怎么测。

**任务2**：建立你的第一个 Baseline——用当前版本的 Agent 跑 50 条 case，记录指标。这就是你的"基准线"。

**任务3**：改动 Agent 的一个组件（如换一个 LLM 模型），重新跑 Benchmark，用统计检验判断是否有显著提升。

---

→ [05-Automated-Eval-Pipeline.md](./05-Automated-Eval-Pipeline.md)
