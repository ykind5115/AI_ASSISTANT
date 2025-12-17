"""
聊天API
提供对话接口
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from app.models.schema import get_db
from app.api.deps import get_current_user_optional
from app.models.schema import User
from app.services.session_manager import SessionManager
from app.services.memory_service import MemoryService
from app.ml.model_api import model_api
from app.utils.security import SecurityFilter
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    """聊天请求"""
    session_id: Optional[int] = None
    message: str
    user_id: Optional[int] = None


class ChatResponse(BaseModel):
    """聊天响应"""
    reply: str
    session_id: int
    message_id: int
    metadata: Optional[Dict] = None
    show_help: bool = False
    help_message: Optional[str] = None


class SessionListItem(BaseModel):
    session_id: int
    title: str
    started_at: str
    last_active_at: str
    message_count: int


class NewSessionResponse(BaseModel):
    session_id: int
    started_at: str
    last_active_at: str


@router.get("/sessions", response_model=List[SessionListItem])
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """获取会话列表（历史对话）"""
    session_manager = SessionManager(db)
    sessions = session_manager.list_sessions(current_user.id if current_user else None, limit=limit, offset=offset)

    items: List[SessionListItem] = []
    for s in sessions:
        meta = s.meta or {}
        title = meta.get("title") or "新对话"
        items.append(
            SessionListItem(
                session_id=s.id,
                title=title,
                started_at=s.started_at.isoformat(),
                last_active_at=(s.last_active_at or s.started_at).isoformat(),
                message_count=session_manager.count_messages(s.id),
            )
        )
    return items


@router.post("/session/new", response_model=NewSessionResponse)
async def create_new_session(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """新建对话（强制创建一个新的 session）"""
    session_manager = SessionManager(db)
    user_id = current_user.id if current_user else None
    session = session_manager.create_session(user_id=user_id, meta={"title": "新对话"})
    return NewSessionResponse(
        session_id=session.id,
        started_at=session.started_at.isoformat(),
        last_active_at=session.last_active_at.isoformat(),
    )


@router.get("/session/{session_id}/export")
async def export_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """导出单个会话的消息记录（JSON）"""
    session_manager = SessionManager(db)
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if current_user and session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权导出该会话")
    if not current_user:
        default_user = session_manager.get_or_create_user(None)
        if session.user_id != default_user.id:
            raise HTTPException(status_code=403, detail="无权导出该会话")

    messages = session_manager.get_messages(session_id=session_id, limit=None, offset=0)

    return {
        "session": {
            "id": session.id,
            "user_id": session.user_id,
            "started_at": session.started_at.isoformat(),
            "last_active_at": (session.last_active_at or session.started_at).isoformat(),
            "meta": session.meta or {},
        },
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """删除会话（历史对话）"""
    session_manager = SessionManager(db)
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if current_user and session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除该会话")
    if not current_user:
        default_user = session_manager.get_or_create_user(None)
        if session.user_id != default_user.id:
            raise HTTPException(status_code=403, detail="无权删除该会话")

    session_manager.delete_session(session_id)
    return {"message": "会话已删除", "session_id": session_id}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """
    处理聊天请求
    
    Args:
        request: 聊天请求
        db: 数据库会话
        
    Returns:
        聊天响应
    """
    try:
        # 安全检查
        security_check = SecurityFilter.handle_dangerous_input(request.message)
        if security_check["is_dangerous"]:
            return ChatResponse(
                reply=security_check["response"],
                session_id=0,
                message_id=0,
                show_help=security_check["show_help"],
                help_message=security_check.get("help_message")
            )
        
        # 获取或创建会话
        session_manager = SessionManager(db)
        if request.session_id:
            session = session_manager.get_session(request.session_id)
            if not session:
                raise HTTPException(status_code=404, detail="会话不存在")
            if current_user and session.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="无权访问该会话")
            if not current_user:
                default_user = session_manager.get_or_create_user(None)
                if session.user_id != default_user.id:
                    raise HTTPException(status_code=403, detail="无权访问该会话")
        else:
            session = session_manager.get_or_create_active_session(current_user.id if current_user else request.user_id)
        
        # 保存用户消息
        user_message = session_manager.add_message(
            session_id=session.id,
            role="user",
            content=request.message
        )
        
        # 获取对话历史
        conversation_history = session_manager.get_conversation_history(
            session_id=session.id,
            max_messages=20
        )
        
        # 获取用户偏好
        user = session_manager.get_or_create_user(current_user.id if current_user else request.user_id)
        user_preferences = user.preferences or {}

        # 跨会话长期记忆：新建对话时也能“记得”用户之前讲过的事情
        try:
            force_refresh = request.session_id is None  # 新会话更倾向刷新一次
            memory = MemoryService(db).ensure_memory_fresh(
                user_id=user.id,
                user_preferences=user_preferences,
                force=force_refresh,
            )
            if memory:
                user_preferences = dict(user_preferences or {})
                user_preferences["long_term_memory"] = memory
        except Exception:
            # 记忆失败不影响聊天主流程
            pass
        
        # 生成回复
        try:
            reply = model_api.generate_chat_response(
                user_message=request.message,
                conversation_history=conversation_history,
                user_preferences=user_preferences
            )
        except Exception as e:
            logger.error(f"生成回复失败: {e}")
            reply = "抱歉，我现在有些困惑。请稍后再试，或者换个方式表达。"
        
        # 安全过滤回复
        reply = SecurityFilter.filter_response(reply)
        
        # 保存助手回复
        assistant_message = session_manager.add_message(
            session_id=session.id,
            role="assistant",
            content=reply
        )
        
        return ChatResponse(
            reply=reply,
            session_id=session.id,
            message_id=assistant_message.id,
            metadata={
                "user_message_id": user_message.id
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"聊天处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"处理请求失败: {str(e)}")


@router.get("/session/{session_id}")
async def get_session_history(
    session_id: int,
    limit: Optional[int] = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """
    获取会话历史
    
    Args:
        session_id: 会话ID
        limit: 限制数量
        offset: 偏移量
        db: 数据库会话
        
    Returns:
        消息列表
    """
    session_manager = SessionManager(db)
    
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if current_user and session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该会话")
    if not current_user:
        default_user = session_manager.get_or_create_user(None)
        if session.user_id != default_user.id:
            raise HTTPException(status_code=403, detail="无权访问该会话")
    
    messages = session_manager.get_messages(
        session_id=session_id,
        limit=limit,
        offset=offset
    )
    
    return {
        "session_id": session_id,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat()
            }
            for msg in messages
        ]
    }


@router.get("/session")
async def get_active_session(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """
    获取活动会话
    
    Args:
        user_id: 用户ID
        db: 数据库会话
        
    Returns:
        会话信息
    """
    session_manager = SessionManager(db)
    session = session_manager.get_or_create_active_session(current_user.id if current_user else user_id)
    
    return {
        "session_id": session.id,
        "started_at": session.started_at.isoformat(),
        "last_active_at": session.last_active_at.isoformat()
    }
