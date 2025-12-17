"""
摘要生成服务
负责生成对话摘要和关怀消息
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.schema import Summary, Message, Session as DBSession
from app.services.session_manager import SessionManager
from app.ml.model_api import model_api
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class SummaryService:
    """摘要服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.session_manager = SessionManager(db)
    
    def generate_summary(
        self,
        user_id: Optional[int] = None,
        window_days: Optional[int] = None,
        force_regenerate: bool = False
    ) -> Summary:
        """
        生成时间窗口内的摘要
        
        Args:
            user_id: 用户ID
            window_days: 时间窗口天数
            force_regenerate: 是否强制重新生成
            
        Returns:
            摘要对象
        """
        window_days = window_days or settings.SUMMARY_WINDOW_DAYS
        window_end = datetime.utcnow()
        window_start = window_end - timedelta(days=window_days)
        
        # 检查是否已有摘要
        if not force_regenerate:
            existing = self.db.query(Summary).filter(
                and_(
                    Summary.window_start >= window_start - timedelta(hours=1),
                    Summary.window_end <= window_end + timedelta(hours=1)
                )
            ).order_by(Summary.generated_at.desc()).first()
            
            if existing:
                logger.info(f"使用已有摘要: {existing.id}")
                return existing
        
        # 获取时间窗口内的消息
        messages = self.session_manager.get_recent_messages(
            user_id=user_id,
            days=window_days
        )
        
        if not messages:
            # 如果没有消息，生成默认摘要
            summary_content = "这段时间您还没有开始对话。随时可以和我聊聊，我会在这里陪伴您。"
        else:
            # 转换为模型输入格式
            message_list = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
            
            # 获取用户偏好
            user = self.session_manager.get_or_create_user(user_id)
            user_preferences = user.preferences or {}
            
            # 生成摘要
            try:
                summary_content = model_api.generate_summary(
                    message_list,
                    window_start,
                    window_end,
                    user_preferences
                )
            except Exception as e:
                logger.error(f"摘要生成失败: {e}")
                summary_content = "这段时间您进行了多次对话。继续保持，我会一直在这里支持您。"
        
        # 保存摘要
        summary = Summary(
            window_start=window_start,
            window_end=window_end,
            content=summary_content,
            generated_at=datetime.utcnow(),
            summary_metadata={
                "message_count": len(messages),
                "window_days": window_days
            }
        )
        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)
        
        logger.info(f"生成摘要: {summary.id}")
        return summary
    
    def get_latest_summary(self, user_id: Optional[int] = None) -> Optional[Summary]:
        """
        获取最新的摘要
        
        Args:
            user_id: 用户ID（目前单用户，暂不使用）
            
        Returns:
            摘要对象或None
        """
        return self.db.query(Summary).order_by(
            Summary.generated_at.desc()
        ).first()
    
    def generate_care_message(
        self,
        summary: Optional[Summary] = None,
        template_id: Optional[int] = None,
        time_of_day: str = "morning"
    ) -> str:
        """
        基于摘要生成关怀消息
        
        Args:
            summary: 摘要对象，如果为None则自动生成
            template_id: 模板ID
            time_of_day: 时段 (morning/noon/evening)
            
        Returns:
            关怀消息内容
        """
        # 获取摘要
        if not summary:
            summary = self.generate_summary()
        
        # 获取模板（如果有）
        template_content = None
        if template_id:
            from app.models.schema import Template
            template = self.db.query(Template).filter(Template.id == template_id).first()
            if template:
                template_content = template.content
        
        # 生成消息
        try:
            message = model_api.generate_care_message(
                summary.content,
                template_content,
                time_of_day
            )
        except Exception as e:
            logger.error(f"关怀消息生成失败: {e}")
            # 生成简单的默认消息
            greetings = {
                "morning": "早安",
                "noon": "中午好",
                "evening": "晚上好"
            }
            greeting = greetings.get(time_of_day, "你好")
            message = f"{greeting}！{summary.content[:100]}... 继续加油！"
        
        return message
    
    def get_summaries(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 10
    ) -> List[Summary]:
        """
        获取摘要列表
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            limit: 限制数量
            
        Returns:
            摘要列表
        """
        query = self.db.query(Summary)
        
        if start_date:
            query = query.filter(Summary.window_start >= start_date)
        if end_date:
            query = query.filter(Summary.window_end <= end_date)
        
        return query.order_by(Summary.generated_at.desc()).limit(limit).all()

