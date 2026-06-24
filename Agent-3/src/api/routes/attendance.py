"""考勤打卡 API."""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["attendance"])


@router.post("/attendance/punch")
async def punch(request: Request):
    session = getattr(request.state, "session", None)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})
    body = await request.json()
    punch_type = body.get("type", "in")  # "in" | "out"
    now = datetime.now(timezone.utc)
    time_str = now.strftime("%H:%M")

    from src.tools.db import get_db
    import uuid
    with get_db() as conn:
        conn.execute(
            "INSERT INTO attendance_records (id, user_id, punch_type, punch_time, date) VALUES (?,?,?,?,?)",
            (uuid.uuid4().hex[:12], session.user_id, punch_type, now.isoformat(), now.strftime("%Y-%m-%d")),
        )
        conn.commit()

    label = "上班" if punch_type == "in" else "下班"
    return {"success": True, "type": punch_type, "time": time_str, "message": f"{label}打卡成功({time_str})"}


@router.get("/attendance/today")
async def today(request: Request):
    session = getattr(request.state, "session", None)
    if session is None:
        return JSONResponse(status_code=401, content={"error": "未认证"})
    from src.tools.db import get_db
    from datetime import date
    today_str = date.today().isoformat()
    with get_db() as conn:
        try:
            rows = conn.execute(
                "SELECT punch_type, punch_time FROM attendance_records WHERE user_id=? AND date=? ORDER BY punch_time",
                (session.user_id, today_str),
            ).fetchall()
        except Exception:
            rows = []
    return {"date": today_str, "records": [dict(r) for r in rows]}
