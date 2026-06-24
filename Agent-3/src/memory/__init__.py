"""Memory 模块 -- 三层记忆架构.

L1 工作记忆 → SessionMemory(内存窗口)
L2 会话持久化 → ConversationStore(SQLite)
L3 长期记忆 → LongTermMemory(SQLite + Chroma)
"""

from src.memory.conversation_store import ConversationStore
from src.memory.summary_compressor import SummaryCompressor
from src.memory.long_term import LongTermMemory


class SessionMemory:
    """L1 工作记忆 -- 内存滑动窗口.

    保留最近 N 轮对话,用于注入 Agent prompt.
    """

    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.messages: list[dict] = []
        self.enabled = True

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        # 保持窗口大小
        if len(self.messages) > self.window_size * 2:
            self.messages = self.messages[-(self.window_size * 2):]

    def get_history(self) -> list[dict]:
        return [{"role": m["role"], "content": m["content"]} for m in self.messages]

    def clear(self) -> None:
        self.messages.clear()


__all__ = ["SessionMemory", "ConversationStore", "SummaryCompressor", "LongTermMemory"]
