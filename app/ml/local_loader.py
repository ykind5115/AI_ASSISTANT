"""
本地模型加载器
负责加载和管理本地大语言模型
"""
import logging
import os
from pathlib import Path
from typing import Optional

try:
    import torch  # type: ignore
except ImportError:  # pragma: no cover
    torch = None

try:
    from transformers import (
        AutoTokenizer,
        AutoModelForCausalLM,
        pipeline,
    )
except ImportError:  # pragma: no cover
    AutoTokenizer = None
    AutoModelForCausalLM = None
    pipeline = None

try:
    from llama_cpp import Llama  # type: ignore
except ImportError:  # pragma: no cover
    Llama = None

from app.config import settings

logger = logging.getLogger(__name__)


class LocalModelLoader:
    """本地模型加载器"""

    def __init__(self):
        self.backend: str = "none"  # transformers | llama_cpp | mock | none
        self.model = None
        self.tokenizer = None
        self.device = self._get_device()
        self.generator = None

    def _get_device(self) -> str:
        """检测可用设备，优先使用GPU"""
        if torch is None:
            logger.warning("未安装torch，将使用Mock模式（不加载transformers模型）")
            return "cpu"
        device_setting = settings.DEVICE.lower()

        # 优先使用CUDA（GPU）
        if device_setting in {"cuda", "auto"}:
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
                logger.info(f"使用CUDA GPU: {gpu_name}")
                logger.info(f"  GPU显存: {gpu_memory:.2f} GB")
                logger.info(f"  CUDA版本: {torch.version.cuda}")
                return "cuda"
            if device_setting == "cuda":
                logger.error("配置要求使用CUDA，但CUDA不可用！")
                logger.error("  请检查：")
                logger.error("  1. PyTorch是否安装了CUDA版本")
                logger.error("  2. NVIDIA驱动是否正确安装")
                logger.error("  3. 运行: python scripts/check_cuda.py 进行诊断")
            else:
                logger.warning("未检测到CUDA，尝试其他设备...")

        # 其次尝试MPS（Apple Silicon）
        if device_setting == "mps" or (device_setting == "auto" and not torch.cuda.is_available()):
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                logger.info("使用MPS (Apple Silicon GPU)")
                return "mps"

        # 最后回退到CPU
        if device_setting == "cpu":
            logger.info("使用CPU（手动指定）")
        else:
            logger.warning("未检测到GPU，回退到CPU模式")
            logger.warning("  性能会较慢，建议安装CUDA版本的PyTorch")
        return "cpu"

    def _find_gguf_file(self, model_path: str) -> Optional[str]:
        path = Path(model_path)
        if path.is_file() and path.suffix.lower() == ".gguf":
            return str(path)
        if path.is_dir():
            candidates = list(path.glob("*.gguf"))
            if not candidates:
                return None
            best = max(candidates, key=lambda p: p.stat().st_size)
            return str(best)
        return None

    def _load_gguf_model(self, gguf_path: str) -> None:
        if Llama is None:
            raise RuntimeError("检测到 .gguf 模型，但未安装 llama-cpp-python；请安装后重试。")

        n_ctx = int(os.getenv("LLAMA_N_CTX", str(settings.MAX_CONTEXT_LENGTH)))
        n_threads = int(os.getenv("LLAMA_N_THREADS", str(os.cpu_count() or 4)))
        prefer_gpu = settings.DEVICE.lower() in {"cuda", "auto"}
        default_gpu_layers = "-1" if prefer_gpu else "0"
        n_gpu_layers = int(os.getenv("LLAMA_N_GPU_LAYERS", default_gpu_layers))

        logger.info(
            f"正在加载GGUF模型: {gguf_path} (n_ctx={n_ctx}, n_gpu_layers={n_gpu_layers}, n_threads={n_threads})"
        )
        try:
            self.model = Llama(
                model_path=gguf_path,
                n_ctx=n_ctx,
                n_gpu_layers=n_gpu_layers,
                n_threads=n_threads,
                verbose=False,
            )
        except Exception as e:
            if n_gpu_layers != 0:
                logger.warning(f"GGUF模型尝试GPU offload失败，将回退到CPU模式: {e}")
                self.model = Llama(
                    model_path=gguf_path,
                    n_ctx=n_ctx,
                    n_gpu_layers=0,
                    n_threads=n_threads,
                    verbose=False,
                )
                n_gpu_layers = 0
            else:
                raise

        self.backend = "llama_cpp"
        self.device = "cuda" if n_gpu_layers != 0 else "cpu"
        self.tokenizer = None
        self.generator = None
        logger.info(f"模型加载完成(GGUF): {gguf_path}, 设备: {self.device}")

    def load_model(self, model_name: Optional[str] = None, model_path: Optional[str] = None) -> None:
        """
        加载模型

        Args:
            model_name: HuggingFace模型名称
            model_path: 本地模型路径
        """
        try:
            model_name = model_name or settings.MODEL_NAME
            model_path = model_path or settings.MODEL_PATH

            # 优先使用本地 GGUF（llama.cpp）模型
            if model_path and os.path.exists(model_path):
                gguf_file = self._find_gguf_file(model_path)
                if gguf_file:
                    self._load_gguf_model(gguf_file)
                    return

            # transformers 路线
            if torch is None or AutoTokenizer is None or AutoModelForCausalLM is None or pipeline is None:
                logger.warning("缺少torch/transformers，且未检测到可用GGUF模型，使用Mock模式")
                self.backend = "mock"
                self.model = None
                self.tokenizer = None
                self.generator = None
                return

            # 重新检测设备（可能在初始化后设备状态改变）
            self.device = self._get_device()

            logger.info(f"正在加载模型(transformers): {model_name}, 设备: {self.device}")
            if self.device == "cuda":
                logger.info(
                    f"GPU信息: {torch.cuda.get_device_name(0)}, 显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB"
                )

            # 检查accelerate库（使用device_map时需要）
            if self.device != "cpu":
                try:
                    import accelerate  # type: ignore

                    logger.info(f"accelerate版本: {accelerate.__version__}")
                except ImportError:
                    logger.warning("未安装accelerate库，device_map功能可能不可用")
                    logger.warning("建议运行: pip install accelerate")

            # 优先使用本地路径
            if model_path and os.path.exists(model_path):
                model_name_or_path = model_path
            else:
                model_name_or_path = model_name

            # 加载tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name_or_path,
                trust_remote_code=True,
            )

            # 如果tokenizer没有pad_token，设置eos_token为pad_token
            if self.tokenizer.pad_token is None:
                if self.tokenizer.eos_token is not None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                elif hasattr(self.tokenizer, "unk_token") and self.tokenizer.unk_token is not None:
                    self.tokenizer.pad_token = self.tokenizer.unk_token
                else:
                    logger.warning("无法设置pad_token，可能影响生成质量")

            # 加载模型
            if self.device == "cuda":
                logger.info("使用GPU模式加载模型（float16精度）")
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name_or_path,
                    trust_remote_code=True,
                    dtype=torch.float16,
                    device_map="auto",
                    low_cpu_mem_usage=True,
                )
            elif self.device == "mps":
                logger.info("使用MPS模式加载模型")
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name_or_path,
                    trust_remote_code=True,
                    dtype=torch.float32,
                    device_map="auto",
                    low_cpu_mem_usage=True,
                )
            else:
                logger.info("使用CPU模式加载模型")
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name_or_path,
                    trust_remote_code=True,
                    dtype=torch.float32,
                    device_map=None,
                    low_cpu_mem_usage=True,
                )
                self.model = self.model.to("cpu")

            # 创建生成管道
            if self.device == "cuda":
                self.generator = pipeline(
                    "text-generation",
                    model=self.model,
                    tokenizer=self.tokenizer,
                )
            elif self.device == "mps":
                self.generator = pipeline(
                    "text-generation",
                    model=self.model,
                    tokenizer=self.tokenizer,
                    device="mps",
                )
            else:
                self.generator = pipeline(
                    "text-generation",
                    model=self.model,
                    tokenizer=self.tokenizer,
                    device=-1,
                )

            logger.info(f"✓ 生成管道创建完成，设备: {self.device}")
            self.backend = "transformers"
            logger.info(f"模型加载完成(transformers): {model_name}, 设备: {self.device}")

        except Exception as e:
            import traceback

            logger.error(f"模型加载失败: {e}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            logger.warning("使用Mock模式（模型未加载）")
            logger.warning("提示：模型加载失败可能的原因：")
            logger.warning("  1. 网络连接问题（首次下载模型需要网络）")
            logger.warning("  2. 磁盘空间不足")
            logger.warning("  3. 内存不足")
            logger.warning("  4. transformers库版本不兼容")
            logger.warning("  5. 模型名称或路径错误")
            logger.warning("  6. 若使用 .gguf，请确认已安装 llama-cpp-python 并启用 CUDA（可选）")
            self.backend = "mock"
            self.model = None
            self.tokenizer = None
            self.generator = None

    def is_loaded(self) -> bool:
        """检查模型是否已加载"""
        if self.backend == "llama_cpp":
            return self.model is not None
        return self.model is not None and self.tokenizer is not None

    def generate(
        self,
        prompt: str,
        max_new_tokens: int,
        temperature: float,
        top_p: float,
        repetition_penalty: float,
        **kwargs,
    ) -> str:
        if not self.is_loaded():
            raise RuntimeError("模型未加载")

        if self.backend == "llama_cpp":
            stop = kwargs.pop("stop", None)
            result = self.model.create_completion(
                prompt=prompt,
                max_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                repeat_penalty=repetition_penalty,
                stop=stop,
            )
            return (result.get("choices", [{}])[0].get("text") or "").strip()

        results = self.generator(
            prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            do_sample=True,
            num_return_sequences=1,
            pad_token_id=self.tokenizer.pad_token_id,
            eos_token_id=self.tokenizer.eos_token_id,
            **kwargs,
        )

        generated_text = results[0]["generated_text"]
        if generated_text.startswith(prompt):
            generated_text = generated_text[len(prompt) :].strip()
        return generated_text

    def generate_mock_response(self, prompt: str) -> str:
        """
        生成Mock响应（用于测试或模型未加载时）

        Args:
            prompt: 输入提示词

        Returns:
            Mock响应
        """
        if "累" in prompt or "辛苦" in prompt:
            return (
                "听起来你今天真的非常辛苦。你完成了很多工作，这值得被肯定。今晚回家后可以先做10分钟放松呼吸，然后早点休息。我会在明天早上再来问问你睡得怎么样。"
            )
        if "开心" in prompt or "高兴" in prompt:
            return "太好了！听到你开心我也很高兴。继续保持这种积极的状态，你做得很好！"
        if "难过" in prompt or "伤心" in prompt:
            return "我理解你的感受。每个人都会有难过的时刻，这很正常。请记住，这些感受是暂时的，你并不孤单。如果需要，我可以陪你聊聊。"
        return "我理解你的感受。作为你的关怀助手，我会一直在这里支持你。如果你愿意，可以和我分享更多你的想法和感受。"
