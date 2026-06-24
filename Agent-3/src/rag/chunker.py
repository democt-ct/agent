"""文本分块器 -- 结构感知的 Markdown 文档分块.

相比旧版改进:
  - 保留 Markdown 标题层级作为 chunk 元数据
  - 每个 chunk 标注所属章节和段落位置
  - 为引用溯源提供 "source → 章节 → 第N段" 的定位信息

Usage:
    from src.rag.chunker import split_documents
    chunks = split_documents(docs, chunk_size=500, chunk_overlap=80)
    # chunk: {"content": "...", "source": "xxx.md", "title": "...",
    #         "section": "## 请假流程", "chunk_index": 3, "total_chunks": 12}
"""

from __future__ import annotations

import re
from langchain_text_splitters import RecursiveCharacterTextSplitter

_CHAR_PER_TOKEN_CHINESE = 1.8

# Markdown 标题正则: ## 标题 / ### 标题
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)


def _extract_headings(text: str) -> list[tuple[int, str, int]]:
    """提取文档中所有标题及其位置.

    Returns:
        [(position, level, heading_text), ...]
        如 [(0, 2, "请假流程"), (150, 3, "年假申请条件"), ...]
    """
    headings = []
    for m in _HEADING_RE.finditer(text):
        level = len(m.group(1))
        headings.append((m.start(), level, m.group(2).strip()))
    return headings


def _find_current_section(pos: int, headings: list[tuple[int, str, int]]) -> str:
    """根据字符位置找到所属的最近标题路径.

    Returns:
        如 "年假管理制度 > 申请条件",或 "(文首)"
    """
    if not headings:
        return ""

    # 找到 pos 之前最接近的各级标题
    current = {}
    for h_pos, level, text in headings:
        if h_pos <= pos:
            current[level] = text
            # 清除更深层级
            for l in list(current.keys()):
                if l > level:
                    del current[l]
        else:
            break

    if not current:
        return ""

    # 按层级构建路径
    parts = [current[l] for l in sorted(current.keys())]
    return " > ".join(parts)


def split_documents(
    documents: list[dict[str, str]],
    chunk_size: int = 500,
    chunk_overlap: int = 80,
) -> list[dict[str, str | int]]:
    """将文档列表切分为带章节信息的 chunks.

    chunk_size 按 token 设计,内部自动转换为字符数.
    每个 chunk 附带 section(所属章节路径)用于引用溯源.
    """
    char_size = int(chunk_size * _CHAR_PER_TOKEN_CHINESE)
    char_overlap = int(chunk_overlap * _CHAR_PER_TOKEN_CHINESE)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=char_size,
        chunk_overlap=char_overlap,
        separators=["\n\n", "\n", ".", ";", ",", " ", ""],
        length_function=len,
    )

    chunks: list[dict[str, str | int]] = []
    for doc in docs:
        text = doc.get("text", "")
        source = doc.get("source", "")
        title = doc.get("title", source)

        # 提取文档标题结构
        headings = _extract_headings(text)

        texts = splitter.split_text(text)
        total = len(texts)
        for i, chunk_text in enumerate(texts):
            # 在原文中定位 chunk 的起始位置(粗略:找前 60 字符)
            search_key = chunk_text[:60].strip()
            pos = text.find(search_key) if search_key else 0
            if pos < 0:
                pos = 0
            section = _find_current_section(pos, headings)

            chunks.append({
                "content": chunk_text,
                "source": source,
                "title": title,
                "section": section,
                "chunk_index": i,
                "total_chunks": total,
            })

    return chunks
