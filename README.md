# 长周期资产消耗计算器（Lifelong Cash Dispenser）

> 基于 Trinity Study 的退休资产模拟工具 — 给定初始资产、年度开销与投资组合，资产能撑多少年？

## 一、当前版本（v2.0）

前后端分离架构，紫调留白现代风：

```
lifelong_cash_dispensor/
├── calculator.py            # 核心计算引擎（不变）
├── server.py                # FastAPI 后端（/api/simulate、/api/presets）
├── static/                  # 前端
│   ├── index.html
│   ├── style.css
│   └── app.js
├── requirements.txt         # fastapi / uvicorn / numpy
├── deploy/                  # 部署相关
│   ├── nginx.conf           # Nginx 子域名配置
│   ├── ecosystem.config.js  # PM2 进程配置
│   ├── server-setup.sh      # 服务器初始化（首次执行）
│   └── deploy.sh            # 本地一键部署脚本
└── visualization/           # v1 旧版 Streamlit（保留作为备份）
    └── app.py
```

## 二、本地启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
cd lifelong_cash_dispensor
uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# 3. 打开浏览器
# 访问 http://localhost:8000
```

## 三、功能特性

- **实时联动**：拖动滑块自动重算（300ms debounce），不用点按钮
- **预设场景**：4% 法则 / FIRE 激进 / 保守稳健 / 高消费验证 一键加载
- **响应式布局**：桌面端 + 移动端自适应
- **ECharts 图表**：资产轨迹、提款率、蒙特卡洛扇形图
- **CSV 导出**：逐年明细一键下载
- **明细表滚动**：默认显示前 10 行，超出滚动查看，表头冻结
- **破产备注**：破产时表格下方红字提示「仅展示至破产年份（第 X 年）」

## 四、核心计算逻辑（与 v1 一致）

详见 calculator.py 的 `run_basic` 和 `run_monte_carlo` 函数。

## 五、部署到腾讯云

**架构**：
```
用户浏览器 → Nginx (80) → /var/www/lifelong-cash/      (前端静态)
                       → 127.0.0.1:8001 (uvicorn)      (API 反代)
                              ↑ PM2 守护
```

**子域名**：`lifelong-cash-dispensor.finailab.com.cn`

### 部署步骤

#### 1. DNSPod 添加 A 记录
- 主机记录：`lifelong-cash-dispensor`
- 记录类型：`A`
- 记录值：`43.139.209.228`

#### 2. 服务器首次初始化（执行一次）
```bash
# 本地：同步项目到服务器
rsync -avz --exclude='.git' --exclude='venv' \
  ~/Desktop/ai_product/lifelong_cash_dispensor/ \
  ubuntu@43.139.209.228:~/lifelong_cash_dispensor/

# 服务器：执行初始化脚本
ssh ubuntu@43.139.209.228
cd ~/lifelong_cash_dispensor
bash deploy/server-setup.sh
```

#### 3. 配置 Nginx
```bash
# 服务器上执行
sudo cp ~/lifelong_cash_dispensor/deploy/nginx.conf \
        /etc/nginx/sites-available/lifelong-cash.finailab.com.cn
sudo ln -s /etc/nginx/sites-available/lifelong-cash.finailab.com.cn \
           /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

#### 4. 后续更新（本地一键执行）
```bash
cd ~/Desktop/ai_product/lifelong_cash_dispensor
bash deploy/deploy.sh
```

### 运维速查

```bash
# PM2 操作
pm2 logs lifelong-cash              # 实时日志
pm2 restart lifelong-cash           # 重启
pm2 monit                           # 监控面板

# Nginx
sudo nginx -t && sudo systemctl reload nginx
sudo tail -f /var/log/nginx/lifelong-cash.error.log

# 验证 API
curl http://127.0.0.1:8001/api/presets
```

## 六、参考文献

1. Burton Malkiel,《漫步华尔街》
2. Trinity Study (Cooley, Hubbard, Walz, 1998)
3. William Bengen (1994) - Determining Withdrawal Rates Using Historical Data
4. Early Retirement Now (ERN) - Safe Withdrawal Rate Series
