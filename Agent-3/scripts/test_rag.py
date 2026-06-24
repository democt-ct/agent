"""RAG 管线测试 — 三个知识库共享 Embedder + 查询改写对比

运行：python scripts/test_rag.py

首次运行会自动下载 BGE 模型（~1.3GB），之后走缓存。
"""

import logging
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag.embedder import Embedder
from src.rag.knowledge_base import KnowledgeBase

# ── 配置 ────────────────────────────────────────────────────────
load_dotenv()
api_key = os.getenv("DEEPSEEK_API_KEY")

print("=" * 60)
print("  RAG Retrieval Quality Test (BGE-large-zh-v1.5)")
print("  三个知识库 · 共享 Embedder")
print("=" * 60)
print()

# ── 共享 Embedder（只加载一次模型） ──────────────────────────────
print("[0] Loading shared Embedder...")
t0 = time.time()
shared_embedder = Embedder()
print(f"    Done in {time.time() - t0:.1f}s  (dimension={shared_embedder.dimension})")
print()

# ── 知识库定义 ──────────────────────────────────────────────────
kb_specs = [
    {
        "name": "hr_kb",
        "docs_dir": "data/hr/",
        "label": "HR 政策",
        "test_cases": [
            ("年假还剩几天", "年假管理制度.md"),
            ("病假工资怎么算", "病假和医疗期规定.md"),
            ("怎么申请请假", "请假审批流程.md"),
            ("迟到会扣钱吗", "考勤政策.md"),
            ("年终奖什么时候发", "薪酬福利说明.md"),
        ],
    },
    {
        "name": "it_kb",
        "docs_dir": "data/it/",
        "label": "IT 支持",
        "test_cases": [
            ("电脑坏了怎么报修", "报修指南.md"),
            ("密码忘了怎么办", "密码和账号管理.md"),
            ("怎么安装软件", "软件安装申请.md"),
            ("笔记本怎么申领", "设备申领流程.md"),
            ("VPN 怎么连", "网络和VPN配置.md"),
        ],
    },
    {
        "name": "legal_kb",
        "docs_dir": "data/legal/",
        "label": "法务合规",
        "test_cases": [
            ("保密协议有什么用", "保密协议说明.md"),
            ("怎么检查合规", "合规检查清单.md"),
            ("合同怎么审批", "合同审批流程.md"),
            ("数据保护有什么规定", "数据保护条例.md"),
            ("知识产权归谁", "知识产权政策.md"),
        ],
    },
]

# ── 构建/加载所有知识库 ──────────────────────────────────────────
kbs: dict[str, KnowledgeBase] = {}

for spec in kb_specs:
    kb = KnowledgeBase(
        kb_name=spec["name"],
        docs_dir=spec["docs_dir"],
        embedder=shared_embedder,  # ← 共享
    )

    meta_path = kb._metadata_path()
    if os.path.exists(meta_path):
        print(f"[{spec['name']}] Loading existing index...")
        kb.load_index()
    else:
        print(f"[{spec['name']}] Building new index...")
        t0 = time.time()
        kb.build_index()
        print(f"    Done in {time.time() - t0:.1f}s")

    kbs[spec["name"]] = kb

# ── 查询改写（共用） ─────────────────────────────────────────────
if api_key:
    from src.llm_client import get_client, get_model
    client = get_client()
    for kb in kbs.values():
        kb.set_rewriter(client)
    rewrite_enabled = True
    print(f"\n[QW] Query rewriting enabled ({get_model()})")
else:
    rewrite_enabled = False
    print("\n[QW] No API key, rewriting disabled")

print()

# ── 逐知识库测试 ─────────────────────────────────────────────────
grand_total_ok = 0
grand_total = 0

for spec in kb_specs:
    kb = kbs[spec["name"]]
    label = spec["label"]
    test_cases = spec["test_cases"]

    print(f"── {label} ({spec['name']}) ──")
    print(f"{'Query':20s} | {'NoRewrite':28s} | {'Rewrite':28s}")
    print("-" * 82)

    kb_ok = 0
    for query, expected_source in test_cases:
        no_rw_ok = False
        rw_ok = False
        no_rw_source = ""
        rw_source = ""

        res = kb.query(query, top_k=5, rewrite=False)
        if res:
            no_rw_source = res[0]["source"]
            no_rw_ok = expected_source in no_rw_source

        if rewrite_enabled:
            res_rw = kb.query(query, top_k=5, rewrite=True)
            if res_rw:
                rw_source = res_rw[0]["source"]
                rw_ok = expected_source in rw_source

        if no_rw_ok:
            kb_ok += 1

        no_rw = f"[OK] {no_rw_source}" if no_rw_ok else f"[XX] {no_rw_source}"
        rw = f"[OK] {rw_source}" if rw_ok else (f"[XX] {rw_source}" if rw_source else "N/A")
        print(f"{query:20s} | {no_rw:28s} | {rw:28s}")

    print(f"    {label}: {kb_ok}/{len(test_cases)}")
    print()
    grand_total_ok += kb_ok
    grand_total += len(test_cases)

# ── 汇总 ─────────────────────────────────────────────────────────
print("=" * 60)
print(f"  Overall: {grand_total_ok}/{grand_total}")
print("=" * 60)
print()
print("Done.")
