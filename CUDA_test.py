import torch

# 核心检查：CUDA 是否可用
cuda_available = torch.cuda.is_available()
print(f"CUDA 可用: {cuda_available}")

if cuda_available:
    # 查看可用 GPU 数量
    print(f"可用 GPU 数量: {torch.cuda.device_count()}")
    # 查看当前默认 GPU 索引
    print(f"当前 GPU 索引: {torch.cuda.current_device()}")
    # 查看 GPU 名称
    print(f"GPU 名称: {torch.cuda.get_device_name(0)}")
    # 查看 PyTorch 编译的 CUDA 版本
    print(f"PyTorch 编译的 CUDA 版本: {torch.version.cuda}")
else:
    print("原因可能：无 NVIDIA 显卡/未装驱动/框架是 CPU 版本")
