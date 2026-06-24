"""文档加载器 -- 加载 MD/TXT/PDF/DOCX 文件为纯文本列表."""

from __future__ import annotations

import os
from pathlib import Path


def load_documents(docs_dir: str) -> list[dict[str, str]]:
    """扫描目录下所有支持的文档,返回纯文本列表.

    Args:
        docs_dir: 文档目录路径,如 "data/hr/".

    Returns:
        [{"text": "全文内容", "source": "年假制度.md", "title": "年假制度"}, ...]
    """
    docs: list[dict[str, str]] = []
    root = Path(docs_dir)

    if not root.exists():
        return docs

    for filepath in sorted(root.iterdir()):
        if filepath.suffix.lower() not in _SUPPORTED_SUFFIXES:
            continue
        if filepath.name.startswith("."):
            continue

        try:
            text = _load_file(str(filepath))
        except Exception:
            continue

        if text.strip():
            docs.append({
                "text": text,
                "source": filepath.name,
                "title": filepath.stem,
            })

    return docs


_SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf", ".docx"}


def _load_file(filepath: str) -> str:
    suffix = Path(filepath).suffix.lower()

    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        return "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

    if suffix == ".docx":
        from docx import Document  # type: ignore[import-untyped]
        doc = Document(filepath)
        return "\n".join(p.text for p in doc.paragraphs)

    # .md / .txt -- 直接按 UTF-8 读
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()
