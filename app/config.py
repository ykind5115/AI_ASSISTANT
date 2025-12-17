"""
配置管理模块
管理应用的所有配置项，包括环境变量、数据库路径、模型配置等
"""
import os
from pathlib import Path
from typing import Optional
try:
    from pydantic_settings import BaseSettings
    from pydantic import Field
except ImportError:
    try:
        # pydantic v2 兼容层
        from pydantic.v1 import BaseSettings, Field  # type: ignore
    except Exception:
        # 兼容 pydantic v1
        from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用基础配置
    APP_NAME: str = "CareMate"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    
    # 数据库配置
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = DATA_DIR / "caremate.db"
    
    # 模型配置
    # 默认使用本地 GGUF 模型（llama.cpp 推理）：Llama3-8B-Chinese-Chat-Q5
    # 如需切回 transformers/HuggingFace 模型，可设置 MODEL_PATH 为空并指定 MODEL_NAME
    MODEL_NAME: str = Field(default="Llama3-8B-Chinese-Chat-Q5", env="MODEL_NAME")
    MODEL_PATH: Optional[str] = Field(default="data/models/Llama3-8B-Chinese-Chat-Q5", env="MODEL_PATH")
    DEVICE: str = Field(default="cuda", env="DEVICE")  # cpu, cuda, mps (cuda优先使用GPU)
    MAX_LENGTH: int = 256  # 减少生成长度，避免生成过长无意义文本
    TEMPERATURE: float = 0.5  # 降低温度，使生成更稳定
    TOP_P: float = 0.85  # 降低top_p，减少随机性
    REPETITION_PENALTY: float = 1.2  # 重复惩罚，避免重复生成
    
    # Embedding配置
    EMBEDDING_MODEL: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", env="EMBEDDING_MODEL")
    EMBEDDING_DIM: int = 384
    
    # 会话配置
    MAX_SESSION_HISTORY_DAYS: int = 30
    MAX_CONTEXT_LENGTH: int = 2048
    
    # 摘要配置
    SUMMARY_WINDOW_DAYS: int = 7  # 摘要时间窗口（天）
    SUMMARY_MAX_LENGTH: int = 200  # 摘要最大长度
    
    # 调度配置
    SCHEDULER_TIMEZONE: str = "Asia/Shanghai"
    
    # 安全配置
    ENABLE_CONTENT_FILTER: bool = True
    SENSITIVE_KEYWORDS: list = [
        "自杀", "自伤", "自残", "跳楼", "割腕", "上吊",
        "暴力", "仇恨", "歧视"
    ]
    
    # 通知配置
    ENABLE_DESKTOP_NOTIFICATION: bool = True
    
    # 加密配置
    ENCRYPT_DATA: bool = True
    ENCRYPTION_KEY_PATH: Path = DATA_DIR / ".encryption_key"
    
    # API配置
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"

    # 认证配置
    AUTH_TOKEN_EXPIRE_DAYS: int = 30
    AUTH_TOKEN_BYTES: int = 32
    
    # 日志配置
    LOG_DIR: Path = BASE_DIR / "logs"
    LOG_LEVEL: str = "INFO"
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        # pydantic v2 兼容
        extra = "ignore"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 确保必要的目录存在
        self.DATA_DIR.mkdir(exist_ok=True)
        self.LOG_DIR.mkdir(exist_ok=True)


# 全局配置实例
settings = Settings()
