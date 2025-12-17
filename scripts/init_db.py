"""
数据库初始化脚本
创建数据库表和初始数据
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.models.schema import init_db, SessionLocal, User, Template
from app.config import settings
from datetime import datetime


def create_default_user():
    """创建默认用户"""
    db = SessionLocal()
    try:
        # 检查是否已有用户
        existing_user = db.query(User).first()
        if existing_user:
            print(f"默认用户已存在: {existing_user.display_name}")
            return existing_user
        
        # 创建默认用户
        default_user = User(
            display_name="用户",
            preferences={
                "tone": "温柔",  # 温柔/中性/鼓励型
                "avoid_topics": [],
                "goals": [],
                "notification_enabled": True,
                "notification_times": ["08:00", "12:00", "20:00"]
            }
        )
        db.add(default_user)
        db.commit()
        db.refresh(default_user)
        print(f"创建默认用户: {default_user.display_name} (ID: {default_user.id})")
        return default_user
    except Exception as e:
        db.rollback()
        print(f"创建默认用户失败: {e}")
        raise
    finally:
        db.close()


def create_default_templates():
    """创建默认推送模板"""
    db = SessionLocal()
    try:
        templates_data = [
            {
                "name": "早安关怀",
                "description": "早晨推送模板",
                "content": """早安！过去几天你提到在忙于{summary}。这是你做得不错的一点：{achievement}。今天的小建议：{suggestion}。我相信你可以做到，加油！"""
            },
            {
                "name": "午间提醒",
                "description": "中午推送模板",
                "content": """中午好！今天上午过得怎么样？记得{reminder}。保持节奏，你已经做得很好了！"""
            },
            {
                "name": "睡前回顾",
                "description": "晚上推送模板",
                "content": """晚上好！今天辛苦了。回顾一下今天：{summary}。明天又是新的一天，好好休息，晚安！"""
            }
        ]
        
        for template_data in templates_data:
            existing = db.query(Template).filter_by(name=template_data["name"]).first()
            if not existing:
                template = Template(**template_data)
                db.add(template)
                print(f"创建模板: {template.name}")
        
        db.commit()
        print("默认模板创建完成")
    except Exception as e:
        db.rollback()
        print(f"创建默认模板失败: {e}")
        raise
    finally:
        db.close()


def main():
    """主函数"""
    print("=" * 50)
    print("初始化CareMate数据库")
    print("=" * 50)
    
    # 创建数据库表
    print("\n1. 创建数据库表...")
    init_db()
    print("✓ 数据库表创建完成")
    
    # 创建默认用户
    print("\n2. 创建默认用户...")
    create_default_user()
    
    # 创建默认模板
    print("\n3. 创建默认模板...")
    create_default_templates()
    
    print("\n" + "=" * 50)
    print("数据库初始化完成！")
    print(f"数据库路径: {settings.DB_PATH}")
    print("=" * 50)


if __name__ == "__main__":
    main()



