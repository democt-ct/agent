"""启动知识库文件监听 — 文件变化自动重建索引

运行：python scripts/watch_kb.py

会在后台持续运行，监听 data/hr/ data/it/ data/legal/ 三个目录。
往里面新增/修改/删除 .md 文件会自动触发索引重建。
Ctrl+C 停止。
"""

import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag.embedder import Embedder
from src.rag.knowledge_base import KnowledgeBase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# ── 共享 Embedder ────────────────────────────────────────────────
print("Loading shared Embedder...")
embedder = Embedder()
print(f"  dimension={embedder.dimension}")

# ── 三个知识库 ───────────────────────────────────────────────────
kb_specs = [
    ("hr_kb", "data/hr/"),
    ("it_kb", "data/it/"),
    ("legal_kb", "data/legal/"),
]

kbs = {}
for name, docs_dir in kb_specs:
    kb = KnowledgeBase(kb_name=name, docs_dir=docs_dir, embedder=embedder)

    if os.path.exists(kb._metadata_path()):
        kb.load_index()
    else:
        kb.build_index()

    kbs[name] = kb

# ── 启动监听 ─────────────────────────────────────────────────────
for name, kb in kbs.items():
    kb.watch()

print()
print("Watchers active on:")
for _, docs_dir in kb_specs:
    print(f"  {docs_dir}")
print()
print("Add/edit/delete any .md file → index rebuilds automatically.")
print("Press Ctrl+C to stop.")
print()

try:
    while True:
        time.sleep(60)
except KeyboardInterrupt:
    print("\nStopping watchers...")
    for kb in kbs.values():
        kb.stop_watch()
    print("Done.")
