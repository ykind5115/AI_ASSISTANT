# CareMate 部署说明

本文档说明如何在开发机器、家庭台式机或笔记本上部署和运行 CareMate。

## 系统要求

### 最低配置（CPU模式）
- **CPU**: 现代4核处理器
- **内存**: 8GB RAM
- **磁盘**: 20GB 可用空间
- **操作系统**: Windows 10+, macOS 10.15+, Linux (Ubuntu 20.04+)

### 推荐配置（良好体验）
- **CPU**: 8核+ 处理器
- **GPU**: NVIDIA RTX 系列或等效（可选，用于加速）
- **内存**: 16GB+ RAM
- **磁盘**: 50GB+ 可用空间
- **操作系统**: Windows 11, macOS 12+, Ubuntu 22.04+

## 安装步骤

### 1. 安装 Python

确保已安装 Python 3.10 或更高版本：

```bash
python --version
```

如果未安装，请从 [python.org](https://www.python.org/downloads/) 下载安装。

### 2. 获取项目代码

```bash
# 如果使用 Git
git clone <repository-url>
cd AI_assistant

# 或直接下载解压到目标目录
```

### 3. 创建虚拟环境

**Windows:**
```powershell
python -m venv venv
venv\Scripts\activate
```

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. 安装依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**注意**: 
- 如果使用 GPU，确保已安装 CUDA 和对应的 PyTorch 版本
- 安装可能需要较长时间，请耐心等待

### 5. 初始化数据库

```bash
python scripts/init_db.py
```

这将创建数据库文件和默认数据。

### 6. 配置环境变量（可选）

创建 `.env` 文件：

```env
# 模型配置
MODEL_NAME=gpt2
MODEL_PATH=
DEVICE=cpu

# 应用配置
DEBUG=False
API_HOST=127.0.0.1
API_PORT=8000
```

### 6.1 使用本地 GGUF 模型（推荐，离线可用）

如果你的模型是 `.gguf`（例如 `data/models/Llama3-8B-Chinese-Chat-Q5/Llama3-8B-Chinese-Chat.Q5_K_M.gguf`），项目会自动走 llama.cpp 推理（需要安装 `llama-cpp-python`）。

1. 在 `.env` 中设置（示例）：

```env
MODEL_NAME=Llama3-8B-Chinese-Chat-Q5
MODEL_PATH=data/models/Llama3-8B-Chinese-Chat-Q5
DEVICE=auto
```

2. 安装依赖（示例，GPU 需启用 CUDA 编译选项）：

```bash
pip install -r requirements-gguf.txt
```

如需继续使用 HuggingFace/transformers 模型，可使用 `python scripts/download_model.py` 下载到 `MODEL_PATH`。

### 7. 启动应用

**开发模式:**
```bash
python -m app.main
```

**生产模式:**
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

**后台运行（Linux/macOS）:**
```bash
nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 > caremate.log 2>&1 &
```

**Windows 服务（使用 NSSM）:**
1. 下载 [NSSM](https://nssm.cc/download)
2. 安装为服务：
```powershell
nssm install CareMate "C:\path\to\venv\Scripts\python.exe" "-m" "app.main"
```

## 验证安装

1. 打开浏览器访问: http://127.0.0.1:8000
2. 应该能看到 CareMate 界面
3. 尝试发送一条消息测试
4. （可选）点击页面顶部“登录/注册”，创建账号并登录

## 模型配置

### 使用默认模型（GPT-2）

默认配置即可使用，无需额外下载。

### 使用自定义模型

1. 下载模型到本地目录
2. 在 `.env` 中设置 `MODEL_PATH=/path/to/model`
3. 重启应用

### 推荐模型

- **小型模型**（适合CPU）: GPT-2, DistilGPT-2
- **中型模型**（需要GPU）: ChatGLM-6B, Baichuan-7B
- **量化模型**: 使用量化版本以降低内存占用

## 数据备份

### 手动备份

数据库文件位于 `data/caremate.db`，定期复制此文件即可。

### 使用导出脚本

```bash
python scripts/export_data.py --output backup.json
```

### 自动备份（Linux/macOS）

创建备份脚本 `backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d_%H%M%S)
cp data/caremate.db "$BACKUP_DIR/caremate_$DATE.db"
python scripts/export_data.py --output "$BACKUP_DIR/export_$DATE.json"
```

添加到 crontab:
```bash
0 2 * * * /path/to/backup.sh
```

## 数据迁移

### 迁移到新机器

1. 在新机器上安装 CareMate
2. 停止应用
3. 复制 `data/caremate.db` 到新机器
4. 启动应用

### 使用导出文件迁移

1. 在原机器导出数据：
```bash
python scripts/export_data.py
```

2. 在新机器导入（需要实现导入脚本或手动导入）

## 卸载

1. 停止应用
2. 删除项目目录
3. （可选）删除虚拟环境
4. （可选）删除数据目录 `data/`

## 故障排除

### 端口被占用

修改 `.env` 中的 `API_PORT` 或使用其他端口：
```bash
uvicorn app.main:app --port 8001
```

### 模型加载失败

- 检查网络连接（首次下载模型需要）
- 检查磁盘空间
- 尝试使用更小的模型
- 查看日志文件 `logs/caremate.log`

### 内存不足

- 使用更小的模型
- 使用量化模型
- 减少 `MAX_CONTEXT_LENGTH` 配置
- 关闭其他占用内存的程序

### 数据库错误

- 检查 `data/` 目录权限
- 尝试重新初始化数据库（会丢失数据）
- 检查磁盘空间

## 性能优化

1. **使用GPU加速**: 设置 `DEVICE=cuda`
2. **使用量化模型**: 降低内存占用
3. **调整上下文长度**: 减少 `MAX_CONTEXT_LENGTH`
4. **定期清理旧会话**: 自动清理超过保留期的会话

## 安全建议

1. 仅在内网运行，不要暴露到公网
2. 如需公网访问，使用反向代理（Nginx）并配置HTTPS
3. 定期备份数据
4. 保护 `.env` 文件，不要提交到版本控制

## 更新

1. 备份数据
2. 停止应用
3. 拉取最新代码
4. 更新依赖: `pip install -r requirements.txt --upgrade`
5. 重启应用

## 获取帮助

如遇问题，请：
1. 查看日志文件 `logs/caremate.log`
2. 检查 GitHub Issues
3. 提交新的 Issue 描述问题
