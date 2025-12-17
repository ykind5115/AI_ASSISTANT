"""
会话管理服务
管理用户会话、消息存储和检索
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from app.models.schema import Session as DBSession, Message, User
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """会话管理器"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_or_create_user(self, user_id: Optional[int] = None) -> User:
        """
        获取或创建用户
        
        Args:
            user_id: 用户ID，如果为None则获取默认用户
            
        Returns:
            用户对象
        """
        if user_id:
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                return user
        
        # 获取或创建默认用户
        user = self.db.query(User).first()
        if not user:
            user = User(
                display_name="用户",
                preferences={}
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            logger.info(f"创建默认用户: {user.id}")
        
        return user
    
    def create_session(self, user_id: Optional[int] = None, meta: Optional[Dict] = None) -> DBSession:
        """
        创建新会话
        
        Args:
            user_id: 用户ID
            meta: 会话元数据
            
        Returns:
            会话对象
        """
        user = self.get_or_create_user(user_id)
        
        session = DBSession(
            user_id=user.id,
            started_at=datetime.utcnow(),
            last_active_at=datetime.utcnow(),
            meta=meta or {}
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        logger.info(f"创建新会话: {session.id}")
        return session
    
    def get_session(self, session_id: int) -> Optional[DBSession]:
        """
        获取会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话对象或None
        """
        return self.db.query(DBSession).filter(DBSession.id == session_id).first()

    def delete_session(self, session_id: int) -> bool:
        """删除会话（级联删除消息）"""
        session = self.get_session(session_id)
        if not session:
            return False
        self.db.delete(session)
        self.db.commit()
        return True
    
    def get_active_session(self, user_id: Optional[int] = None) -> Optional[DBSession]:
        """
        获取用户的活动会话（最近使用的）
        
        Args:
            user_id: 用户ID
            
        Returns:
            会话对象或None
        """
        user = self.get_or_create_user(user_id)
        
        # 查找最近30天内的活动会话
        cutoff_date = datetime.utcnow() - timedelta(days=settings.MAX_SESSION_HISTORY_DAYS)
        
        session = self.db.query(DBSession).filter(
            and_(
                DBSession.user_id == user.id,
                DBSession.last_active_at >= cutoff_date
            )
        ).order_by(desc(DBSession.last_active_at)).first()
        
        return session
    
    def get_or_create_active_session(self, user_id: Optional[int] = None) -> DBSession:
        """
        获取或创建活动会话
        
        Args:
            user_id: 用户ID
            
        Returns:
            会话对象
        """
        session = self.get_active_session(user_id)
        if not session:
            session = self.create_session(user_id)
        return session
    
    def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        embedding_ref: Optional[str] = None
    ) -> Message:
        """
        添加消息到会话
        
        Args:
            session_id: 会话ID
            role: 角色 (user/assistant/system)
            content: 消息内容
            embedding_ref: 嵌入向量引用
            
        Returns:
            消息对象
        """
        from app.utils.security import SecurityFilter
        
        # 清理内容
        content = SecurityFilter.sanitize_for_storage(content)
        
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            embedding_ref=embedding_ref,
            created_at=datetime.utcnow()
        )
        self.db.add(message)
        
        # 更新会话最后活动时间
        session = self.get_session(session_id)
        if session:
            session.last_active_at = datetime.utcnow()
            if role == "user":
                meta = session.meta or {}
                current_title = meta.get("title")
                if not current_title or current_title == "新对话":
                    title = content.strip().replace("\n", " ")
                    title = title[:30] if len(title) > 30 else title
                    meta = dict(meta)
                    meta["title"] = title or "新对话"
                    session.meta = meta
        
        self.db.commit()
        self.db.refresh(message)
        
        return message

    def list_sessions(
        self,
        user_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DBSession]:
        """
        获取会话列表（按最近活跃排序）

        Args:
            user_id: 用户ID（None 时为默认用户）
            limit: 返回数量
            offset: 偏移量
        """
        user = self.get_or_create_user(user_id)
        query = self.db.query(DBSession).filter(DBSession.user_id == user.id).order_by(desc(DBSession.last_active_at))
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        return query.all()

    def count_messages(self, session_id: int) -> int:
        """统计会话消息数量"""
        return self.db.query(Message).filter(Message.session_id == session_id).count()
    
    def get_messages(
        self,
        session_id: int,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Message]:
        """
        获取会话消息
        
        Args:
            session_id: 会话ID
            limit: 限制数量
            offset: 偏移量
            
        Returns:
            消息列表
        """
        query = self.db.query(Message).filter(
            Message.session_id == session_id
        ).order_by(Message.created_at)
        
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_recent_messages(
        self,
        user_id: Optional[int] = None,
        days: int = 7,
        limit: Optional[int] = None
    ) -> List[Message]:
        """
        获取用户最近的消息
        
        Args:
            user_id: 用户ID
            days: 天数
            limit: 限制数量
            
        Returns:
            消息列表
        """
        user = self.get_or_create_user(user_id)
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # 获取用户的所有会话
        sessions = self.db.query(DBSession).filter(
            and_(
                DBSession.user_id == user.id,
                DBSession.last_active_at >= cutoff_date
            )
        ).all()
        
        session_ids = [s.id for s in sessions]
        
        if not session_ids:
            return []
        
        query = self.db.query(Message).filter(
            and_(
                Message.session_id.in_(session_ids),
                Message.created_at >= cutoff_date
            )
        ).order_by(Message.created_at)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_conversation_history(
        self,
        session_id: int,
        max_messages: int = 20
    ) -> List[Dict[str, str]]:
        """
        获取对话历史（用于模型输入）
        
        Args:
            session_id: 会话ID
            max_messages: 最大消息数
            
        Returns:
            对话历史列表 [{"role": "user", "content": "..."}, ...]
        """
        messages = self.get_messages(session_id, limit=max_messages)
        
        history = []
        for msg in messages:
            history.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return history
    
    def cleanup_old_sessions(self, days: Optional[int] = None):
        """
        清理旧会话（超过保留期的）
        
        Args:
            days: 保留天数，默认使用配置值
        """
        days = days or settings.MAX_SESSION_HISTORY_DAYS
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # 查找旧会话
        old_sessions = self.db.query(DBSession).filter(
            DBSession.last_active_at < cutoff_date
        ).all()
        
        count = len(old_sessions)
        for session in old_sessions:
            self.db.delete(session)
        
        self.db.commit()
        logger.info(f"清理了 {count} 个旧会话")
