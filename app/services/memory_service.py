"""
长期记忆服务
把用户跨会话的重要信息压缩成一段摘要，注入到后续对话中，避免 new chat 后“失忆”。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.schema import User
from app.services.session_manager import SessionManager
from app.ml.model_api import model_api


class MemoryService:
    """用户长期记忆（跨会话摘要）"""

    MEMORY_KEY = "long_term_memory"
    UPDATED_AT_KEY = "long_term_memory_updated_at"

    def __init__(self, db: Session):
        self.db = db
        self.session_manager = SessionManager(db)

    def _get_user(self, user_id: int) -> User:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("用户不存在")
        return user

    def get_memory(self, user_id: int) -> Optional[str]:
        user = self._get_user(user_id)
        prefs = user.preferences or {}
        memory = prefs.get(self.MEMORY_KEY)
        if isinstance(memory, str) and memory.strip():
            return memory.strip()
        return None

    def _get_updated_at(self, user: User) -> Optional[datetime]:
        prefs = user.preferences or {}
        raw = prefs.get(self.UPDATED_AT_KEY)
        if not isinstance(raw, str) or not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except Exception:
            return None

    def ensure_memory_fresh(
        self,
        user_id: int,
        user_preferences: Optional[Dict] = None,
        force: bool = False,
        max_messages: int = 200,
        refresh_hours: int = 6,
    ) -> Optional[str]:
        """
        保证长期记忆可用：没有就生成，过期就刷新。

        - 摘要来源：最近 N 天（settings.MAX_SESSION_HISTORY_DAYS）内所有会话的消息
        - 输出长度：复用模型的摘要 prompt（约 200 字）
        """
        user = self._get_user(user_id)
        prefs = dict(user.preferences or {})

        memory = prefs.get(self.MEMORY_KEY)
        updated_at = self._get_updated_at(user)
        now = datetime.utcnow()

        is_stale = (updated_at is None) or (now - updated_at > timedelta(hours=refresh_hours))
        if not force and isinstance(memory, str) and memory.strip() and not is_stale:
            return memory.strip()

        window_days = settings.MAX_SESSION_HISTORY_DAYS
        messages = self.session_manager.get_recent_messages(user_id=user_id, days=window_days, limit=max_messages)
        if not messages:
            return memory.strip() if isinstance(memory, str) else None

        message_list = [{"role": m.role, "content": m.content} for m in messages[-max_messages:]]
        window_end = now
        window_start = now - timedelta(days=window_days)

        summary = model_api.generate_summary(message_list, window_start, window_end, user_preferences or prefs)
        summary = (summary or "").strip()
        if not summary:
            return memory.strip() if isinstance(memory, str) else None

        prefs[self.MEMORY_KEY] = summary
        prefs[self.UPDATED_AT_KEY] = now.isoformat()
        user.preferences = prefs
        self.db.commit()
        return summary

