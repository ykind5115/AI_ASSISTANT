"""
主应用入口
FastAPI应用启动和配置
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.config import settings
from app.api.v1 import chat, schedule, auth
from app.services.scheduler_service import SchedulerService
from app.models.schema import get_db, init_db
from app.ml.model_api import model_api
from app.ml.embedding import embedding_service
import logging.config

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.LOG_DIR / "caremate.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("=" * 50)
    logger.info(f"启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("=" * 50)
    
    # 初始化数据库
    logger.info("初始化数据库...")
    init_db()
    logger.info("数据库初始化完成")
    
    # 初始化模型
    logger.info("初始化模型...")
    logger.info(f"模型配置: MODEL_NAME={settings.MODEL_NAME}, MODEL_PATH={settings.MODEL_PATH}, DEVICE={settings.DEVICE}")
    try:
        model_api.initialize()
        if model_api.loader.is_loaded():
            logger.info("模型初始化完成")
        else:
            logger.warning("模型初始化完成，但模型未成功加载，将使用Mock模式")
    except Exception as e:
        import traceback
        logger.error(f"模型初始化失败，将使用Mock模式: {e}")
        logger.error(f"错误详情: {traceback.format_exc()}")
    
    # 初始化嵌入服务
    logger.info("初始化嵌入服务...")
    try:
        embedding_service.initialize()
        logger.info("嵌入服务初始化完成")
    except Exception as e:
        logger.warning(f"嵌入服务初始化失败: {e}")
    
    # 初始化调度器
    logger.info("初始化调度器...")
    try:
        db = next(get_db())
        scheduler_service = SchedulerService(db)
        scheduler_service.initialize()
        logger.info("调度器初始化完成")
    except Exception as e:
        logger.error(f"调度器初始化失败: {e}")
    
    logger.info("=" * 50)
    logger.info("应用启动完成")
    logger.info(f"API地址: http://{settings.API_HOST}:{settings.API_PORT}")
    logger.info("=" * 50)
    
    yield
    
    # 关闭时清理
    logger.info("正在关闭应用...")
    try:
        db = next(get_db())
        scheduler_service = SchedulerService(db)
        scheduler_service.shutdown()
    except Exception:
        pass
    logger.info("应用已关闭")


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="关怀型本地大模型聊天应用",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router, prefix=settings.API_PREFIX, tags=["聊天"])
app.include_router(schedule.router, prefix=settings.API_PREFIX, tags=["调度"])
app.include_router(auth.router, prefix=settings.API_PREFIX, tags=["认证"])


# 添加其他API端点
@app.get("/api/v1/summaries")
async def get_summaries(
    start_date: str = None,
    end_date: str = None,
    limit: int = 10,
    db = Depends(get_db)
):
    """获取摘要列表"""
    from datetime import datetime
    from app.services.summary_service import SummaryService
    summary_service = SummaryService(db)
    
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    
    summaries = summary_service.get_summaries(start, end, limit)
    
    return {
        "summaries": [
            {
                "id": s.id,
                "window_start": s.window_start.isoformat(),
                "window_end": s.window_end.isoformat(),
                "content": s.content,
                "generated_at": s.generated_at.isoformat(),
                "metadata": s.summary_metadata
            }
            for s in summaries
        ]
    }


@app.post("/api/v1/export")
async def export_data(
    db = Depends(get_db)
):
    """导出用户数据"""
    from app.services.session_manager import SessionManager
    from app.models.schema import User, Session, Message, Summary
    import json
    session_manager = SessionManager(db)
    user = session_manager.get_or_create_user()
    
    # 收集所有数据
    sessions = db.query(Session).filter(Session.user_id == user.id).all()
    session_ids = [s.id for s in sessions]
    
    messages = db.query(Message).filter(Message.session_id.in_(session_ids)).all()
    summaries = db.query(Summary).all()
    
    export_data = {
        "user": {
            "id": user.id,
            "display_name": user.display_name,
            "preferences": user.preferences,
            "created_at": user.created_at.isoformat()
        },
        "sessions": [
            {
                "id": s.id,
                "started_at": s.started_at.isoformat(),
                "last_active_at": s.last_active_at.isoformat(),
                "meta": s.meta
            }
            for s in sessions
        ],
        "messages": [
            {
                "id": m.id,
                "session_id": m.session_id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ],
        "summaries": [
            {
                "id": s.id,
                "window_start": s.window_start.isoformat(),
                "window_end": s.window_end.isoformat(),
                "content": s.content,
                "generated_at": s.generated_at.isoformat()
            }
            for s in summaries
        ]
    }
    
    return export_data


@app.delete("/api/v1/data")
async def delete_data(
    confirm: bool = False,
    db = Depends(get_db)
):
    """删除用户数据（需确认）"""
    if not confirm:
        raise HTTPException(status_code=400, detail="需要确认参数 confirm=true")
    
    from app.services.session_manager import SessionManager
    from app.models.schema import User, Session, Message, Summary
    session_manager = SessionManager(db)
    user = session_manager.get_or_create_user()
    
    # 删除所有相关数据
    sessions = db.query(Session).filter(Session.user_id == user.id).all()
    session_ids = [s.id for s in sessions]
    
    db.query(Message).filter(Message.session_id.in_(session_ids)).delete()
    db.query(Session).filter(Session.user_id == user.id).delete()
    db.query(Summary).delete()
    
    db.commit()
    
    return {"message": "数据已删除"}


# 静态文件服务（前端）
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path / "static")), name="static")
    
    @app.get("/")
    async def read_root():
        """返回前端页面"""
        index_file = frontend_path / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "CareMate API", "version": settings.APP_VERSION}


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )
