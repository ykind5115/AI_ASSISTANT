"""
调度服务
管理定时推送任务
"""
from datetime import datetime, time
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from app.models.schema import Schedule, User
from app.services.summary_service import SummaryService
from app.services.session_manager import SessionManager
from app.utils.notifier import Notifier
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class SchedulerService:
    """调度服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.scheduler = BackgroundScheduler(timezone=settings.SCHEDULER_TIMEZONE)
        self.summary_service = SummaryService(db)
        self.session_manager = SessionManager(db)
        self._initialized = False
    
    def initialize(self):
        """初始化调度器"""
        if not self._initialized:
            self.scheduler.start()
            self._load_schedules()
            self._initialized = True
            logger.info("调度器初始化完成")
    
    def _load_schedules(self):
        """加载所有启用的调度任务"""
        schedules = self.db.query(Schedule).filter(Schedule.enabled == True).all()
        
        for schedule in schedules:
            try:
                self._add_schedule_job(schedule)
            except Exception as e:
                logger.error(f"加载调度任务失败 (ID: {schedule.id}): {e}")
    
    def _add_schedule_job(self, schedule: Schedule):
        """
        添加调度任务
        
        Args:
            schedule: 调度对象
        """
        job_id = f"schedule_{schedule.id}"
        
        # 解析cron表达式或时间
        trigger = self._parse_schedule_trigger(schedule.cron_or_time)
        
        if trigger:
            self.scheduler.add_job(
                func=self._send_care_message,
                trigger=trigger,
                id=job_id,
                args=[schedule.id],
                replace_existing=True
            )
            logger.info(f"添加调度任务: {job_id}")
    
    def _parse_schedule_trigger(self, cron_or_time: str):
        """
        解析调度触发器
        
        Args:
            cron_or_time: cron表达式或时间字符串 (HH:MM)
            
        Returns:
            触发器对象
        """
        # 尝试解析为时间格式 (HH:MM)
        try:
            hour, minute = map(int, cron_or_time.split(":"))
            return CronTrigger(hour=hour, minute=minute)
        except ValueError:
            pass
        
        # 尝试解析为cron表达式
        try:
            parts = cron_or_time.split()
            if len(parts) == 5:
                # 标准cron格式: minute hour day month day_of_week
                return CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4]
                )
        except Exception:
            pass
        
        logger.warning(f"无法解析调度表达式: {cron_or_time}")
        return None
    
    def _send_care_message(self, schedule_id: int):
        """
        发送关怀消息（调度任务回调）
        
        Args:
            schedule_id: 调度ID
        """
        try:
            # 获取调度配置
            schedule = self.db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not schedule or not schedule.enabled:
                return
            
            # 确定时段
            current_hour = datetime.now().hour
            if 5 <= current_hour < 12:
                time_of_day = "morning"
            elif 12 <= current_hour < 18:
                time_of_day = "noon"
            else:
                time_of_day = "evening"
            
            # 生成关怀消息
            care_message = self.summary_service.generate_care_message(
                template_id=schedule.template_id,
                time_of_day=time_of_day
            )
            
            # 获取用户
            user = self.db.query(User).filter(User.id == schedule.user_id).first()
            if not user:
                return
            
            # 发送通知
            Notifier.send_notification(
                title="CareMate关怀提醒",
                message=care_message,
                duration=10
            )
            
            # 可选：将消息保存到会话
            session = self.session_manager.get_or_create_active_session(schedule.user_id)
            self.session_manager.add_message(
                session_id=session.id,
                role="assistant",
                content=care_message
            )
            
            # 更新最后触发时间
            schedule.last_triggered_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"发送关怀消息: schedule_id={schedule_id}")
            
        except Exception as e:
            logger.error(f"发送关怀消息失败: {e}")
    
    def create_schedule(
        self,
        user_id: int,
        cron_or_time: str,
        template_id: Optional[int] = None,
        enabled: bool = True
    ) -> Schedule:
        """
        创建调度任务
        
        Args:
            user_id: 用户ID
            cron_or_time: cron表达式或时间
            template_id: 模板ID
            enabled: 是否启用
            
        Returns:
            调度对象
        """
        schedule = Schedule(
            user_id=user_id,
            cron_or_time=cron_or_time,
            template_id=template_id,
            enabled=enabled
        )
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        
        # 添加到调度器
        if enabled:
            self._add_schedule_job(schedule)
        
        logger.info(f"创建调度任务: {schedule.id}")
        return schedule
    
    def update_schedule(
        self,
        schedule_id: int,
        cron_or_time: Optional[str] = None,
        template_id: Optional[int] = None,
        enabled: Optional[bool] = None
    ) -> Optional[Schedule]:
        """
        更新调度任务
        
        Args:
            schedule_id: 调度ID
            cron_or_time: 新的cron表达式或时间
            template_id: 新的模板ID
            enabled: 是否启用
            
        Returns:
            更新后的调度对象
        """
        schedule = self.db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule:
            return None
        
        # 移除旧任务
        job_id = f"schedule_{schedule_id}"
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass
        
        # 更新字段
        if cron_or_time is not None:
            schedule.cron_or_time = cron_or_time
        if template_id is not None:
            schedule.template_id = template_id
        if enabled is not None:
            schedule.enabled = enabled
        
        self.db.commit()
        self.db.refresh(schedule)
        
        # 重新添加任务
        if schedule.enabled:
            self._add_schedule_job(schedule)
        
        logger.info(f"更新调度任务: {schedule_id}")
        return schedule
    
    def delete_schedule(self, schedule_id: int) -> bool:
        """
        删除调度任务
        
        Args:
            schedule_id: 调度ID
            
        Returns:
            是否成功
        """
        schedule = self.db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule:
            return False
        
        # 移除任务
        job_id = f"schedule_{schedule_id}"
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass
        
        self.db.delete(schedule)
        self.db.commit()
        
        logger.info(f"删除调度任务: {schedule_id}")
        return True
    
    def get_schedules(self, user_id: Optional[int] = None) -> List[Schedule]:
        """
        获取调度任务列表
        
        Args:
            user_id: 用户ID
            
        Returns:
            调度任务列表
        """
        query = self.db.query(Schedule)
        if user_id:
            query = query.filter(Schedule.user_id == user_id)
        return query.all()
    
    def shutdown(self):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("调度器已关闭")



