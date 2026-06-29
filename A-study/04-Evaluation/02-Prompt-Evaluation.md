# 02 - Prompt Evaluation

> 学习目标：掌握 Prompt 的 A/B 对比测试和回归测试，确保每次改 Prompt 是优化而非倒退

---

## 1. Prompt 是 Agent 的"基因"

改一行 System Prompt，可能让 Agent 的行为完全不同：

```
Prompt A: "你是旅游规划助手，帮用户制定行程。"
→ Agent 倾向于：先问用户偏好，再搜索

Prompt B: "你是高效的旅游规划助手，直接给出最优方案。"
→ Agent 倾向于：不等用户，直接搜+出方案
```

> **核心认知**：Prompt 是 Agent 最敏感的变量。每次改动必须评测。

---

## 2. A/B 测试 Prompt

```python
class PromptABTest:
    def __init__(self, prompt_a: str, prompt_b: str, test_cases: list):
        self.prompt_a = prompt_a
        self.prompt_b = prompt_b
        self.test_cases = test_cases
    
    def run(self) -> dict:
        results = {"a_wins": 0, "b_wins": 0, "tie": 0, "details": []}
        
        for case in self.test_cases:
            # 用 Prompt A 生成
            output_a = agent.run(case["input"], system_prompt=self.prompt_a)
            score_a = judge.evaluate(case["input"], output_a)
            
            # 用 Prompt B 生成
            output_b = agent.run(case["input"], system_prompt=self.prompt_b)
            score_b = judge.evaluate(case["input"], output_b)
            
            if score_a["overall"] > score_b["overall"]:
                results["a_wins"] += 1
            elif score_b["overall"] > score_a["overall"]:
                results["b_wins"] += 1
            else:
                results["tie"] += 1
            
            results["details"].append({
                "case": case["id"],
                "score_a": score_a["overall"],
                "score_b": score_b["overall"],
                "winner": "A" if score_a["overall"] > score_b["overall"] else
                          "B" if score_b["overall"] > score_a["overall"] else "tie"
            })
        
        return results
    
    def report(self, results: dict) -> str:
        total = results["a_wins"] + results["b_wins"] + results["tie"]
        return f"""
╔══════════════════════════════════╗
║       Prompt A/B Test Report     ║
╠══════════════════════════════════╣
║ Test cases: {total}
║ Prompt A wins: {results['a_wins']} ({results['a_wins']/total*100:.0f}%)
║ Prompt B wins: {results['b_wins']} ({results['b_wins']/total*100:.0f}%)
║ Tie:           {results['tie']} ({results['tie']/total*100:.0f}%)
║
║ {'✅ Prompt B is better' if results['b_wins'] > results['a_wins'] 
     else '⚠️  Prompt A is better' if results['a_wins'] > results['b_wins'] 
     else '➡️  No significant difference'}
╚══════════════════════════════════╝
"""
```

---

## 3. 回归测试

改了 Prompt，不能"修好一个 case，搞坏十个 case"。回归测试确保不倒退。

```python
class PromptRegressionTest:
    def __init__(self, baseline_results: dict):
        """baseline_results = {case_id: score}"""
        self.baseline = baseline_results
        self.regression_threshold = 0.1  # 允许 10% 的波动
    
    def check(self, new_results: dict) -> dict:
        regressions = []
        improvements = []
        
        for case_id, new_score in new_results.items():
            old_score = self.baseline.get(case_id)
            if old_score is None:
                continue
            
            change = (new_score - old_score) / old_score
            
            if change < -self.regression_threshold:
                regressions.append({
                    "case": case_id,
                    "old": old_score,
                    "new": new_score,
                    "change_pct": change * 100
                })
            elif change > self.regression_threshold:
                improvements.append({
                    "case": case_id,
                    "old": old_score,
                    "new": new_score,
                    "change_pct": change * 100
                })
        
        passed = len(regressions) == 0
        
        return {
            "passed": passed,
            "regressions": regressions,
            "improvements": improvements,
            "summary": f"{'✅ PASS' if passed else '❌ FAIL'}: "
                       f"{len(regressions)} regressions, "
                       f"{len(improvements)} improvements"
        }
```

---

## 4. Promptfoo — 专业 Prompt 评测工具

```yaml
# promptfooconfig.yaml
prompts:
  - file://prompts/travel_agent_v1.txt
  - file://prompts/travel_agent_v2.txt

providers:
  - id: openai:gpt-4o-mini
  - id: openai:gpt-4o

tests:
  - vars:
      user_input: "帮我规划成都三日游，预算3000"
    assert:
      - type: contains
        value: "Day 1"
      - type: not-contains
        value: "作为AI"
      - type: llm-rubric
        value: "输出是否包含交通、住宿和景点推荐？"
  
  - vars:
      user_input: "我想去一个暖和的地方"
    assert:
      - type: llm-rubric
        value: "Agent 是否追问了用户的偏好（预算/时间/出发点）？"
```

```bash
# 运行评测
npx promptfoo eval

# 查看结果
npx promptfoo view
```

Promptfoo 的价值：把上面的 A/B 测试和回归测试自动化了，加一个 Web UI。

---

## 5. 评测流水线

```python
class PromptEvalPipeline:
    def run(self, new_prompt: str) -> dict:
        # 1. A/B 测试（新 Prompt vs 旧 Prompt）
        ab_test = PromptABTest(self.current_prompt, new_prompt, self.ab_cases)
        ab_results = ab_test.run()
        
        # 2. 回归测试（确保不倒退）
        baseline_scores = self.load_baseline()  # 旧 Prompt 在 full dataset 上的分数
        new_scores = self.evaluate_all(new_prompt, self.full_dataset)
        regression = PromptRegressionTest(baseline_scores).check(new_scores)
        
        # 3. 决策
        if ab_results["b_wins"] > ab_results["a_wins"] and regression["passed"]:
            return {"decision": "deploy", "ab": ab_results, "regression": regression}
        else:
            return {"decision": "reject", "ab": ab_results, "regression": regression}
```

---

## 常见错误

| 错误 | 后果 | 正确做法 |
|------|------|---------|
| A/B 测试只用 5 条 case | 统计噪音淹没真实差异 | 至少 30 条 |
| 改了 Prompt 不跑回归 | 修好一个坏十个 | 每次改动跑全套回归 |
| 阈值太松 | 实际倒退测不出 | 回归阈值 ≤ 10% |
| 只看总分不看细分 | 总体提升但某类 case 全崩 | 按 category 分组看 |

---

## 实践任务

**任务1**：为你旅游 Agent 的 System Prompt 写两个版本（一个简练、一个详细），用 A/B 测试对比 20 条 case，分析哪个更好。

**任务2**：搭建 Promptfoo，跑你旅游 Agent 的 10 条测试用例，查看 Web UI 报告。

**任务3**：模拟一次回归测试——故意在 Prompt 中加一句"不要提预算"，看回归测试能否检测到这个退化。

---

→ [03-Agent-Evaluation.md](./03-Agent-Evaluation.md)
