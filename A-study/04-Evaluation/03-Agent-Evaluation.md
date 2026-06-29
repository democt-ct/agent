# 03 - Agent Evaluation — 端到端评测

> 学习目标：掌握 Agent 级别的评测——不只是 Prompt 好不好，而是整个 Agent 能不能完成任务

---

## 1. Prompt 评测 vs Agent 评测

```
Prompt 评测：给 LLM 一个 Prompt → 看输出
  "这个 System Prompt 生成的行程序质量如何？"

Agent 评测：给 Agent 一个任务 → 看全过程
  "这个 Agent 能不能从零完成'成都三日游规划'？"
  
  不只是看最终输出，还要看：
  - 工具选择对不对？
  - 规划是否合理？
  - 有没有多余的 LLM 调用？
  - 失败后有没有正确恢复？
```

---

## 2. Task Success Rate — 核心指标

```python
class AgentEvaluator:
    def __init__(self, agent, test_suite: list, judge):
        self.agent = agent
        self.test_suite = test_suite
        self.judge = judge
    
    def evaluate(self) -> dict:
        results = []
        
        for case in self.test_suite:
            # 运行 Agent
            start = time.perf_counter()
            agent_output = self.agent.handle(case["user_input"], 
                                             user_id="eval_user")
            latency = (time.perf_counter() - start) * 1000
            
            # 多维度评测
            evaluation = {
                "case_id": case["id"],
                "category": case["category"],
                "difficulty": case["difficulty"],
                
                # 任务完成度
                "task_success": self._check_success_criteria(
                    agent_output, case["success_criteria"]
                ),
                
                # 质量打分
                "quality_score": self.judge.evaluate(
                    case["user_input"], agent_output
                )["overall"],
                
                # 效率
                "latency_ms": latency,
                "tool_calls": agent_output.get("tool_calls_count", 0),
                "tokens": agent_output.get("total_tokens", 0),
                
                # 过程检查
                "planning_quality": self._check_planning(agent_output, case),
                "tool_selection_accuracy": self._check_tool_selection(
                    agent_output, case
                ),
            }
            
            results.append(evaluation)
        
        return self._aggregate(results)
    
    def _check_success_criteria(self, output: dict, 
                                 criteria: list) -> bool:
        """检查是否满足了所有成功条件"""
        for criterion in criteria:
            if not self._check_one(output, criterion):
                return False
        return True
    
    def _aggregate(self, results: list) -> dict:
        by_category = {}
        for r in results:
            cat = r["category"]
            if cat not in by_category:
                by_category[cat] = {"total": 0, "success": 0, "scores": []}
            by_category[cat]["total"] += 1
            if r["task_success"]:
                by_category[cat]["success"] += 1
            by_category[cat]["scores"].append(r["quality_score"])
        
        return {
            "overall_success_rate": sum(1 for r in results if r["task_success"]) 
                                    / len(results),
            "avg_quality_score": sum(r["quality_score"] for r in results) 
                                 / len(results),
            "avg_latency_ms": sum(r["latency_ms"] for r in results) 
                              / len(results),
            "avg_tool_calls": sum(r["tool_calls"] for r in results) 
                              / len(results),
            "by_category": {
                cat: {
                    "success_rate": data["success"] / data["total"],
                    "avg_score": sum(data["scores"]) / len(data["scores"])
                }
                for cat, data in by_category.items()
            },
            "details": results
        }
```

---

## 3. 工具选择准确率

Agent 选了正确的工具吗？这是评测 Agent "聪明程度"的重要维度。

```python
class ToolSelectionEvaluator:
    def evaluate(self, agent_trace: list, expected_tools: list) -> dict:
        """
        agent_trace: Agent 实际调用的工具序列
        expected_tools: 预期应该调用的工具（人工标注）
        """
        actual = [t["tool_name"] for t in agent_trace]
        
        # 精确匹配率
        exact_match = actual == expected_tools
        
        # 召回率：预期要调的工具，实际调了吗？
        recall = len(set(expected_tools) & set(actual)) / len(expected_tools)
        
        # 精确率：实际调的工具中，哪些是该调的？
        precision = len(set(expected_tools) & set(actual)) / len(set(actual))
        
        # 多余调用 + 遗漏
        extra_calls = set(actual) - set(expected_tools)
        missed_calls = set(expected_tools) - set(actual)
        
        return {
            "exact_match": exact_match,
            "recall": recall,
            "precision": precision,
            "extra_calls": list(extra_calls),
            "missed_calls": list(missed_calls),
            "tool_call_count": len(actual),
            "expected_count": len(expected_tools)
        }


# 示例
case = {
    "input": "成都三日游",
    "expected_tools": ["web_search", "weather_api", "flight_search", 
                       "hotel_search"]
}

# Agent 实际调了：web_search → flight_search → hotel_search
# 遗漏了 weather_api
# → recall = 3/4 = 75%，precision = 3/3 = 100%
```

---

## 4. 评测报告模板

```python
def generate_eval_report(results: dict) -> str:
    return f"""
╔══════════════════════════════════════════════════╗
║           Agent Evaluation Report                ║
╠══════════════════════════════════════════════════╣
║ Overall Success Rate: {results['overall_success_rate']:.1%}
║ Avg Quality Score:    {results['avg_quality_score']:.1f}/5
║ Avg Latency:          {results['avg_latency_ms']:.0f}ms
║ Avg Tool Calls:       {results['avg_tool_calls']:.1f}
╠══════════════════════════════════════════════════╣
║ By Category:
{"".join(
    f"║   {cat:20s}: {data['success_rate']:.0%} "
    f"(score: {data['avg_score']:.1f}/5)\n"
    for cat, data in results['by_category'].items()
)}
╠══════════════════════════════════════════════════╣
║ Top Failures:
{"".join(
    f"║   ❌ {r['case_id']}: {r.get('failure_reason','unknown')[:50]}\n"
    for r in results['details'] if not r['task_success']
)[:3]}
╚══════════════════════════════════════════════════╝
"""
```

---

## 常见错误

| 错误 | 后果 | 正确做法 |
|------|------|---------|
| 只看最终输出不看过程 | Agent 用了10步才完成，效率极低但"看起来对" | 加上 tool_calls/tokens 指标 |
| Success Rate 不分组 | 总体 90% 但 hard 类全崩 | 按 difficulty/category 分组 |
| 测试集太简单 | 上线后真实用户场景大量失败 | 包含 20% hard + 10% adversarial |

---

## 实践任务

**任务1**：为你旅游 Agent 的 20 条评测用例跑一次完整评测，输出 Success Rate + avg latency + tool calls。

**任务2**：标注 10 条 case 的 expected_tools，评测你 Agent 的工具选择准确率（recall/precision）。

**任务3**：找出 Success Rate 最低的 3 个 case，分析为什么失败，提出改进方案。

---

→ [04-Metrics-and-Benchmark.md](./04-Metrics-and-Benchmark.md)
