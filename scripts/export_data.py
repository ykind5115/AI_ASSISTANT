"""
数据导出脚本
导出用户数据到JSON文件
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.models.schema import SessionLocal, User, Session, Message, Summary
from app.config import settings


def export_user_data(user_id: int = None, output_path: Path = None):
    """
    导出用户数据
    
    Args:
        user_id: 用户ID，如果为None则导出默认用户
        output_path: 输出文件路径
    """
    db = SessionLocal()
    
    try:
        # 获取用户
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
        else:
            user = db.query(User).first()
        
        if not user:
            print("未找到用户")
            return
        
        print(f"导出用户数据: {user.display_name} (ID: {user.id})")
        
        # 收集数据
        sessions = db.query(Session).filter(Session.user_id == user.id).all()
        session_ids = [s.id for s in sessions]
        
        messages = db.query(Message).filter(Message.session_id.in_(session_ids)).all()
        summaries = db.query(Summary).all()
        
        # 构建导出数据
        export_data = {
            "export_time": datetime.utcnow().isoformat(),
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
                    "generated_at": s.generated_at.isoformat(),
                    "metadata": s.summary_metadata
                }
                for s in summaries
            ],
            "statistics": {
                "total_sessions": len(sessions),
                "total_messages": len(messages),
                "total_summaries": len(summaries)
            }
        }
        
        # 确定输出路径
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = settings.DATA_DIR / f"export_{timestamp}.json"
        
        # 保存文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        print(f"数据导出完成: {output_path}")
        print(f"统计信息:")
        print(f"  - 会话数: {len(sessions)}")
        print(f"  - 消息数: {len(messages)}")
        print(f"  - 摘要数: {len(summaries)}")
        
    except Exception as e:
        print(f"导出失败: {e}")
        raise
    finally:
        db.close()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="导出CareMate用户数据")
    parser.add_argument("--user-id", type=int, help="用户ID")
    parser.add_argument("--output", type=str, help="输出文件路径")
    
    args = parser.parse_args()
    
    output_path = Path(args.output) if args.output else None
    
    export_user_data(args.user_id, output_path)


if __name__ == "__main__":
    main()

