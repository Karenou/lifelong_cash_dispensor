"""
长周期资产消耗计算器（Lifelong Cash Withdrawer）
基于 Trinity Study 的退休资产模拟工具

功能：
  - 基础模式：固定收益率的确定性迭代计算
  - 高级模式：蒙特卡洛模拟（支持逐年不同正态分布参数）

用法：
  python3 calculator.py --mode basic --w0 5000000 --rate 0.04 --years 30 --inflation 0.03 --return_rate 0.07
  python3 calculator.py --mode monte_carlo --w0 5000000 --rate 0.04 --years 30 --inflation 0.03 --mu 0.07 --sigma 0.15 --simulations 10000
"""

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np


# ============================================================
# 数据结构定义
# ============================================================

@dataclass
class YearRecord:
    """单年记录"""
    year: int                # 年份序号
    withdrawal: float        # 当年提款额 E(t)
    wealth_before: float     # 年初资产（提款前）
    wealth_after: float      # 年末资产（提款+增长后）
    return_rate: float       # 当年实际收益率
    withdrawal_ratio: float  # 实际提款率 E(t)/W(t-1)


@dataclass
class SimulationResult:
    """单次模拟结果"""
    is_bankrupt: bool             # 是否破产
    bankrupt_year: Optional[int]  # 破产年份（未破产则为 None）
    final_wealth: float           # 最终残值
    records: List[YearRecord]     # 逐年记录


@dataclass
class MonteCarloResult:
    """蒙特卡洛汇总结果"""
    num_simulations: int          # 模拟次数
    bankrupt_count: int           # 破产次数
    bankrupt_probability: float   # 破产概率
    # 各年份资产的分位数路径 [year][percentile]
    percentile_paths: dict        # {5: [...], 25: [...], 50: [...], 75: [...], 95: [...]}
    median_final_wealth: float    # 中位数最终残值


# ============================================================
# 收益率分布参数解析
# ============================================================

def build_return_params(years: int,
                        mu: Optional[float] = None,
                        sigma: Optional[float] = None,
                        phases: Optional[List[dict]] = None,
                        yearly: Optional[List[Tuple[float, float]]] = None
                        ) -> List[Tuple[float, float]]:
    """
    构建逐年的 (μ, σ) 参数列表

    三种模式：
      1. 全局统一：传入 mu, sigma → 所有年份相同
      2. 分阶段：传入 phases = [{"start": 1, "end": 10, "mu": 0.08, "sigma": 0.18}, ...]
      3. 逐年自定义：传入 yearly = [(μ1,σ1), (μ2,σ2), ...]

    返回：长度为 years 的列表 [(μ_1, σ_1), (μ_2, σ_2), ...]
    """
    # 模式③：逐年自定义
    if yearly is not None:
        if len(yearly) != years:
            raise ValueError(f"逐年参数列表长度({len(yearly)})与规划年限({years})不匹配")
        return yearly

    # 模式②：分阶段设定
    if phases is not None:
        params = [None] * years
        for phase in phases:
            start = phase["start"] - 1  # 转为 0-indexed
            end = phase["end"]
            for i in range(start, min(end, years)):
                params[i] = (phase["mu"], phase["sigma"])
        # 检查是否有未覆盖的年份
        for i, p in enumerate(params):
            if p is None:
                raise ValueError(f"第 {i+1} 年未被任何阶段覆盖，请检查 phases 配置")
        return params

    # 模式①：全局统一
    if mu is not None and sigma is not None:
        return [(mu, sigma)] * years

    raise ValueError("请提供收益率分布参数：(mu, sigma) 或 phases 或 yearly")


# ============================================================
# 核心计算引擎
# ============================================================

