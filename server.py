"""
长周期资产消耗计算器 - FastAPI 后端服务

复用 calculator.py 的核心计算引擎，提供 REST API 供前端调用。

启动方式：
  cd lifelong_cash_dispensor
  uvicorn server:app --host 0.0.0.0 --port 8000 --reload

或直接运行：
  python3 server.py
"""

import os
import sys
from typing import List, Optional

# 把当前目录加入 path 以便导入 calculator
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from calculator import run_basic, run_monte_carlo, build_return_params


# ============================================================
# 请求 / 响应模型
# ============================================================

class SimulateRequest(BaseModel):
    w0: float = Field(..., gt=0, description="初始资产总额")
    years: int = Field(..., ge=1, le=80, description="规划年限")
    inflation: float = Field(..., ge=0, le=0.5, description="通胀率")
    return_rate: float = Field(..., ge=-0.5, le=1.0, description="预期年化收益率")
    e0: Optional[float] = Field(None, gt=0, description="首年提款金额（与 rate 二选一）")
    rate: Optional[float] = Field(None, gt=0, le=1.0, description="首年提款率（与 e0 二选一）")
    enable_mc: bool = Field(True, description="是否启用蒙特卡洛模拟")
    sigma: float = Field(0.15, ge=0.01, le=1.0, description="收益率标准差")
    num_simulations: int = Field(5000, ge=100, le=100000, description="模拟次数")
    seed: Optional[int] = Field(42, description="随机种子")


class YearRecordOut(BaseModel):
    year: int
    withdrawal: float
    wealth_before: float
    wealth_after: float
    return_rate: float
    withdrawal_ratio: float


class BasicResultOut(BaseModel):
    is_bankrupt: bool
    bankrupt_year: Optional[int]
    final_wealth: float
    records: List[YearRecordOut]


class MonteCarloResultOut(BaseModel):
    num_simulations: int
    bankrupt_probability: float
    survival_probability: float
    median_final_wealth: float
    percentile_paths: dict


class SimulateResponse(BaseModel):
    basic: BasicResultOut
    monte_carlo: Optional[MonteCarloResultOut]


# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(title="人生提款模拟器 API", version="2.0.0")

# 允许跨域（开发期前端可能跑在不同端口）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/presets")
def get_presets():
    """返回预设场景配置"""
    return {
        "presets": [
            {
                "id": "four_percent",
                "name": "4% 法则",
                "description": "Trinity Study 经典结论：4% 提款率 + 60/40 股债组合",
                "params": {
                    "w0": 1000000,
                    "rate": 0.04,
                    "years": 30,
                    "inflation": 0.03,
                    "return_rate": 0.055,
                    "sigma": 0.15,
                    "num_simulations": 5000,
                },
            },
            {
                "id": "fire_aggressive",
                "name": "FIRE 激进型",
                "description": "提前退休 + 高股票配比，预期高收益伴随高波动",
                "params": {
                    "w0": 2000000,
                    "rate": 0.04,
                    "years": 40,
                    "inflation": 0.025,
                    "return_rate": 0.08,
                    "sigma": 0.18,
                    "num_simulations": 5000,
                },
            },
            {
                "id": "conservative",
                "name": "保守稳健型",
                "description": "低波动 + 低提款率，优先保本",
                "params": {
                    "w0": 3000000,
                    "rate": 0.03,
                    "years": 30,
                    "inflation": 0.025,
                    "return_rate": 0.045,
                    "sigma": 0.08,
                    "num_simulations": 5000,
                },
            },
            {
                "id": "high_withdrawal",
                "name": "高消费验证",
                "description": "6% 高提款率，看看资产能撑几年",
                "params": {
                    "w0": 1000000,
                    "rate": 0.06,
                    "years": 30,
                    "inflation": 0.03,
                    "return_rate": 0.06,
                    "sigma": 0.15,
                    "num_simulations": 5000,
                },
            },
        ]
    }


@app.post("/api/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest):
    """执行模拟计算"""

    # 提款金额计算
    if req.e0 is not None:
        e0 = req.e0
    elif req.rate is not None:
        e0 = req.w0 * req.rate
    else:
        raise HTTPException(status_code=400, detail="必须提供 e0 或 rate")

    # 基础模式
    basic_result = run_basic(
        w0=req.w0,
        e0=e0,
        years=req.years,
        inflation=req.inflation,
        return_rate=req.return_rate,
    )

    basic_out = BasicResultOut(
        is_bankrupt=basic_result.is_bankrupt,
        bankrupt_year=basic_result.bankrupt_year,
        final_wealth=basic_result.final_wealth,
        records=[
            YearRecordOut(
                year=rec.year,
                withdrawal=rec.withdrawal,
                wealth_before=rec.wealth_before,
                wealth_after=rec.wealth_after,
                return_rate=rec.return_rate,
                withdrawal_ratio=rec.withdrawal_ratio,
            )
            for rec in basic_result.records
        ],
    )

    # 蒙特卡洛模式
    mc_out = None
    if req.enable_mc:
        try:
            return_params = build_return_params(
                years=req.years,
                mu=req.return_rate,
                sigma=req.sigma,
            )
            mc_result = run_monte_carlo(
                w0=req.w0,
                e0=e0,
                years=req.years,
                inflation=req.inflation,
                return_params=return_params,
                num_simulations=req.num_simulations,
                seed=req.seed,
            )
            mc_out = MonteCarloResultOut(
                num_simulations=mc_result.num_simulations,
                bankrupt_probability=mc_result.bankrupt_probability,
                survival_probability=1 - mc_result.bankrupt_probability,
                median_final_wealth=mc_result.median_final_wealth,
                percentile_paths=mc_result.percentile_paths,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"蒙特卡洛模拟失败: {str(e)}")

    return SimulateResponse(basic=basic_out, monte_carlo=mc_out)


# ============================================================
# 静态文件服务（前端）
# ============================================================

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
