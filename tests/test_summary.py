"""
摘要服务测试用例
"""
import pytest
from datetime import datetime, timedelta
from app.models.schema import SessionLocal, init_db, reset_engine, User, Session, Message
from app.services.summary_service import SummaryService
from app.services.session_manager import SessionManager
from app.config import settings
import tempfile
import os

# 使用临时数据库进行测试
test_db_path = tempfile.mktemp(suffix=".db")
settings.DB_PATH = test_db_path
reset_engine(settings.DB_PATH)


@pytest.fixture(autouse=True)
def setup_db():
    """测试前初始化数据库"""
    init_db()
    yield
    # 测试后清理
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


def test_generate_summary():
    """测试生成摘要"""
    db = SessionLocal()
    try:
        # 创建用户和会话
        user = User(display_name="测试用户", preferences={})
        db.add(user)
        db.commit()
        
        session = Session(user_id=user.id)
        db.add(session)
        db.commit()
        
        # 添加一些消息
        messages = [
            Message(session_id=session.id, role="user", content="我今天感觉很累"),
            Message(session_id=session.id, role="assistant", content="我理解你的感受"),
            Message(session_id=session.id, role="user", content="工作压力很大"),
        ]
        for msg in messages:
            db.add(msg)
        db.commit()
        
        # 生成摘要
        summary_service = SummaryService(db)
        summary = summary_service.generate_summary(user_id=user.id, window_days=7)
        
        assert summary is not None
        assert summary.content is not None
        assert len(summary.content) > 0
        
    finally:
        db.close()


def test_get_latest_summary():
    """测试获取最新摘要"""
    db = SessionLocal()
    try:
        summary_service = SummaryService(db)
        
        # 生成摘要
        summary1 = summary_service.generate_summary()
        
        # 获取最新摘要
        latest = summary_service.get_latest_summary()
        
        assert latest is not None
        assert latest.id == summary1.id
        
    finally:
        db.close()


def test_generate_care_message():
    """测试生成关怀消息"""
    db = SessionLocal()
    try:
        summary_service = SummaryService(db)
        
        # 生成摘要
        summary = summary_service.generate_summary()
        
        # 生成关怀消息
        care_message = summary_service.generate_care_message(
            summary=summary,
            time_of_day="morning"
        )
        
        assert care_message is not None
        assert len(care_message) > 0
        
    finally:
        db.close()


def test_get_summaries():
    """测试获取摘要列表"""
    db = SessionLocal()
    try:
        summary_service = SummaryService(db)
        
        # 生成几个摘要
        summary_service.generate_summary()
        summary_service.generate_summary()
        
        # 获取摘要列表
        summaries = summary_service.get_summaries(limit=10)
        
        assert len(summaries) >= 2
        
    finally:
        db.close()