def run_basic(w0: float, e0: float, years: int,
              inflation: float, return_rate: float) -> SimulationResult:
    """
    基础模式：固定收益率的确定性迭代

    参数：
      w0: 初始资产
      e0: 首年提款金额
      years: 规划年限 T
      inflation: 通胀率 i
      return_rate: 固定年化收益率 R
    """
    records = []
    w = w0
    e = e0

    for t in range(1, years + 1):
        # 步骤①：通胀调整提款额（第1年也要调整，因为 e0 是"计划"金额，实际第1年提 e0*(1+i)）
        # 注：按文档逻辑，E(1) = E0 * (1+i)，即 E0 是基准，第1年就开始通胀
        # 但更常见的理解是 E0 就是第1年的实际提款额，从第2年开始通胀
        # 这里采用后者：第1年提 E0，第2年起通胀递增
        if t == 1:
            e_current = e0
        else:
            e_current = e * (1 + inflation)
            e = e_current

        wealth_before = w
        withdrawal_ratio = e_current / w if w > 0 else float('inf')

        # 步骤②：提款后增长
        w = (w - e_current) * (1 + return_rate)

        records.append(YearRecord(
            year=t,
            withdrawal=e_current,
            wealth_before=wealth_before,
            wealth_after=w,
            return_rate=return_rate,
            withdrawal_ratio=withdrawal_ratio
        ))

        # 步骤③：破产判定
        if w <= 0:
            return SimulationResult(
                is_bankrupt=True,
                bankrupt_year=t,
                final_wealth=w,
                records=records
            )

        # 更新 e 的基准（第1年特殊处理后）
        if t == 1:
            e = e_current

    return SimulationResult(
        is_bankrupt=False,
        bankrupt_year=None,
        final_wealth=w,
        records=records
    )


def run_single_monte_carlo(w0: float, e0: float, years: int,
                           inflation: float,
                           return_params: List[Tuple[float, float]],
                           rng: np.random.Generator) -> SimulationResult:
    """
    单次蒙特卡洛模拟

    参数：
      return_params: 逐年 (μ, σ) 列表
      rng: numpy 随机数生成器
    """
    records = []
    w = w0
    e = e0

    for t in range(1, years + 1):
        # 通胀调整
        if t == 1:
            e_current = e0
        else:
            e_current = e * (1 + inflation)
            e = e_current

        wealth_before = w
        withdrawal_ratio = e_current / w if w > 0 else float('inf')

        # 从对应年份的正态分布抽样收益率
        mu_t, sigma_t = return_params[t - 1]
        r_t = rng.normal(mu_t, sigma_t)

        # 提款后增长
        w = (w - e_current) * (1 + r_t)

        records.append(YearRecord(
            year=t,
            withdrawal=e_current,
            wealth_before=wealth_before,
            wealth_after=w,
            return_rate=r_t,
            withdrawal_ratio=withdrawal_ratio
        ))

        # 破产判定
        if w <= 0:
            return SimulationResult(
                is_bankrupt=True,
                bankrupt_year=t,
                final_wealth=w,
                records=records
            )

        if t == 1:
            e = e_current

    return SimulationResult(
        is_bankrupt=False,
        bankrupt_year=None,
        final_wealth=w,
        records=records
    )


def run_monte_carlo(w0: float, e0: float, years: int,
                    inflation: float,
                    return_params: List[Tuple[float, float]],
                    num_simulations: int = 10000,
                    seed: Optional[int] = None) -> MonteCarloResult:
    """
    蒙特卡洛批量模拟

    参数：
      return_params: 逐年 (μ, σ) 列表
      num_simulations: 模拟次数 N
      seed: 随机种子（可选，用于复现）
    """
    rng = np.random.default_rng(seed)

    # 存储每次模拟每年的资产值，用于计算分位数
    # shape: (num_simulations, years)
    all_wealth_paths = np.zeros((num_simulations, years))
    bankrupt_count = 0

    for sim in range(num_simulations):
        result = run_single_monte_carlo(w0, e0, years, inflation, return_params, rng)
        if result.is_bankrupt:
            bankrupt_count += 1
            # 破产后填充 0
            for rec in result.records:
                all_wealth_paths[sim, rec.year - 1] = max(rec.wealth_after, 0)
            for y in range(len(result.records), years):
                all_wealth_paths[sim, y] = 0
        else:
            for rec in result.records:
                all_wealth_paths[sim, rec.year - 1] = rec.wealth_after

    # 计算分位数路径
    percentiles = [5, 25, 50, 75, 95]
    percentile_paths = {}
    for p in percentiles:
        percentile_paths[p] = np.percentile(all_wealth_paths, p, axis=0).tolist()

    median_final = np.median(all_wealth_paths[:, -1])

    return MonteCarloResult(
        num_simulations=num_simulations,
        bankrupt_count=bankrupt_count,
        bankrupt_probability=bankrupt_count / num_simulations,
        percentile_paths=percentile_paths,
        median_final_wealth=median_final
    )


# ============================================================
# 输出模块
# ============================================================

