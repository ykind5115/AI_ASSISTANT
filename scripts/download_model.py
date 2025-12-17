import argparse
import sys
import os
from pathlib import Path

def _download_via_hub(model: str, output: Path, revision: str | None = None, file: str | None = None) -> None:
    """通过 huggingface_hub 下载模型（支持指定单个文件）"""
    from huggingface_hub import snapshot_download
    output.mkdir(parents=True, exist_ok=True)
    
    # 配置：若指定了file，仅下载该文件；否则下载整个仓库
    download_kwargs = {}
    if file:
        download_kwargs["allow_patterns"] = [file]  # 过滤仅保留目标文件
        print(f"仅下载指定文件: {file}")

    snapshot_download(
        repo_id=model,
        revision=revision,
        local_dir=str(output),
        local_dir_use_symlinks=False,
        resume_download=True,
        **download_kwargs
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Download HF model (支持代理与镜像加速)")
    parser.add_argument("--model", type=str, required=True, help="HuggingFace仓库ID")
    parser.add_argument("--output", type=str, required=True, help="本地保存目录")
    parser.add_argument("--revision", type=str, default=None, help="可选：模型分支/版本")
    parser.add_argument("--file", type=str, default=None, help="可选：指定要下载的单个文件名")
    
    # === 新增参数 ===
    parser.add_argument("--proxy", type=str, default="http://127.0.0.1:7897", help="代理地址 (默认设置为 Clash 端口 7897)")
    parser.add_argument("--no-mirror", action="store_true", help="禁用 HF 镜像加速 (默认开启)")
    
    args = parser.parse_args()

    # === 1. 设置代理 (基于你的 Clash 截图) ===
    if args.proxy:
        print(f"🌐 正在应用代理设置: {args.proxy}")
        os.environ["http_proxy"] = args.proxy
        os.environ["https_proxy"] = args.proxy

    # === 2. 设置 HF 镜像 (国内下载提速神器) ===
    if not args.no_mirror:
        print("🚀 已启用 hf-mirror.com 镜像加速")
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    model = args.model
    output_path = Path(args.output)

    try:
        _download_via_hub(model, output_path, args.revision, file=args.file)
        print(f"✅ 下载完成！文件已保存至：{output_path}")
        return 0
    except ImportError:
        print("❌ 缺少依赖：请先安装 huggingface_hub（执行 pip install huggingface_hub）")
        return 1
    except Exception as e:
        print(f"❌ 下载失败：{str(e)}")
        print("💡 提示：请检查 Clash 是否已开启 System Proxy 或 TUN 模式，并确保端口 7897 正确。")
        return 1


if __name__ == "__main__":
    sys.exit(main())