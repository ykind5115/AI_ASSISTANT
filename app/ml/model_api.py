"""
统一的模型推理接口
封装模型调用，提供统一的生成和嵌入接口
"""
from typing import Optional, List, Dict, Any
import logging
from app.ml.local_loader import LocalModelLoader
from app.config import settings

logger = logging.getLogger(__name__)


class ModelAPI:
    """模型API统一接口"""
    
    def __init__(self):
        self.loader = LocalModelLoader()
        self._model_loaded = False
    
    def initialize(self, model_name: Optional[str] = None, model_path: Optional[str] = None):
        """初始化模型"""
        if not self._model_loaded:
            self.loader.load_model(model_name, model_path)
            self._model_loaded = True
    
    def generate(
        self,
        prompt: str,
        max_length: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        生成文本
        
        Args:
            prompt: 输入提示词
            max_length: 最大生成长度
            temperature: 温度参数
            top_p: top_p采样参数
            **kwargs: 其他生成参数
            
        Returns:
            生成的文本
        """
        # 如果模型未加载，使用mock响应
        if not self.loader.is_loaded():
            logger.warning("模型未加载，使用Mock响应")
            return self.loader.generate_mock_response(prompt)
        
        try:
            # 设置默认参数
            max_length = max_length or settings.MAX_LENGTH
            temperature = temperature or settings.TEMPERATURE
            top_p = top_p or settings.TOP_P
            repetition_penalty = kwargs.pop('repetition_penalty', settings.REPETITION_PENALTY)
            
            max_new_tokens = min(max_length, 200)  # 限制新生成的token数量，避免生成过长无意义文本
            
            return self.loader.generate(
                prompt,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                **kwargs,
            )
            
        except Exception as e:
            logger.error(f"文本生成失败: {e}")
            # 失败时返回mock响应
            return self.loader.generate_mock_response(prompt)
    
    def generate_chat_response(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_preferences: Optional[Dict] = None
    ) -> str:
        """
        生成聊天回复
        
        Args:
            user_message: 用户消息
            conversation_history: 对话历史
            user_preferences: 用户偏好
            
        Returns:
            助手回复
        """
        from app.utils.prompts import PromptManager

        user_preferences = user_preferences or {}
        long_term_memory = user_preferences.get("long_term_memory")
        memory_hint = None
        if isinstance(long_term_memory, str) and long_term_memory.strip():
            memory_hint = long_term_memory.strip()

        # 约束：不要编造“你之前说过”的内容
        anti_hallucination = (
            "重要：如果你不确定用户以前是否提到过某件事，必须明确说明不确定，"
            "不要编造过去的对话内容；可以基于下方“长期记忆摘要”与当前消息进行回应。"
        )
        
        # 检查是否是Qwen系列模型（使用ChatML格式）
        model_name = settings.MODEL_NAME.lower()
        is_qwen = (
            "qwen" in model_name
            and getattr(self.loader, "backend", None) == "transformers"
            and self.loader.tokenizer is not None
        )
        
        if is_qwen:
            # Qwen模型使用ChatML格式
            messages = []
            
            # 添加系统消息
            messages.append({
                "role": "system",
                "content": PromptManager.SYSTEM_PROMPT
            })
            messages.append({"role": "system", "content": anti_hallucination})
            if memory_hint:
                messages.append(
                    {
                        "role": "system",
                        "content": f"用户长期记忆摘要（来自历史对话，可能不完整）：\n{memory_hint}",
                    }
                )
            
            # 添加对话历史
            if conversation_history:
                for msg in conversation_history[-10:]:  # 只保留最近10轮
                    role = msg.get("role", "user")
                    if role == "assistant":
                        messages.append({"role": "assistant", "content": msg.get("content", "")})
                    elif role == "user":
                        messages.append({"role": "user", "content": msg.get("content", "")})
            
            # 添加当前用户消息
            messages.append({"role": "user", "content": user_message})
            
            # 使用apply_chat_template构建prompt
            prompt = self.loader.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
        else:
            # 其他模型使用原来的格式
            if memory_hint:
                user_message = f"【用户长期记忆摘要（可能不完整）】\n{memory_hint}\n\n【当前用户消息】\n{user_message}"
            prompt = PromptManager.get_chat_prompt(
                user_message,
                conversation_history,
                user_preferences
            )
        
        # 生成回复
        response = self.generate(prompt, max_length=512)  # Qwen模型可以生成更长的回复
        
        # 清理回复（移除可能的重复或格式问题）
        response = self._clean_response(response)
        
        return response
    
    def generate_summary(
        self,
        messages: List[Dict[str, str]],
        window_start,
        window_end,
        user_preferences: Optional[Dict] = None
    ) -> str:
        """
        生成摘要
        
        Args:
            messages: 消息列表
            window_start: 窗口开始时间
            window_end: 窗口结束时间
            user_preferences: 用户偏好
            
        Returns:
            生成的摘要
        """
        from app.utils.prompts import PromptManager
        
        # 构建摘要prompt
        prompt = PromptManager.get_summary_prompt(
            messages,
            window_start,
            window_end,
            user_preferences
        )
        
        # 生成摘要
        summary = self.generate(prompt, max_length=settings.SUMMARY_MAX_LENGTH, temperature=0.5)
        
        return summary.strip()
    
    def generate_care_message(
        self,
        summary: str,
        template_content: Optional[str] = None,
        time_of_day: str = "morning"
    ) -> str:
        """
        生成关怀消息
        
        Args:
            summary: 摘要内容
            template_content: 模板内容
            time_of_day: 时段
            
        Returns:
            关怀消息
        """
        from app.utils.prompts import PromptManager
        
        # 构建消息prompt
        prompt = PromptManager.get_care_message_prompt(
            summary,
            template_content,
            time_of_day
        )
        
        # 生成消息
        message = self.generate(prompt, max_length=200, temperature=0.7)
        
        return message.strip()
    
    def _clean_response(self, response: str) -> str:
        """
        清理生成的回复
        
        Args:
            response: 原始回复
            
        Returns:
            清理后的回复
        """
        import re
        
        # 移除多余的空白
        response = " ".join(response.split())
        
        # 检测并移除重复的短语（常见问题）
        # 如果同一短语重复3次以上，可能是模型卡住了
        words = response.split()
        if len(words) > 10:
            # 检查是否有重复的短语
            for i in range(len(words) - 5):
                phrase = " ".join(words[i:i+3])
                if response.count(phrase) >= 3:
                    # 找到重复短语，只保留第一次出现
                    parts = response.split(phrase)
                    if len(parts) > 1:
                        response = phrase.join([parts[0], parts[-1]])
                    break
        
        # 移除可能的重复开头
        lines = response.split("\n")
        if len(lines) > 1:
            # 如果第一行很短，可能是标签，移除它
            if len(lines[0]) < 10:
                response = "\n".join(lines[1:])
        
        # 移除无意义的重复字符
        # 如果某个字符连续出现5次以上，可能是模型错误
        response = re.sub(r'(.)\1{4,}', r'\1', response)
        
        # 检测是否包含大量无意义字符（如果超过30%是重复字符，可能是错误生成）
        if len(response) > 20:
            char_counts = {}
            for char in response:
                char_counts[char] = char_counts.get(char, 0) + 1
            max_char_count = max(char_counts.values()) if char_counts else 0
            if max_char_count > len(response) * 0.3:
                # 如果某个字符占比过高，可能是错误生成
                logger.warning("检测到可能的错误生成，使用fallback响应")
                return "抱歉，我理解你的问题，但我的回答可能不够清晰。请换个方式问我，我会尽力帮助你。"
        
        # 限制长度
        max_length = 500
        if len(response) > max_length:
            # 在句号、问号、感叹号处截断
            for punct in ["。", "？", "！", ".", "?", "!"]:
                last_punct = response[:max_length].rfind(punct)
                if last_punct > max_length * 0.7:
                    response = response[:last_punct + 1]
                    break
            else:
                response = response[:max_length] + "..."
        
        # 如果回复太短或看起来无意义，返回默认回复
        if len(response.strip()) < 5:
            return "我理解你的问题。作为你的关怀助手，我会一直在这里支持你。"
        
        return response.strip()


# 全局模型API实例
model_api = ModelAPI()
