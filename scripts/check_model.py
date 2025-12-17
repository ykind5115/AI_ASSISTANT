"""
模型检查脚本
用于诊断模型加载问题
"""
import os
import sys
from pathlib import Path
from typing import Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import torch  # type: ignore
except ImportError:  # pragma: no cover
    torch = None

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM  # type: ignore
except ImportError:  # pragma: no cover
    AutoTokenizer = None
    AutoModelForCausalLM = None

try:
    from llama_cpp import Llama  # type: ignore
except ImportError:  # pragma: no cover
    Llama = None

from app.config import settings


def _find_gguf_file(model_path: str) -> Optional[Path]:
    p = Path(model_path)
    if p.is_file() and p.suffix.lower() == ".gguf":
        return p
    if p.is_dir():
        candidates = list(p.glob("*.gguf"))
        if candidates:
            return max(candidates, key=lambda x: x.stat().st_size)
    return None


def check_environment() -> None:
    print("=" * 50)
    print("环境检查")
    print("=" * 50)

    print(f"Python版本: {sys.version}")

    if torch is not None:
        print(f"PyTorch版本: {torch.__version__}")
    else:
        print("PyTorch: 未安装")

    if torch is not None and torch.cuda.is_available():
        print("CUDA可用: 是")
        print(f"CUDA版本: {torch.version.cuda}")
        print(f"GPU数量: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            print(f"  GPU {i}: {torch.cuda.get_device_name(i)}")
    else:
        print("CUDA可用: 否")

    if torch is not None and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        print("MPS可用: 是")
    else:
        print("MPS可用: 否")

    try:
        import transformers  # type: ignore

        print(f"Transformers版本: {transformers.__version__}")
    except ImportError:
        print("Transformers: 未安装")

    if Llama is None:
        print("llama-cpp-python: 未安装")
    else:
        try:
            import llama_cpp  # type: ignore

            print(f"llama-cpp-python版本: {llama_cpp.__version__}")
        except Exception:
            print("llama-cpp-python: 已安装")

    print()


def check_model_loading() -> bool:
    print("=" * 50)
    print("模型加载测试")
    print("=" * 50)

    model_name = settings.MODEL_NAME
    model_path = settings.MODEL_PATH

    print(f"模型名称: {model_name}")
    print(f"模型路径: {model_path}")
    print(f"设备: {settings.DEVICE}")
    print()

    # 优先检测 GGUF
    if model_path and Path(model_path).exists():
        gguf = _find_gguf_file(model_path)
        if gguf is not None:
            print(f"使用GGUF模型: {gguf}")
            print()
            print("开始加载模型(llama.cpp)...")
            if Llama is None:
                print("✗ 未安装 llama-cpp-python，无法加载 .gguf 模型")
                print("建议:")
                print("  pip install llama-cpp-python")
                print("  (GPU: CMAKE_ARGS='-DGGML_CUDA=on' pip install llama-cpp-python)")
                return False

            n_ctx = int(os.getenv("LLAMA_N_CTX", str(settings.MAX_CONTEXT_LENGTH)))
            prefer_gpu = settings.DEVICE.lower() in {"cuda", "auto"}
            default_gpu_layers = "-1" if prefer_gpu else "0"
            n_gpu_layers = int(os.getenv("LLAMA_N_GPU_LAYERS", default_gpu_layers))
            n_threads = int(os.getenv("LLAMA_N_THREADS", str(os.cpu_count() or 4)))

            try:
                llm = Llama(
                    model_path=str(gguf),
                    n_ctx=n_ctx,
                    n_gpu_layers=n_gpu_layers,
                    n_threads=n_threads,
                    verbose=False,
                )
            except Exception as e:
                if n_gpu_layers != 0:
                    print(f"! GPU offload失败，回退CPU: {e}")
                    llm = Llama(
                        model_path=str(gguf),
                        n_ctx=n_ctx,
                        n_gpu_layers=0,
                        n_threads=n_threads,
                        verbose=False,
                    )
                else:
                    raise

            test_prompt = "你好"
            out = llm.create_completion(prompt=test_prompt, max_tokens=50, temperature=0.7)
            text = (out.get("choices", [{}])[0].get("text") or "").strip()

            print("✓ 模型加载成功")
            print(f"输入: {test_prompt}")
            print(f"输出: {text[:200]}...")
            print()
            print("=" * 50)
            print("✓ 模型加载测试通过！")
            print("=" * 50)
            return True

    # transformers/HF
    if model_path and Path(model_path).exists():
        model_name_or_path = model_path
        print(f"使用本地模型目录(transformers): {model_path}")
    else:
        model_name_or_path = model_name
        print(f"使用HuggingFace模型: {model_name}")
        print("注意：首次下载需要网络连接")

    print()
    print("开始加载模型(transformers)...")

    if torch is None or AutoTokenizer is None or AutoModelForCausalLM is None:
        print("✗ 缺少 torch/transformers，无法进行 transformers 加载测试")
        return False

    try:
        print("1. 加载tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(model_name_or_path, trust_remote_code=True)
        print("   ✓ Tokenizer加载成功")

        if tokenizer.pad_token is None and tokenizer.eos_token is not None:
            tokenizer.pad_token = tokenizer.eos_token
            print("   ✓ 设置pad_token")

        print("2. 加载模型...")
        device = settings.DEVICE
        if device == "cuda" and not torch.cuda.is_available():
            print("   ! CUDA不可用，使用CPU")
            device = "cpu"

        model = AutoModelForCausalLM.from_pretrained(
            model_name_or_path,
            trust_remote_code=True,
            dtype=torch.float16 if device != "cpu" else torch.float32,
            device_map="auto" if device != "cpu" else None,
            low_cpu_mem_usage=True,
        )

        if device == "cpu":
            model = model.to(device)

        print("   ✓ 模型加载成功")

        print("3. 测试生成...")
        test_prompt = "你好"
        inputs = tokenizer(test_prompt, return_tensors="pt").to(device)

        with torch.no_grad():
            outputs = model.generate(
                inputs.input_ids,
                max_length=50,
                do_sample=True,
                temperature=0.7,
                pad_token_id=tokenizer.pad_token_id,
            )

        generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        print("   ✓ 生成测试成功")
        print(f"   输入: {test_prompt}")
        print(f"   输出: {generated_text[:100]}...")

        print()
        print("=" * 50)
        print("✓ 模型加载测试通过！")
        print("=" * 50)
        return True

    except Exception as e:
        import traceback

        print()
        print("=" * 50)
        print("✗ 模型加载失败")
        print("=" * 50)
        print(f"错误: {e}")
        print()
        print("详细错误信息:")
        print(traceback.format_exc())
        print()
        print("可能的原因:")
        print("  1. 网络连接问题（首次下载需要网络）")
        print("  2. 磁盘空间不足")
        print("  3. 内存不足")
        print("  4. 模型名称错误")
        print("  5. 依赖包版本不兼容")
        print()
        return False


def main() -> None:
    check_environment()
    print()
    success = check_model_loading()

    if not success:
        print()
        print("建议:")
        print("  1. 检查模型路径与文件是否存在")
        print("  2. 若使用 .gguf：安装 llama-cpp-python，并按需设置 LLAMA_N_GPU_LAYERS")
        print("  3. 若使用 transformers：安装 torch/transformers，并检查显存/内存")
        sys.exit(1)


if __name__ == "__main__":
    main()
