"""
安全过滤模块
检测和处理危险内容，确保生成内容的安全性
"""
import re
from typing import Tuple, List, Dict
from app.config import settings


class SecurityFilter:
    """安全过滤器"""
    
    # 危险关键词（可扩展）
    DANGER_KEYWORDS = settings.SENSITIVE_KEYWORDS
    
    # 紧急帮助信息
    EMERGENCY_HELP_MESSAGE = """
检测到您可能正在经历困难时刻。请记住：
- 您不是一个人，有人关心您
- 专业帮助是有效的，请考虑联系：
  * 心理危机干预热线：400-161-9995（24小时）
  * 当地心理健康中心
  * 信任的朋友或家人

如果您处于紧急情况，请立即拨打紧急电话。
"""
    
    @classmethod
    def check_content_safety(cls, content: str) -> Tuple[bool, str]:
        """
        检查内容安全性
        
        Args:
            content: 待检查的内容
            
        Returns:
            (is_safe, reason): 是否安全，如果不安全则返回原因
        """
        if not settings.ENABLE_CONTENT_FILTER:
            return True, ""
        
        content_lower = content.lower()
        
        # 检查危险关键词
        for keyword in cls.DANGER_KEYWORDS:
            if keyword in content:
                return False, f"检测到敏感内容：{keyword}"
        
        # 检查自伤/自杀相关模式
        self_harm_patterns = [
            r'不想.*活',
            r'结束.*生命',
            r'离开.*世界',
            r'伤害.*自己',
        ]
        
        for pattern in self_harm_patterns:
            if re.search(pattern, content):
                return False, "检测到可能涉及自伤的内容"
        
        return True, ""
    
    @classmethod
    def filter_response(cls, response: str) -> str:
        """
        过滤模型生成的回复，移除危险内容
        
        Args:
            response: 模型生成的回复
            
        Returns:
            过滤后的回复
        """
        # 检查回复安全性
        is_safe, reason = cls.check_content_safety(response)
        
        if not is_safe:
            # 如果回复本身不安全，返回安全提示
            return "我理解您可能正在经历困难。作为关怀助手，我建议您联系专业的心理健康服务。请记住，寻求帮助是勇敢的表现。"
        
        # 移除可能的危险建议
        dangerous_advice_patterns = [
            r'你应该.*伤害',
            r'建议.*自杀',
            r'可以.*自残',
        ]
        
        filtered_response = response
        for pattern in dangerous_advice_patterns:
            filtered_response = re.sub(pattern, '', filtered_response, flags=re.IGNORECASE)
        
        return filtered_response.strip()
    
    @classmethod
    def handle_dangerous_input(cls, user_input: str) -> Dict[str, any]:
        """
        处理危险用户输入
        
        Args:
            user_input: 用户输入
            
        Returns:
            处理结果字典，包含is_dangerous、response、show_help等字段
        """
        is_safe, reason = cls.check_content_safety(user_input)
        
        if not is_safe:
            return {
                "is_dangerous": True,
                "reason": reason,
                "response": "我注意到您可能正在经历困难。请记住，您不是一个人，专业帮助是有效的。如果您需要，我可以为您提供一些资源信息。",
                "show_help": True,
                "help_message": cls.EMERGENCY_HELP_MESSAGE
            }
        
        return {
            "is_dangerous": False,
            "response": None,
            "show_help": False
        }
    
    @classmethod
    def sanitize_for_storage(cls, content: str) -> str:
        """
        清理内容以便安全存储（移除特殊字符等）
        
        Args:
            content: 原始内容
            
        Returns:
            清理后的内容
        """
        # 移除控制字符
        content = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content)
        # 限制长度
        max_length = 10000
        if len(content) > max_length:
            content = content[:max_length] + "..."
        
        return content



