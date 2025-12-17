#!/bin/bash
# CareMate 本地运行脚本

echo "=================================="
echo "启动 CareMate"
echo "=================================="

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 检查依赖
echo "检查依赖..."
pip install -q -r requirements.txt

# 检查数据库
if [ ! -f "data/caremate.db" ]; then
    echo "初始化数据库..."
    python scripts/init_db.py
fi

# 启动应用
echo "启动应用..."
echo "访问地址: http://127.0.0.1:8000"
echo "按 Ctrl+C 停止"
echo "=================================="

python -m app.main



