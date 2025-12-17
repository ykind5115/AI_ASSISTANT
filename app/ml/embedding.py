"""
嵌入向量服务
用于生成文本的向量表示，支持记忆检索
"""
import logging
from typing import List, Optional
import numpy as np
try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except ImportError:  # pragma: no cover
    SentenceTransformer = None
from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """嵌入向量服务"""
    
    def __init__(self):
        self.model = None
        self._model_loaded = False
    
    def initialize(self, model_name: Optional[str] = None):
        """初始化嵌入模型"""
        if not self._model_loaded:
            try:
                model_name = model_name or settings.EMBEDDING_MODEL
                logger.info(f"正在加载嵌入模型: {model_name}")
                if SentenceTransformer is None:
                    raise ImportError("sentence-transformers is not installed")
                self.model = SentenceTransformer(model_name)
                self._model_loaded = True
                logger.info("嵌入模型加载完成")
            except Exception as e:
                logger.error(f"嵌入模型加载失败: {e}")
                self.model = None
    
    def is_loaded(self) -> bool:
        """检查模型是否已加载"""
        return self.model is not None
    
    def encode(self, texts: List[str]) -> np.ndarray:
        """
        将文本编码为向量
        
        Args:
            texts: 文本列表
            
        Returns:
            向量数组 (n, dim)
        """
        if not self.is_loaded():
            logger.warning("嵌入模型未加载，返回零向量")
            # 返回零向量作为fallback
            return np.zeros((len(texts), settings.EMBEDDING_DIM))
        
        try:
            embeddings = self.model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            return embeddings
        except Exception as e:
            logger.error(f"文本编码失败: {e}")
            return np.zeros((len(texts), settings.EMBEDDING_DIM))
    
    def encode_single(self, text: str) -> np.ndarray:
        """
        编码单个文本
        
        Args:
            text: 文本
            
        Returns:
            向量 (dim,)
        """
        return self.encode([text])[0]
    
    def similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        计算两个向量的余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
            
        Returns:
            相似度分数 (0-1)
        """
        # 归一化
        vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-8)
        vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-8)
        
        # 计算余弦相似度
        similarity = np.dot(vec1_norm, vec2_norm)
        return float(similarity)


# 全局嵌入服务实例
embedding_service = EmbeddingService()