def print_basic_result(result: SimulationResult):
    """控制台打印基础模式结果"""
    print("\n" + "=" * 70)
    print("  长周期资产消耗计算器 - 基础模式结果")
    print("=" * 70)

    # 表头
    header = f"{'年份':>4} | {'年初资产':>14} | {'提款金额':>12} | {'提款率':>7} | {'收益率':>6} | {'年末资产':>14}"
    print(header)
    print("-" * 70)

    for rec in result.records:
        print(f"{rec.year:>4} | {rec.wealth_before:>14,.0f} | {rec.withdrawal:>12,.0f} | "
              f"{rec.withdrawal_ratio:>6.2%} | {rec.return_rate:>5.2%} | {rec.wealth_after:>14,.0f}")

    print("-" * 70)
    if result.is_bankrupt:
        print(f"  [破产] 资产在第 {result.bankrupt_year} 年耗尽")
    else:
        print(f"  [成功] 规划期满，最终残值: ¥{result.final_wealth:,.0f}")
    print("=" * 70)


def print_monte_carlo_result(mc_result: MonteCarloResult, years: int):
    """控制台打印蒙特卡洛结果"""
    print("\n" + "=" * 70)
    print("  长周期资产消耗计算器 - 蒙特卡洛模拟结果")
    print("=" * 70)
    print(f"  模拟次数: {mc_result.num_simulations:,}")
    print(f"  破产次数: {mc_result.bankrupt_count:,}")
    print(f"  破产概率: {mc_result.bankrupt_probability:.2%}")
    print(f"  中位数最终残值: ¥{mc_result.median_final_wealth:,.0f}")
    print("-" * 70)

    # 分位数路径摘要（每5年输出一次）
    print(f"\n{'年份':>4} | {'5%分位':>14} | {'25%分位':>14} | {'50%中位':>14} | {'75%分位':>14} | {'95%分位':>14}")
    print("-" * 90)
    step = max(1, years // 6)
    display_years = list(range(step, years, step)) + [years]
    for y in display_years:
        idx = y - 1
        print(f"{y:>4} | {mc_result.percentile_paths[5][idx]:>14,.0f} | "
              f"{mc_result.percentile_paths[25][idx]:>14,.0f} | "
              f"{mc_result.percentile_paths[50][idx]:>14,.0f} | "
              f"{mc_result.percentile_paths[75][idx]:>14,.0f} | "
              f"{mc_result.percentile_paths[95][idx]:>14,.0f}")
    print("=" * 90)


def export_basic_csv(result: SimulationResult, filepath: str):
    """导出基础模式结果到 CSV"""
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['年份', '年初资产', '提款金额', '提款率', '收益率', '年末资产'])
        for rec in result.records:
            writer.writerow([
                rec.year,
                f"{rec.wealth_before:.2f}",
                f"{rec.withdrawal:.2f}",
                f"{rec.withdrawal_ratio:.4f}",
                f"{rec.return_rate:.4f}",
                f"{rec.wealth_after:.2f}"
            ])
    print(f"\n  结果已导出至: {filepath}")


def export_monte_carlo_csv(mc_result: MonteCarloResult, years: int, filepath: str):
    """导出蒙特卡洛分位数路径到 CSV"""
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['年份', '5%分位', '25%分位', '50%中位', '75%分位', '95%分位'])
        for y in range(1, years + 1):
            idx = y - 1
            writer.writerow([
                y,
                f"{mc_result.percentile_paths[5][idx]:.2f}",
                f"{mc_result.percentile_paths[25][idx]:.2f}",
                f"{mc_result.percentile_paths[50][idx]:.2f}",
                f"{mc_result.percentile_paths[75][idx]:.2f}",
                f"{mc_result.percentile_paths[95][idx]:.2f}"
            ])
    print(f"\n  分位数路径已导出至: {filepath}")


# ============================================================
# CLI 入口
# ============================================================

