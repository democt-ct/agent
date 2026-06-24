"""上下文压缩 -- 长会话摘要生成器.

当会话消息数超过阈值(默认 20 条),触发 LLM 摘要压缩:
  1. 保留最近 6 条消息(3 轮对话)
  2. 前面的消息用 LLM 生成一段 200 字摘要
  3. 删除旧消息,插入摘要行

Usage:
    compressor = SummaryCompressor(client, model)
    compressor.compress(session_id, store)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

COMPRESS_THRESHOLD = 20       # 超过此数量触发压缩
KEEP_RECENT = 6               # 始终保留最近 N 条

SUMMARY_SYSTEM_PROMPT = """你是一个对话摘要专家.将以下多轮对话压缩为一段简洁摘要.

## 要求
1. 100-200 字
2. 保留关键信息:用户身份,核心问题,工具调用结果,最终决定
3. 忽略寒暄和冗余内容
4. 使用中文

## 对话内容"""


class SummaryCompressor:
    """LLM 对话摘要压缩器."""

    def __init__(self, client: Any, model: str = "deepseek-v4-flash"):
        self.client = client
        self.model = model

    def should_compress(self, store: Any, session_id: str) -> bool:
        """判断是否需要压缩."""
        count = store.count_messages(session_id)
        return count >= COMPRESS_THRESHOLD

    def compress(self, store: Any, session_id: str) -> str | None:
        """执行压缩:生成摘要 → 替换旧消息.

        Returns:
            生成的摘要文本,失败返回 None.
        """
        messages = store.load_recent(session_id, limit=100)
        if len(messages) <= COMPRESS_THRESHOLD:
            return None

        # 旧消息(去掉保留的 KEEP_RECENT 条)
        old_messages = messages[:-KEEP_RECENT] if len(messages) > KEEP_RECENT else []
        if not old_messages:
            return None

        # 构建压缩文本
        dialogue = "\n".join(
            f"[{m['role']}]: {m['content'][:300]}" for m in old_messages
        )

        # 调用 LLM 生成摘要
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": dialogue},
                ],
                temperature=0.1,
                max_tokens=400,
            )
            summary = response.choices[0].message.content or ""
            summary = summary.strip()

            if summary:
                # 替换旧消息为摘要
                store.replace_with_summary(session_id, summary, len(old_messages))
                logger.info(
                    "Compressed session %s: %d messages → summary (%d chars)",
                    session_id, len(old_messages), len(summary),
                )
                return summary
        except Exception as e:
            logger.warning("Summary compression failed: %s", e)

        return None
