"""
调度API
提供定时推送管理接口
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.schema import get_db
from app.api.deps import get_current_user_optional
from app.models.schema import User, Schedule
from app.services.scheduler_service import SchedulerService
from app.services.session_manager import SessionManager
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ScheduleCreate(BaseModel):
    """创建调度请求"""
    user_id: Optional[int] = None
    cron_or_time: str  # cron表达式或时间 (HH:MM)
    template_id: Optional[int] = None
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    """更新调度请求"""
    cron_or_time: Optional[str] = None
    template_id: Optional[int] = None
    enabled: Optional[bool] = None


class ScheduleResponse(BaseModel):
    """调度响应"""
    id: int
    user_id: int
    cron_or_time: str
    template_id: Optional[int]
    enabled: bool
    last_triggered_at: Optional[str] = None
    created_at: str


@router.post("/schedule", response_model=ScheduleResponse)
async def create_schedule(
    request: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """
    创建定时推送任务
    
    Args:
        request: 创建请求
        db: 数据库会话
        
    Returns:
        调度对象
    """
    try:
        session_manager = SessionManager(db)
        user = session_manager.get_or_create_user(current_user.id if current_user else request.user_id)
        
        scheduler_service = SchedulerService(db)
        scheduler_service.initialize()
        
        schedule = scheduler_service.create_schedule(
            user_id=user.id,
            cron_or_time=request.cron_or_time,
            template_id=request.template_id,
            enabled=request.enabled
        )
        
        return ScheduleResponse(
            id=schedule.id,
            user_id=schedule.user_id,
            cron_or_time=schedule.cron_or_time,
            template_id=schedule.template_id,
            enabled=schedule.enabled,
            last_triggered_at=schedule.last_triggered_at.isoformat() if schedule.last_triggered_at else None,
            created_at=schedule.created_at.isoformat()
        )
        
    except Exception as e:
        logger.error(f"创建调度失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建调度失败: {str(e)}")


@router.put("/schedule/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    request: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """
    更新定时推送任务
    
    Args:
        schedule_id: 调度ID
        request: 更新请求
        db: 数据库会话
        
    Returns:
        更新后的调度对象
    """
    try:
        if current_user:
            existing = db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not existing:
                raise HTTPException(status_code=404, detail="调度任务不存在")
            if existing.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="无权操作该调度任务")
        else:
            session_manager = SessionManager(db)
            default_user = session_manager.get_or_create_user(None)
            existing = db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not existing:
                raise HTTPException(status_code=404, detail="调度任务不存在")
            if existing.user_id != default_user.id:
                raise HTTPException(status_code=403, detail="无权操作该调度任务")

        scheduler_service = SchedulerService(db)
        scheduler_service.initialize()
        
        schedule = scheduler_service.update_schedule(
            schedule_id=schedule_id,
            cron_or_time=request.cron_or_time,
            template_id=request.template_id,
            enabled=request.enabled
        )
        
        if not schedule:
            raise HTTPException(status_code=404, detail="调度任务不存在")
        
        return ScheduleResponse(
            id=schedule.id,
            user_id=schedule.user_id,
            cron_or_time=schedule.cron_or_time,
            template_id=schedule.template_id,
            enabled=schedule.enabled,
            last_triggered_at=schedule.last_triggered_at.isoformat() if schedule.last_triggered_at else None,
            created_at=schedule.created_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新调度失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新调度失败: {str(e)}")


@router.delete("/schedule/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """
    删除定时推送任务
    
    Args:
        schedule_id: 调度ID
        db: 数据库会话
        
    Returns:
        删除结果
    """
    try:
        if current_user:
            existing = db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not existing:
                raise HTTPException(status_code=404, detail="调度任务不存在")
            if existing.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="无权操作该调度任务")
        else:
            session_manager = SessionManager(db)
            default_user = session_manager.get_or_create_user(None)
            existing = db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not existing:
                raise HTTPException(status_code=404, detail="调度任务不存在")
            if existing.user_id != default_user.id:
                raise HTTPException(status_code=403, detail="无权操作该调度任务")

        scheduler_service = SchedulerService(db)
        scheduler_service.initialize()
        
        success = scheduler_service.delete_schedule(schedule_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="调度任务不存在")
        
        return {"message": "调度任务已删除", "schedule_id": schedule_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除调度失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除调度失败: {str(e)}")


@router.get("/schedule", response_model=List[ScheduleResponse])
async def get_schedules(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """
    获取调度任务列表
    
    Args:
        user_id: 用户ID
        db: 数据库会话
        
    Returns:
        调度任务列表
    """
    try:
        scheduler_service = SchedulerService(db)
        if current_user:
            if user_id is not None and user_id != current_user.id:
                raise HTTPException(status_code=403, detail="无权访问该用户的调度任务")
            user_id = current_user.id
        else:
            session_manager = SessionManager(db)
            default_user = session_manager.get_or_create_user(None)
            if user_id is not None and user_id != default_user.id:
                raise HTTPException(status_code=403, detail="无权访问该用户的调度任务")
            user_id = default_user.id
        schedules = scheduler_service.get_schedules(user_id)
        
        return [
            ScheduleResponse(
                id=s.id,
                user_id=s.user_id,
                cron_or_time=s.cron_or_time,
                template_id=s.template_id,
                enabled=s.enabled,
                last_triggered_at=s.last_triggered_at.isoformat() if s.last_triggered_at else None,
                created_at=s.created_at.isoformat()
            )
            for s in schedules
        ]
        
    except Exception as e:
        logger.error(f"获取调度列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取调度列表失败: {str(e)}")


@router.post("/schedule/{schedule_id}/trigger")
async def trigger_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """
    手动触发调度任务（用于测试）
    
    Args:
        schedule_id: 调度ID
        db: 数据库会话
        
    Returns:
        触发结果
    """
    try:
        if current_user:
            existing = db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not existing:
                raise HTTPException(status_code=404, detail="调度任务不存在")
            if existing.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="无权操作该调度任务")
        else:
            session_manager = SessionManager(db)
            default_user = session_manager.get_or_create_user(None)
            existing = db.query(Schedule).filter(Schedule.id == schedule_id).first()
            if not existing:
                raise HTTPException(status_code=404, detail="调度任务不存在")
            if existing.user_id != default_user.id:
                raise HTTPException(status_code=403, detail="无权操作该调度任务")

        scheduler_service = SchedulerService(db)
        scheduler_service.initialize()
        
        scheduler_service._send_care_message(schedule_id)
        
        return {"message": "调度任务已触发", "schedule_id": schedule_id}
        
    except Exception as e:
        logger.error(f"触发调度失败: {e}")
        raise HTTPException(status_code=500, detail=f"触发调度失败: {str(e)}")

