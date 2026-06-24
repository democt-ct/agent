"""查询改写 -- 将用户口语 query 转为检索友好的书面表达.

原理:用户自然语言 ("年终奖什么时候发") 和文档书面语言
("年终奖发放规则") 处于不同语义空间,LLM 改写后两者对齐,
检索命中率大幅提升.
"""

from __future__ import annotations

from typing import Any

REWRITE_PROMPT = """你是一个查询改写专家.将用户的口语化问题改写为适合在企业文档中检索的书面表达.

## 规则
1. 提取问题中的核心实体和动作
2. 用正式书面语替代口语词(如"扣钱"→"扣款/处罚","什么时候发"→"发放时间/规则")
3. 扩展缩写和模糊表达
4. 只返回改写后的查询字符串,不要任何解释

## 示例
用户: 年终奖什么时候发
改写: 年终奖发放规则 发放时间

用户: 迟到会扣钱吗
改写: 迟到处罚 扣款标准 考勤违规处理

用户: 病假工资怎么算
改写: 病假工资标准 病假薪资计算

用户: 怎么请假
改写: 请假申请流程 请假审批步骤"""


def rewrite_query(
    client: Any,
    query: str,
    model: str = "deepseek-v4-flash",
) -> str:
    """用 LLM 改写用户查询.

    Args:
        client: OpenAI 兼容客户端.
        query: 用户原始查询.
        model: 模型名称.

    Returns:
        改写后的查询字符串.
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": REWRITE_PROMPT},
            {"role": "user", "content": f"用户: {query}\n改写:"},
        ],
        temperature=0.1,
        max_tokens=100,
    )
    rewritten = response.choices[0].message.content or query
    return rewritten.strip()
