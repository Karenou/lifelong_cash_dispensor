#!/bin/bash
# ============================================================
# 本地执行的一键部署脚本
#
# 用法：
#   cd ~/Desktop/ai_product/lifelong_cash_dispensor
#   bash deploy/deploy.sh
#
# 前提：
#   1. 已配置 SSH 免密登录（ssh-copy-id ubuntu@43.139.209.228）
#   2. 服务器已执行过 deploy/server-setup.sh（装好 Python 环境）
#   3. DNSPod 已添加 A 记录: lifelong-cash-dispensor → 43.139.209.228
# ============================================================
set -e

# ===== 配置 =====
SERVER_IP="43.139.209.228"
SERVER_USER="ubuntu"
REMOTE_DIR="~/lifelong_cash_dispensor"
WEB_DIR="/var/www/lifelong-cash"

# 项目根目录（脚本所在的上一级）
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "🚀 开始部署 lifelong_cash_dispensor 到 $SERVER_IP"
echo "   本地项目: $PROJECT_DIR"
echo ""

# ===== 1. rsync 同步代码到服务器 =====
echo "📦 [1/4] rsync 同步代码..."
rsync -avz --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='venv' \
    --exclude='.preview-*' \
    --exclude='.playwright-cli' \
    --exclude='visualization' \
    --exclude='deploy' \
    ./ "$SERVER_USER@$SERVER_IP:$REMOTE_DIR/"

echo "   ✓ 代码已同步"
echo ""

# ===== 2. 服务器端重新安装依赖（venv 不上传，需重装）=====
echo "📦 [2/4] 服务器端安装依赖..."
ssh "$SERVER_USER@$SERVER_IP" "cd $REMOTE_DIR && \
    source venv/bin/activate && \
    pip install --upgrade pip -q && \
    pip install -r requirements.txt -q && \
    deactivate && \
    echo '   ✓ 依赖已更新'"

# ===== 3. 同步前端静态文件到 Nginx 目录 =====
echo "🌐 [3/4] 同步前端静态文件..."
ssh "$SERVER_USER@$SERVER_IP" "sudo rsync -av --delete \
    $REMOTE_DIR/static/ $WEB_DIR/static/ && \
    sudo cp $REMOTE_DIR/static/index.html $WEB_DIR/index.html && \
    sudo chown -R www-data:www-data $WEB_DIR"
echo "   ✓ 前端文件已同步"

# ===== 4. 重启 PM2 进程 =====
echo "🔄 [4/4] 重启 PM2 进程..."
ssh "$SERVER_USER@$SERVER_IP" "cd $REMOTE_DIR && \
    pm2 delete lifelong-cash 2>/dev/null || true && \
    pm2 start deploy/ecosystem.config.js && \
    pm2 save"
echo "   ✓ PM2 进程已启动"

# ===== 完成提示 =====
echo ""
echo "✅ 部署完成！"
echo ""
echo "📍 访问地址："
echo "   - 域名（需 DNS 解析生效）：http://lifelong-cash-dispensor.finailab.com.cn"
echo "   - IP 直连（备用）：http://43.139.209.228（需 Nginx 配置 default_server 或单独 location）"
echo ""
echo "🔍 验证命令："
echo "   - 服务器健康检查：curl http://127.0.0.1:8001/api/presets"
echo "   - PM2 日志：ssh $SERVER_USER@$SERVER_IP 'pm2 logs lifelong-cash --lines 20'"
echo "   - Nginx 错误日志：ssh $SERVER_USER@$SERVER_IP 'sudo tail -f /var/log/nginx/lifelong-cash.error.log'"
