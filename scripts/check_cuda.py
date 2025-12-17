"""
CUDA检查脚本
检查PyTorch是否正确支持CUDA
"""
import torch
import sys

print("=" * 50)
print("CUDA 支持检查")
print("=" * 50)

# PyTorch版本
print(f"PyTorch版本: {torch.__version__}")

# CUDA可用性
print(f"\nCUDA可用: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"CUDA版本: {torch.version.cuda}")
    print(f"cuDNN版本: {torch.backends.cudnn.version()}")
    print(f"GPU数量: {torch.cuda.device_count()}")
    
    for i in range(torch.cuda.device_count()):
        print(f"\nGPU {i}:")
        print(f"  名称: {torch.cuda.get_device_name(i)}")
        print(f"  显存: {torch.cuda.get_device_properties(i).total_memory / 1024**3:.2f} GB")
        print(f"  计算能力: {torch.cuda.get_device_properties(i).major}.{torch.cuda.get_device_properties(i).minor}")
    
    # 测试CUDA张量
    print("\n测试CUDA张量操作...")
    try:
        x = torch.randn(3, 3).cuda()
        y = torch.randn(3, 3).cuda()
        z = torch.matmul(x, y)
        print("✓ CUDA张量操作成功")
    except Exception as e:
        print(f"✗ CUDA张量操作失败: {e}")
else:
    print("\n⚠ CUDA不可用！")
    print("\n可能的原因：")
    print("1. PyTorch安装的是CPU版本")
    print("2. CUDA驱动未正确安装")
    print("3. PyTorch版本与CUDA版本不匹配")
    print("\n解决方案：")
    print("1. 卸载当前PyTorch: pip uninstall torch torchvision torchaudio")
    print("2. 安装CUDA版本的PyTorch:")
    print("   访问 https://pytorch.org/get-started/locally/")
    print("   选择对应的CUDA版本安装命令")
    print("   例如（CUDA 11.8）:")
    print("   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")
    print("   或（CUDA 12.1）:")
    print("   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121")

print("\n" + "=" * 50)