def parse_phases(phases_str: str) -> List[dict]:
    """
    解析分阶段参数字符串
    格式: JSON 数组，如 '[{"start":1,"end":10,"mu":0.08,"sigma":0.18},...]'
    """
    try:
        phases = json.loads(phases_str)
        for p in phases:
            assert all(k in p for k in ("start", "end", "mu", "sigma"))
        return phases
    except (json.JSONDecodeError, AssertionError, KeyError):
        raise argparse.ArgumentTypeError(
            "phases 格式错误，应为 JSON 数组: "
            '[{"start":1,"end":10,"mu":0.08,"sigma":0.18}, ...]'
        )


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description="长周期资产消耗计算器（Lifelong Cash Withdrawer）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基础模式
  python3 calculator.py --mode basic --w0 5000000 --rate 0.04 --years 30 --inflation 0.03 --return_rate 0.07

  # 蒙特卡洛（全局统一参数）
  python3 calculator.py --mode monte_carlo --w0 5000000 --rate 0.04 --years 30 --inflation 0.03 --mu 0.07 --sigma 0.15

  # 蒙特卡洛（分阶段参数）
  python3 calculator.py --mode monte_carlo --w0 5000000 --rate 0.04 --years 30 --inflation 0.03 \\
    --phases '[{"start":1,"end":10,"mu":0.08,"sigma":0.18},{"start":11,"end":20,"mu":0.06,"sigma":0.12},{"start":21,"end":30,"mu":0.05,"sigma":0.08}]'
        """
    )

    # 必选参数
    parser.add_argument('--mode', choices=['basic', 'monte_carlo'], required=True, help='计算模式: basic(基础) 或 monte_carlo(蒙特卡洛)')
    parser.add_argument('--w0', type=float, required=True, help='初始资产总额')
    parser.add_argument('--years', type=int, required=True, help='规划年限 T')
    parser.add_argument('--inflation', type=float, required=True, help='预计长期通胀率（如 0.03 表示 3%%）')

    # 提款参数（二选一）
    parser.add_argument('--e0', type=float, default=None, help='首年提款金额（与 --rate 二选一）')
    parser.add_argument('--rate', type=float, default=None, help='首年提款率（与 --e0 二选一，如 0.04 表示 4%%）')

    # 基础模式参数
    parser.add_argument('--return_rate', type=float, default=None, help='[基础模式] 固定年化收益率 R（如 0.07 表示 7%%）')

    # 蒙特卡洛参数
    parser.add_argument('--mu', type=float, default=None, help='[蒙特卡洛] 全局收益率均值 μ')
    parser.add_argument('--sigma', type=float, default=None, help='[蒙特卡洛] 全局收益率标准差 σ')
    parser.add_argument('--phases', type=parse_phases, default=None, help='[蒙特卡洛] 分阶段参数，JSON格式')
    parser.add_argument('--simulations', type=int, default=10000, help='[蒙特卡洛] 模拟次数（默认 10000）')
    parser.add_argument('--seed', type=int, default=None, help='[蒙特卡洛] 随机种子（可选，用于复现结果）')

    # 输出参数
    parser.add_argument('--output', type=str, default=None, help='输出 CSV 文件路径（可选）')

    args = parser.parse_args()

    # --- 参数校验 ---
    # 提款金额计算
    if args.e0 is not None:
        e0 = args.e0
        rate = e0 / args.w0
    elif args.rate is not None:
        rate = args.rate
        e0 = args.w0 * rate
    else:
        parser.error("请提供 --e0（首年提款金额）或 --rate（首年提款率）")

    print(f"\n  初始资产: ¥{args.w0:,.0f}")
    print(f"  首年提款: ¥{e0:,.0f}（提款率 {rate:.2%}）")
    print(f"  规划年限: {args.years} 年")
    print(f"  通胀率: {args.inflation:.2%}")

    # --- 执行计算 ---
    if args.mode == 'basic':
        if args.return_rate is None:
            parser.error("基础模式需要提供 --return_rate")
        print(f"  固定收益率: {args.return_rate:.2%}")

        result = run_basic(args.w0, e0, args.years, args.inflation, args.return_rate)
        print_basic_result(result)

        if args.output:
            export_basic_csv(result, args.output)

    elif args.mode == 'monte_carlo':
        # 构建收益率参数
        try:
            return_params = build_return_params(
                years=args.years,
                mu=args.mu,
                sigma=args.sigma,
                phases=args.phases
            )
        except ValueError as e:
            parser.error(str(e))

        mu_first, sigma_first = return_params[0]
        mu_last, sigma_last = return_params[-1]
        print(f"  收益率分布: 第1年 N({mu_first:.2%}, {sigma_first:.2%}) → 第{args.years}年 N({mu_last:.2%}, {sigma_last:.2%})")
        print(f"  模拟次数: {args.simulations:,}")

        mc_result = run_monte_carlo(
            w0=args.w0,
            e0=e0,
            years=args.years,
            inflation=args.inflation,
            return_params=return_params,
            num_simulations=args.simulations,
            seed=args.seed
        )
        print_monte_carlo_result(mc_result, args.years)

        if args.output:
            export_monte_carlo_csv(mc_result, args.years, args.output)


