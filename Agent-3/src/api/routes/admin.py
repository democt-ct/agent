"""Admin API -- 管理后台接口(仅 manager/hr/admin 角色可访问).

端点:
    GET /api/admin/users          -- 用户列表
    GET /api/admin/leaves         -- 请假记录总览
    GET /api/admin/approvals      -- 审批记录查询
    GET /api/admin/expenses       -- 报销记录总览
    PUT /api/admin/users/{uid}    -- 更新用户信息
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["admin"])


def _require_admin(request: Request):
    session = getattr(request.state, "session", None)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})
    if session.role not in ("manager", "hr", "admin"):
        return JSONResponse(status_code=403, content={"error": "无权访问管理后台"})
    return None


@router.get("/admin/users")
async def list_users(request: Request):
    err = _require_admin(request)
    if err:
        return err
    from src.tools.db import get_db
    with get_db() as conn:
        rows = conn.execute(
            """SELECT u.user_id, u.name, u.role, u.status, u.hire_date,
                      u.annual, u.sick, u.personal,
                      d.name as department_name,
                      m.name as manager_name
               FROM users u
               JOIN departments d ON u.department_id = d.id
               LEFT JOIN users m ON u.manager_id = m.user_id
               ORDER BY u.department_id, u.user_id"""
        ).fetchall()
    return {"users": [dict(r) for r in rows], "total": len(rows)}


@router.put("/admin/users/{uid}")
async def update_user(request: Request, uid: str):
    err = _require_admin(request)
    if err:
        return err
    body = await request.json()
    allowed = {"name", "role", "status", "annual", "sick", "personal", "manager_id", "department_id"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        return JSONResponse(status_code=400, content={"error": "无有效更新字段"})
    from src.tools.db import get_db
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_db() as conn:
        conn.execute(
            f"UPDATE users SET {set_clause}, updated_at = datetime('now') WHERE user_id = ?",
            list(updates.values()) + [uid],
        )
        conn.commit()
    return {"success": True, "user_id": uid}


@router.get("/admin/leaves")
async def list_leaves(request: Request, status: str = "", user_id: str = "", limit: int = 100):
    err = _require_admin(request)
    if err:
        return err
    from src.tools.db import get_db
    conditions = []
    params = []
    if status:
        conditions.append("l.status = ?")
        params.append(status)
    if user_id:
        conditions.append("l.user_id = ?")
        params.append(user_id)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)
    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT l.*, u.name as user_name, d.name as department_name
                FROM leave_records l
                JOIN users u ON l.user_id = u.user_id
                JOIN departments d ON u.department_id = d.id
                {where}
                ORDER BY l.created_at DESC LIMIT ?""",
            params,
        ).fetchall()
    return {"leaves": [dict(r) for r in rows], "total": len(rows)}


@router.get("/admin/approvals")
async def list_approvals(request: Request, status: str = "pending", limit: int = 100):
    err = _require_admin(request)
    if err:
        return err
    from src.tools.db import get_db
    params = []
    cond = ""
    if status:
        cond = "WHERE a.status = ?"
        params.append(status)
    params.append(limit)
    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT a.*, u.name as approver_name
                FROM approval_flow a
                JOIN users u ON a.approver_id = u.user_id
                {cond}
                ORDER BY a.created_at DESC LIMIT ?""",
            params,
        ).fetchall()
    return {"approvals": [dict(r) for r in rows], "total": len(rows)}


@router.get("/admin/expenses")
async def list_expenses(request: Request, status: str = "", limit: int = 100):
    err = _require_admin(request)
    if err:
        return err
    from src.tools.db import get_db
    params = []
    cond = ""
    if status:
        cond = "WHERE e.status = ?"
        params.append(status)
    params.append(limit)
    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT e.*, u.name as user_name
                FROM expense_reports e
                JOIN users u ON e.user_id = u.user_id
                {cond}
                ORDER BY e.created_at DESC LIMIT ?""",
            params,
        ).fetchall()
    return {"expenses": [dict(r) for r in rows], "total": len(rows)}




@router.get("/admin/eval/latest")
async def latest_eval_report(request: Request):
    """获取最新的评估报告(从 data/eval/report_*.json 读取)."""
    err = _require_admin(request)
    if err:
        return err

    import glob as _glob
    import os as _os

    eval_dir = _os.path.join(
        _os.path.dirname(__file__), "..", "..", "..", "data", "eval"
    )
    pattern = _os.path.join(eval_dir, "report_*.json")
    files = sorted(_glob.glob(pattern), key=_os.path.getmtime, reverse=True)

    if not files:
        return JSONResponse(
            status_code=404,
            content={
                "error": "暂无评估报告",
                "hint": "运行 py scripts/run_eval.py --output data/eval/report_retrieval.json 生成报告",
            },
        )

    import json as _json
    with open(files[0], "r", encoding="utf-8") as f:
        report = _json.load(f)

    return {
        "file": _os.path.basename(files[0]),
        "report": report,
    }


@router.post("/admin/eval/run")
async def run_eval(request: Request):
    """触发一次评估运行,结果保存到 data/eval/report_{timestamp}.json."""
    err = _require_admin(request)
    if err:
        return err

    import json as _json
    import os as _os
    import time as _time

    state = request.app.state.app_state

    if state is None or state.orchestrator is None:
        return JSONResponse(status_code=503, content={"error": "Agent 引擎未就绪"})

    from src.evaluation.loader import TestLoader
    from src.evaluation.runner import EvalRunner

    eval_dir = _os.path.join(
        _os.path.dirname(__file__), "..", "..", "..", "data", "eval"
    )
    test_path = _os.path.join(eval_dir, "test_set.jsonl")

    if not _os.path.exists(test_path):
        return JSONResponse(status_code=404, content={"error": f"测试集不存在: {test_path}"})

    loader = TestLoader(test_path)
    cases = loader.load()

    # 可选限制用例数量(?limit=5)
    try:
        limit = int(request.query_params.get("limit", "0"))
    except (ValueError, TypeError):
        limit = 0
    if limit > 0 and limit < len(cases):
        cases = cases[:limit]

    if not cases:
        return JSONResponse(status_code=400, content={"error": "测试集为空"})

    # 暂停所有知识库文件监听,避免评估期间误触发全量重建
    for kb in state.knowledge_bases.values():
        try:
            kb.stop_watch()
        except Exception:
            pass

    # 是否使用 LLM 路由(?llm=false 仅关键词路由)
    use_llm = request.query_params.get("llm", "true").lower() != "false"
    # 是否使用查询改写(?rewrite=false 跳过改写)
    rewrite = request.query_params.get("rewrite", "true").lower() != "false"

    try:
        runner = EvalRunner(state.orchestrator, state.agent_instances)
        report_obj = runner.run(cases, retrieval_only=True, use_llm=use_llm, rewrite=rewrite)
    finally:
        # 恢复文件监听
        for kb in state.knowledge_bases.values():
            try:
                kb.watch()
            except Exception:
                pass

    # 保存报告
    ts = _time.strftime("%Y%m%d_%H%M%S")
    out_path = _os.path.join(eval_dir, f"report_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report_obj.model_dump_json(indent=2))

    return {
        "file": _os.path.basename(out_path),
        "report": _json.loads(report_obj.model_dump_json()),
    }
