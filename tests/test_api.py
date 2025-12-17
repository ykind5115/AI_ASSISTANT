"""
API测试用例
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.schema import SessionLocal, init_db, reset_engine
from app.config import settings
import tempfile
import os

# 使用临时数据库进行测试
test_db_path = tempfile.mktemp(suffix=".db")
settings.DB_PATH = test_db_path
reset_engine(settings.DB_PATH)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """测试前初始化数据库"""
    init_db()
    yield
    # 测试后清理
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


def test_health_check():
    """测试健康检查"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_chat():
    """测试聊天接口"""
    # 发送消息
    response = client.post(
        "/api/v1/chat",
        json={
            "message": "你好"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "session_id" in data
    assert data["session_id"] > 0


def test_get_session():
    """测试获取会话"""
    # 先创建一个会话
    chat_response = client.post(
        "/api/v1/chat",
        json={"message": "测试消息"}
    )
    session_id = chat_response.json()["session_id"]
    
    # 获取会话历史
    response = client.get(f"/api/v1/session/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert len(data["messages"]) > 0


def test_get_active_session():
    """测试获取活动会话"""
    response = client.get("/api/v1/session")
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data


def test_session_list_new_and_export():
    """测试会话列表/新建会话/导出单会话"""
    # 新建会话
    r = client.post("/api/v1/session/new")
    assert r.status_code == 200
    new_session_id = r.json()["session_id"]

    # 写入一条消息
    r = client.post("/api/v1/chat", json={"session_id": new_session_id, "message": "hello session"})
    assert r.status_code == 200

    # 会话列表应包含该会话
    r = client.get("/api/v1/sessions")
    assert r.status_code == 200
    sessions = r.json()
    assert any(s["session_id"] == new_session_id for s in sessions)

    # 导出单会话
    r = client.get(f"/api/v1/session/{new_session_id}/export")
    assert r.status_code == 200
    exported = r.json()
    assert exported["session"]["id"] == new_session_id
    assert isinstance(exported["messages"], list)
    assert any(m["role"] == "user" and "hello session" in m["content"] for m in exported["messages"])


def test_delete_session():
    """测试删除会话"""
    r = client.post("/api/v1/session/new")
    assert r.status_code == 200
    session_id = r.json()["session_id"]

    r = client.post("/api/v1/chat", json={"session_id": session_id, "message": "to be deleted"})
    assert r.status_code == 200

    r = client.delete(f"/api/v1/session/{session_id}")
    assert r.status_code == 200

    r = client.get(f"/api/v1/session/{session_id}")
    assert r.status_code == 404

def test_create_schedule():
    """测试创建调度任务"""
    response = client.post(
        "/api/v1/schedule",
        json={
            "cron_or_time": "08:00",
            "enabled": True
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["cron_or_time"] == "08:00"


def test_get_schedules():
    """测试获取调度列表"""
    # 先创建一个调度
    client.post(
        "/api/v1/schedule",
        json={"cron_or_time": "08:00"}
    )
    
    response = client.get("/api/v1/schedule")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_update_schedule():
    """测试更新调度"""
    # 创建调度
    create_response = client.post(
        "/api/v1/schedule",
        json={"cron_or_time": "08:00"}
    )
    schedule_id = create_response.json()["id"]
    
    # 更新调度
    response = client.put(
        f"/api/v1/schedule/{schedule_id}",
        json={"cron_or_time": "09:00"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["cron_or_time"] == "09:00"


def test_delete_schedule():
    """测试删除调度"""
    # 创建调度
    create_response = client.post(
        "/api/v1/schedule",
        json={"cron_or_time": "08:00"}
    )
    schedule_id = create_response.json()["id"]
    
    # 删除调度
    response = client.delete(f"/api/v1/schedule/{schedule_id}")
    assert response.status_code == 200


def test_get_summaries():
    """测试获取摘要列表"""
    response = client.get("/api/v1/summaries")
    assert response.status_code == 200
    data = response.json()
    assert "summaries" in data


def test_export_data():
    """测试导出数据"""
    # 先创建一些数据
    client.post("/api/v1/chat", json={"message": "测试"})
    
    response = client.post("/api/v1/export")
    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert "messages" in data


def test_auth_register_login_me_logout():
    """测试注册/登录/获取当前用户/退出"""
    r = client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "password": "password123", "display_name": "Alice"},
    )
    assert r.status_code == 200

    r = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password123"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Alice"

    r = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200

    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
