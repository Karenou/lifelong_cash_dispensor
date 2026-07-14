// ============================================================
// 人生提款模拟器 · PM2 进程配置
//
// 用法（在服务器项目根目录执行）：
//   pm2 start deploy/ecosystem.config.js
//   pm2 save
//   pm2 startup  # 按提示执行一次 sudo 命令，开机自启
//
// 日常运维：
//   pm2 logs lifelong-cash            # 实时日志
//   pm2 restart lifelong-cash         # 重启
//   pm2 stop lifelong-cash            # 停止
//   pm2 delete lifelong-cash          # 删除进程
// ============================================================

module.exports = {
  apps: [
    {
      name: 'lifelong-cash',
      cwd: '/home/ubuntu/lifelong_cash_dispensor',
      // 直接调用 venv 里的 uvicorn 可执行文件
      script: 'venv/bin/uvicorn',
      args: 'server:app --host 127.0.0.1 --port 8001 --workers 2',
      interpreter: 'none',  // script 本身是可执行文件，不用解释器
      instances: 1,
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
      max_memory_restart: '500M',
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1',
      },
      error_file: '/home/ubuntu/.pm2/logs/lifelong-cash-error.log',
      out_file: '/home/ubuntu/.pm2/logs/lifelong-cash-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
    },
  ],
};
