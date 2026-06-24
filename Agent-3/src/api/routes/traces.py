"""Trace 查询 API -- 读取 traces/ 目录下的 JSON/JSONL 文件."""
from __future__ import annotations

import glob
import json
import os
from typing import Any

from fastapi import APIRouter

from src.config import config

router = APIRouter(tags=["traces"])


def _load_trace_file(path: str) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as f:
            if path.endswith(".jsonl"):
                for line in f:
                    line = line.strip()
                    if line:
                        traces.append(json.loads(line))
            else:
                data = json.load(f)
                traces.extend(data if isinstance(data, list) else [data])
    except Exception:
        return []
    return traces


@router.get("/traces")
async def list_traces():
    traces: list[dict[str, Any]] = []
    pattern = os.path.join(config.trace_output_dir, "trace_*.json*")
    for path in sorted(glob.glob(pattern), reverse=True)[:20]:
        traces.extend(_load_trace_file(path))

    traces.sort(key=lambda t: t.get("start_time", 0), reverse=True)
    return {"traces": traces[:100], "total": len(traces)}
