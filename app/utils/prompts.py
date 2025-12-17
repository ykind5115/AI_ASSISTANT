"""
Prompt模板管理
定义系统提示词和各类生成任务的模板
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from app.config import settings


class PromptManager:
    """Prompt管理器"""
    
    # 系统提示词（中性文本提示，适配多种后端）
    SYSTEM_PROMPT = """你是一个关怀型的智能助手，名字叫CareMate。你的角色是：
1. 像朋友一样倾听用户的感受和想法
2. 给予温暖、鼓励和支持的话语
3. 帮助用户缓解孤独感和情绪困扰
4. 提供积极的生活建议和动力

重要约束：
- 你只能提供情感支持和一般性建议
- 不得提供医疗诊断、法律建议或专业治疗建议
- 如果用户提到自伤、自杀等严重情况，应温和地建议他们联系专业机构
- 使用温暖、同理心的语言，避免冷漠或机械化的回复
- 保持积极正面的态度，但也要理解用户的真实感受

请用自然、温暖的方式与用户对话。"""

    @staticmethod
    def get_chat_prompt(
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_preferences: Optional[Dict] = None
    ) -> str:
        """
        构建对话提示词
        
        Args:
            user_message: 用户消息
            conversation_history: 对话历史 [{"role": "user", "content": "..."}, ...]
            user_preferences: 用户偏好设置
        """
        prompt_parts = [PromptManager.SYSTEM_PROMPT]
        
        # 添加用户偏好信息
        if user_preferences:
            tone = user_preferences.get("tone", "温柔")
            goals = user_preferences.get("goals", [])
            
            if tone:
                prompt_parts.append(f"\n用户偏好语气：{tone}")
            if goals:
                prompt_parts.append(f"\n用户当前目标：{', '.join(goals)}")
        
        # 添加对话历史
        if conversation_history:
            prompt_parts.append("\n\n对话历史：")
            for msg in conversation_history[-10:]:  # 只保留最近10轮对话
                role_name = {"user": "用户", "assistant": "助手"}.get(msg.get("role"), msg.get("role"))
                prompt_parts.append(f"{role_name}：{msg.get('content', '')}")
        
        # 添加当前用户消息
        prompt_parts.append(f"\n\n用户：{user_message}")
        prompt_parts.append("\n助手：")
        
        return "\n".join(prompt_parts)
    
    @staticmethod
    def get_summary_prompt(
        messages: List[Dict[str, str]],
        window_start: datetime,
        window_end: datetime,
        user_preferences: Optional[Dict] = None
    ) -> str:
        """
        构建摘要生成提示词
        
        Args:
            messages: 时间窗口内的消息列表
            window_start: 窗口开始时间
            window_end: 窗口结束时间
            user_preferences: 用户偏好
        """
        # 提取用户消息
        user_messages = [
            msg.get("content", "") 
            for msg in messages 
            if msg.get("role") == "user"
        ]
        
        date_range = f"{window_start.strftime('%Y-%m-%d')} 至 {window_end.strftime('%Y-%m-%d')}"
        
        prompt = f"""请基于以下时间范围（{date_range}）内用户的对话内容，生成一份关怀型摘要。

用户对话内容：
{chr(10).join([f"- {msg}" for msg in user_messages[-20:]])}

请生成包含以下部分的摘要（用中文）：
1. 行为/成就总结（2-3句话）：总结用户这段时间的主要活动、提到的目标或取得的进展
2. 情绪观察（1-2句话）：简要描述用户这段时间的情绪状态和变化
3. 当日建议（1-2条）：基于用户的情况，给出1-2条具体可执行的建议
4. 鼓励话语（1段）：写一段温暖、鼓励的话语

格式要求：
- 语言温暖、积极
- 建议要具体、可执行
- 总长度控制在200字以内

摘要："""
        
        return prompt
    
    @staticmethod
    def get_care_message_prompt(
        summary: str,
        template_content: Optional[str] = None,
        time_of_day: str = "morning"  # morning, noon, evening
    ) -> str:
        """
        构建关怀推送消息提示词
        
        Args:
            summary: 生成的摘要
            template_content: 模板内容（可选）
            time_of_day: 时段
        """
        time_greetings = {
            "morning": "早安",
            "noon": "中午好",
            "evening": "晚上好"
        }
        greeting = time_greetings.get(time_of_day, "你好")
        
        if template_content:
            # 使用模板
            prompt = f"""基于以下摘要，使用提供的模板生成一条关怀消息。

摘要内容：
{summary}

模板：
{template_content}

请将摘要中的信息自然地填充到模板中，生成一条完整、温暖的消息。"""
        else:
            # 不使用模板，直接生成
            prompt = f"""基于以下摘要，生成一条{greeting}关怀消息。

摘要内容：
{summary}

要求：
- 以"{greeting}"开头
- 包含摘要中的关键信息
- 语言温暖、鼓励
- 长度控制在100-150字
- 给出1-2条具体建议

消息："""
        
        return prompt
    
    @staticmethod
    def get_safety_check_prompt(content: str) -> str:
        """
        构建安全检查提示词
        
        Args:
            content: 需要检查的内容
        """
        return f"""请检查以下内容是否包含以下危险内容：
1. 自伤、自杀相关内容
2. 暴力、仇恨言论
3. 鼓励危险行为的内容

内容：
{content}

请只回答：安全 或 危险（如果危险，请简要说明原因）"""
