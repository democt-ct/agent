# 05 - Automated Eval Pipeline — 自动化评测流水线

> 学习目标：把评测从"手动跑"升级为"自动跑"——CI 集成、批量测试、报告生成

---

## 1. 手动评测 vs 自动评测

```
手动评测：
  改了代码 → 心里没底 → 手动跑几条 case → "看起来还行" → 上线
  问题：慢、不完整、不可重复、容易自欺欺人

自动评测：
  改了代码 → git push → CI 自动触发 → 跑 200 条 case → 
  → 生成报告 → 指标达标 ✅ → 自动部署
  → 指标下降 ❌ → 阻止合并 → 通知开发者
```

> **核心认知**：评测的价值 = 频率 × 覆盖度。只有自动化才能同时最大化两者。

---

## 2. 评测流水线架构

```
Git Push
    │
    ▼
┌─────────────┐
│  CI Trigger  │  (GitHub Actions / GitLab CI / Jenkins)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Build Image  │  docker build -t agent-eval .
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│            Eval Pipeline                 │
│                                          │
│  ① Prompt Eval (30s)                     │
│     └── Promptfoo: A/B + Regression      │
│                                          │
│  ② Agent Eval (5min)                     │
│     └── 200 cases × Agent loop           │
│                                          │
│  ③ Metrics Collection (10s)              │
│     └── 聚合指标，存入 eval_history       │
│                                          │
│  ④ Report Generation (5s)               │
│     └── Markdown 报告 + JSON 数据        │
│                                          │
│  ⑤ Decision Gate                        │
│     ├── Pass → 允许合并                  │
│     └── Fail → 阻止合并 + 通知           │
└─────────────────────────────────────────┘
```

---

## 3. GitHub Actions 集成

```yaml
# .github/workflows/eval.yml
name: Agent Evaluation

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  eval:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    
    services:
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run Prompt Eval
        run: |
          python -m eval.prompt_eval \
            --test-cases tests/prompt_cases.json \
            --output reports/prompt_eval.json
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      
      - name: Run Agent Eval
        run: |
          python -m eval.agent_eval \
            --test-suite tests/agent_suite.json \
            --parallel 4 \
            --output reports/agent_eval.json
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          REDIS_URL: redis://localhost:6379
      
      - name: Check Thresholds
        id: check
        run: |
          python -m eval.check_thresholds \
            --report reports/agent_eval.json \
            --min-success-rate 0.85 \
            --max-p95-latency 15000
      
      - name: Generate Report
        run: |
          python -m eval.generate_report \
            --prompt-report reports/prompt_eval.json \
            --agent-report reports/agent_eval.json \
            --output reports/EVAL_REPORT.md
      
      - name: Upload Report
        uses: actions/upload-artifact@v4
        with:
          name: eval-report
          path: reports/
      
      - name: Comment PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('reports/EVAL_REPORT.md', 'utf8');
            github.rest.issues.createComment({
              ...context.repo,
              issue_number: context.issue.number,
              body: report
            });
      
      - name: Notify on Failure
        if: failure()
        run: |
          python -m eval.notify \
            --webhook ${{ secrets.SLACK_WEBHOOK }} \
            --message "❌ Agent Eval FAILED on ${{ github.ref }}"
```

---

## 4. 并行评测器

200 条 case × 每条 5-10 秒 = 16-33 分钟。并行可以大幅缩短。

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

class ParallelEvaluator:
    def __init__(self, agent_factory, max_workers: int = 4):
        """
        agent_factory: 每个 worker 创建独立的 Agent 实例
                       （因为 Agent 有状态，不能共享）
        """
        self.agent_factory = agent_factory
        self.max_workers = max_workers
    
    def evaluate(self, test_suite: list) -> dict:
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._evaluate_one, case): case["id"]
                for case in test_suite
            }
            
            for future in as_completed(futures):
                case_id = futures[future]
                try:
                    result = future.result(timeout=60)  # 每条最多60秒
                    results.append(result)
                except Exception as e:
                    results.append({
                        "case_id": case_id,
                        "task_success": False,
                        "error": str(e)
                    })
        
        return self._aggregate(results)
    
    def _evaluate_one(self, case: dict) -> dict:
        agent = self.agent_factory()  # 每个线程独立 Agent
        start = time.perf_counter()
        output = agent.handle(case["user_input"], user_id=f"eval_{case['id']}")
        latency = (time.perf_counter() - start) * 1000
        
        return {
            "case_id": case["id"],
            "task_success": check_criteria(output, case["success_criteria"]),
            "latency_ms": latency,
            "tool_calls": output.get("tool_calls_count", 0),
        }
```

---

## 5. 阈值门禁

```python
class EvalGate:
    THRESHOLDS = {
        "overall_success_rate": {"min": 0.85, "severity": "critical"},
        "hard_success_rate":     {"min": 0.60, "severity": "critical"},
        "p95_latency_ms":        {"max": 15000, "severity": "warning"},
        "avg_cost_per_task":     {"max": 0.05, "severity": "warning"},
        "hallucination_rate":    {"max": 0.05, "severity": "critical"},
        "groundedness":          {"min": 0.80, "severity": "warning"},
    }
    
    def check(self, results: dict) -> dict:
        violations = []
        
        for metric, threshold in self.THRESHOLDS.items():
            value = results.get(metric)
            if value is None:
                continue
            
            if "min" in threshold and value < threshold["min"]:
                violations.append({
                    "metric": metric,
                    "value": value,
                    "threshold": threshold["min"],
                    "direction": "below_min",
                    "severity": threshold["severity"]
                })
            
            if "max" in threshold and value > threshold["max"]:
                violations.append({
                    "metric": metric,
                    "value": value,
                    "threshold": threshold["max"],
                    "direction": "above_max",
                    "severity": threshold["severity"]
                })
        
        criticals = [v for v in violations if v["severity"] == "critical"]
        passed = len(criticals) == 0
        
        return {
            "passed": passed,
            "violations": violations,
            "decision": "✅ PASS" if passed else "❌ FAIL (critical violations)"
        }
```

---

## 实践任务

**任务1**：写一个最简单的评测脚本（Python）——读 test_suite.json → 逐条跑 Agent → 输出 success_rate。验证能跑通。

**任务2**：把评测脚本改成并行版本（ThreadPoolExecutor），对比 50 条 case 的串行和并行耗时。

**任务3**：配置 GitHub Actions（或本地 pre-commit hook），实现 push 自动跑评测。如果 success_rate < 85%，阻止提交。

---

→ [06-实践：搭建评测平台.md](./06-实践：搭建评测平台.md)
