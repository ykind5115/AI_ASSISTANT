# CareMate - 关怀型本地大模型聊天应用

CareMate 是一款本地运行的智能聊天应用，旨在提供温暖、关怀的对话体验，帮助用户缓解孤独感和情绪困扰。

## ✨ 特性

- 💬 **自然对话**：提供温暖、同理心的对话体验
- ⏰ **定时关怀**：每天定时发送个性化关怀消息
- 📝 **智能摘要**：自动生成对话摘要，记录用户进展
- 🔒 **隐私保护**：所有数据本地存储，不上传云端
- 🎨 **简洁界面**：现代化的聊天界面
- 🛡️ **安全过滤**：自动检测和处理危险内容

## 🚀 快速开始

### 环境要求

- Python 3.10+
- 8GB+ RAM（推荐16GB+）
- 20GB+ 可用磁盘空间

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd AI_assistant
```

2. **创建虚拟环境**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **初始化数据库**
```bash
python scripts/init_db.py
```

5. **启动应用**
```bash
python -m app.main
```

或者使用 uvicorn：
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

6. **访问应用**
打开浏览器访问：http://127.0.0.1:8000

## 📁 项目结构

```
caremate/
├── app/                    # 应用代码
│   ├── api/               # API路由
│   ├── models/            # 数据模型
│   ├── services/          # 业务逻辑
│   ├── ml/                # 模型推理
│   ├── utils/             # 工具类
│   └── main.py            # 应用入口
├── frontend/              # 前端界面
├── scripts/               # 脚本工具
├── tests/                 # 测试用例
├── docs/                  # 文档
└── data/                  # 数据目录（自动创建）
```

## ⚙️ 配置

创建 `.env` 文件（可选）：

```env
# 模型配置
MODEL_NAME=gpt2
MODEL_PATH=
DEVICE=cpu

# 应用配置
DEBUG=False
API_HOST=127.0.0.1
API_PORT=8000

# 其他配置见 app/config.py
```

## 🧪 测试

运行测试：
```bash
pytest tests/
```

## 📖 使用说明

### 基本对话

1. 打开应用后，在输入框输入消息
2. CareMate 会以温暖、关怀的方式回复
3. 所有对话历史会自动保存

### 设置定时推送

通过API设置定时推送：
```bash
curl -X POST http://127.0.0.1:8000/api/v1/schedule \
  -H "Content-Type: application/json" \
  -d '{"cron_or_time": "08:00", "enabled": true}'
```

### 导出数据

使用脚本导出数据：
```bash
python scripts/export_data.py
```

或通过API：
```bash
curl http://127.0.0.1:8000/api/v1/export
```

## 🔧 API文档

启动应用后，访问 http://127.0.0.1:8000/docs 查看完整的API文档。

主要API端点：
- `POST /api/v1/chat` - 发送消息
- `GET /api/v1/session/{id}` - 获取会话历史
- `GET /api/v1/sessions` - 获取历史会话列表
- `POST /api/v1/session/new` - 新建会话
- `GET /api/v1/session/{id}/export` - 导出单个会话
- `DELETE /api/v1/session/{id}` - 删除单个会话
- `POST /api/v1/schedule` - 创建定时推送
- `GET /api/v1/summaries` - 获取摘要列表
- `POST /api/v1/auth/register` - 注册账号
- `POST /api/v1/auth/login` - 登录获取 Token
- `GET /api/v1/auth/me` - 获取当前登录用户
- `POST /api/v1/auth/logout` - 退出登录
- `POST /api/v1/export` - 导出数据

## 🛡️ 安全说明

- 应用会自动检测危险内容（自伤、自杀等）
- 检测到危险内容时会显示帮助信息
- 所有数据存储在本地，不会上传到云端

## 📝 开发说明

### 模型选择

默认使用本地 GGUF 量化模型：`Llama3-8B-Chinese-Chat-Q5`（适合 11GB 显存部署，离线可用；需要 `llama-cpp-python`）。

修改 `.env` 文件中的 `MODEL_NAME` / `MODEL_PATH` 即可切换模型：
- **GGUF（llama.cpp）**：`MODEL_PATH` 指向 `.gguf` 文件或包含 `.gguf` 的目录（例如 `data/models/Llama3-8B-Chinese-Chat-Q5`）
- **Transformers/HuggingFace**：清空 `MODEL_PATH`，并设置 `MODEL_NAME` 为 HuggingFace repo id（例如 `Qwen/Qwen2.5-1.5B-Instruct`）

使用 GGUF 时可额外安装：`pip install -r requirements-gguf.txt`（GPU 可按需启用 CUDA 编译选项）。

### 扩展功能

- 添加新的Prompt模板
- 实现向量检索增强记忆
- 添加情绪分析功能
- 支持多用户模式

## 📄 许可证

见 LICENSE 文件

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题或建议，请提交 Issue。

---

**注意**：CareMate 仅提供情感支持，不提供医疗、法律或专业治疗建议。如有严重心理问题，请寻求专业帮助。
