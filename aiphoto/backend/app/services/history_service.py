"""
轻量 JSON 文件存储的会话历史与用户偏好服务。

数据文件（backend/data/）：
  - sessions.json          会话列表
  - messages_{sid}.json    每个会话的消息流
  - preferences.json       长期用户偏好（风格偏好、平均参数偏移）

MVP 阶段用文件 I/O，预留接口便于未来切到 PG/Redis。
"""
import json
import uuid
import os
from datetime import datetime
from typing import Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")
PREFERENCES_FILE = os.path.join(DATA_DIR, "preferences.json")


def _read_json(path: str) -> any:
    """Read JSON file, return empty list/dict on missing or corrupt."""
    if not os.path.exists(path):
        return [] if "sessions" in path else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return [] if "sessions" in path else {}


def _write_json(path: str, data: any) -> None:
    """Write JSON atomically."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class HistoryService:
    """会话消息持久化 + 用户偏好记忆。"""

    # ── Sessions ────────────────────────────────────────────

    def list_sessions(self) -> List[Dict]:
        sessions = _read_json(SESSIONS_FILE)
        if not isinstance(sessions, list):
            return []
        # 按 created_at 降序
        sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return sessions

    def create_session(self, name: Optional[str] = None) -> Dict:
        sessions = _read_json(SESSIONS_FILE)
        if not isinstance(sessions, list):
            sessions = []
        sid = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat(timespec="seconds")
        session = {
            "id": sid,
            "name": name or f"会话 {now[:10]}",
            "created_at": now,
            "current_image_id": None,
            "message_count": 0,
        }
        sessions.append(session)
        _write_json(SESSIONS_FILE, sessions)
        return session

    def get_session(self, session_id: str) -> Optional[Dict]:
        sessions = self.list_sessions()
        for s in sessions:
            if s["id"] == session_id:
                return s
        return None

    def update_session(self, session_id: str, **fields) -> Optional[Dict]:
        sessions = _read_json(SESSIONS_FILE)
        for i, s in enumerate(sessions):
            if s["id"] == session_id:
                sessions[i].update(fields)
                _write_json(SESSIONS_FILE, sessions)
                return sessions[i]
        return None

    def delete_session(self, session_id: str) -> bool:
        sessions = _read_json(SESSIONS_FILE)
        before = len(sessions)
        sessions = [s for s in sessions if s["id"] != session_id]
        if len(sessions) < before:
            _write_json(SESSIONS_FILE, sessions)
            # 删除消息文件
            msg_path = os.path.join(DATA_DIR, f"messages_{session_id}.json")
            if os.path.exists(msg_path):
                os.remove(msg_path)
            return True
        return False

    # ── Messages ────────────────────────────────────────────

    def list_messages(self, session_id: str) -> List[Dict]:
        path = os.path.join(DATA_DIR, f"messages_{session_id}.json")
        msgs = _read_json(path)
        return msgs if isinstance(msgs, list) else []

    def append_message(
        self,
        session_id: str,
        role: str,
        text: str,
        image_id: Optional[str] = None,
        params: Optional[Dict] = None,
        diagnosis: Optional[Dict] = None,
    ) -> Dict:
        path = os.path.join(DATA_DIR, f"messages_{session_id}.json")
        msgs = _read_json(path)
        if not isinstance(msgs, list):
            msgs = []

        msg = {
            "id": str(uuid.uuid4())[:10],
            "role": role,  # "user" | "assistant"
            "text": text,
            "image_id": image_id,
            "params": params,
            "diagnosis": diagnosis,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        msgs.append(msg)
        _write_json(path, msgs)

        # 更新会话的消息计数和当前工作图
        self.update_session(
            session_id,
            message_count=len(msgs),
            current_image_id=image_id if role == "assistant" else None,
        )
        return msg

    # ── Preferences ────────────────────────────────────────

    def get_preferences(self) -> Dict:
        prefs = _read_json(PREFERENCES_FILE)
        if not isinstance(prefs, dict):
            return {"favorite_styles": {}, "avg_params": {}, "total_edits": 0}
        return prefs

    def record_edit(self, style: Optional[str] = None, params: Optional[Dict] = None) -> None:
        prefs = self.get_preferences()
        prefs["total_edits"] = prefs.get("total_edits", 0) + 1

        # 风格计数
        if style:
            favs = prefs.setdefault("favorite_styles", {})
            favs[style] = favs.get(style, 0) + 1

        # 累积平均参数（增量均值）
        if params:
            n = prefs["total_edits"]
            prev_avg = prefs.setdefault("avg_params", {})
            for k, v in params.items():
                if k == "style":
                    continue
                try:
                    val = float(v)
                    old = float(prev_avg.get(k, 0))
                    prev_avg[k] = round((old * (n - 1) + val) / n, 2)
                except (ValueError, TypeError):
                    pass

        _write_json(PREFERENCES_FILE, prefs)
