#!/bin/bash
# ============================================================
# 服务器初始化脚本（首次部署执行一次）
# 在服务器上执行：bash deploy/server-setup.sh
# ============================================================
set -e

echo "🚀 开始初始化 lifelong_cash_dispensor 服务器环境..."

# 1. 安装 Python 3.10+ 和 venv
echo "📦 [1/5] 安装 Python 环境..."
if ! command -v python3.10 &> /dev/null; then
    sudo add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
    sudo apt update
    sudo apt install -y python3.10 python3.10-venv python3.10-dev
else
    echo "   ✓ python3.10 已存在"
fi

# 也兼容系统自带的 python3（Ubuntu 22.04 是 3.10）
PYTHON_BIN=$(command -v python3.10 || command -v python3)
echo "   使用 Python: $PYTHON_BIN ($($PYTHON_BIN --version))"

# 2. 创建项目目录
echo "📁 [2/5] 创建项目目录..."
mkdir -p ~/lifelong_cash_dispensor
mkdir -p ~/.pm2/logs

# 3. 创建 venv 并安装依赖（在项目目录里执行）
echo "📦 [3/5] 创建虚拟环境并安装依赖..."
cd ~/lifelong_cash_dispensor

if [ ! -d "venv" ]; then
    $PYTHON_BIN -m venv venv
fi

# 激活 venv 后安装依赖
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

echo "   ✓ 依赖安装完成"

# 4. 创建前端静态目录
echo "📁 [4/5] 创建 Nginx 静态目录..."
sudo mkdir -p /var/www/lifelong-cash
sudo chown -R $(whoami):$(whoami) /var/www/lifelong-cash

# 5. 验证 PM2
echo "🔍 [5/5] 检查 PM2..."
if ! command -v pm2 &> /dev/null; then
    echo "   ⚠ PM2 未安装，正在安装..."
    npm install -g pm2
else
    echo "   ✓ PM2 已存在: $(pm2 --version)"
fi

echo ""
echo "✅ 服务器初始化完成！"
echo ""
echo "下一步：在本地执行 deploy/deploy.sh 同步代码并启动服务"
