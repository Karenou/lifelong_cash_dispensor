"""
长周期资产消耗计算器 - 可视化网页
基于 Streamlit 构建的交互式面板

启动方式：
  cd lifelong_cash_withdrawer/visualization
  streamlit run app.py
"""

import sys
import os

# 将父目录加入 path，以便导入 calculator 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from calculator import (
    run_basic,
    run_monte_carlo,
    build_return_params,
)


# ============================================================
# 页面配置
# ============================================================

st.set_page_config(
    page_title="人生提款模拟器",
    page_icon="💰",
    layout="wide"
)

# 白色背景 + 黑色字体
st.markdown("""
<style>
    .stApp {
        background-color: #ffffff;
        color: #000000;
    }
    /* 顶部 header 栏 */
    [data-testid="stHeader"], header {
        background-color: #ffffff !important;
    }
    .stSidebar, [data-testid="stSidebar"] {
        background-color: #f5f5f5;
        color: #000000;
    }
    h1, h2, h3, h4, h5, h6, p, span, label, .stMarkdown, .stCaption,
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"],
    .css-1629p8f, .css-10trblm, .css-16idsys {
        color: #000000 !important;
    }
    .stRadio label, .stCheckbox label, .stSelectbox label,
    .stSlider label, .stNumberInput label {
        color: #000000 !important;
    }
    /* expander 折叠/展开区域统一浅色 */
    [data-testid="stExpander"] {
        background-color: #f9f9f9 !important;
        border: 1px solid #e0e0e0 !important;
        border-radius: 4px;
    }
    [data-testid="stExpander"] summary {
        color: #000000 !important;
        background-color: #f9f9f9 !important;
    }
    [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        background-color: #f9f9f9 !important;
        color: #000000 !important;
    }
    /* dataframe 表格 */
    .stDataFrame, [data-testid="stDataFrame"] {
        background-color: #ffffff !important;
    }
    [data-testid="stDataFrame"] th, [data-testid="stDataFrame"] td {
        color: #000000 !important;
        background-color: #ffffff !important;
    }
    /* 侧边栏滑块、按钮等主题色改为深蓝 */
    [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] div[role="slider"] {
        background-color: #64B5F6 !important;
    }
    [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] div[data-testid="stThumbValue"] {
        color: #1565C0 !important;
    }
    [data-testid="stSidebar"] button[kind="primary"] {
        background-color: #DDE3F0 !important;
        border-color: #DDE3F0 !important;
        color: #000000 !important;
    }
    [data-testid="stSidebar"] .stCheckbox svg {
        color: #1565C0 !important;
        fill: #1565C0 !important;
    }
    /* 全局 Streamlit 主色调改为深蓝 */
    :root {
        --primary-color: #1565C0;
    }
    .st-emotion-cache-1gulkj5, .st-emotion-cache-1aehpvj {
        color: #1565C0 !important;
    }
    /* 滑块圆点 */
    div[data-baseweb="slider"] div[role="slider"] {
        background-color: #64B5F6 !important;
    }
    /* 滑块已滑过的轨道（红线 → 浅蓝线） */
    div[data-baseweb="slider"] div[data-testid="stTickBar"] > div:first-child {
        background-color: #64B5F6 !important;
    }
    /* slider track active 部分 - 覆盖各种可能的选择器 */
    div[data-baseweb="slider"] div[role="progressbar"],
    div[data-baseweb="slider"] div[class*="Track"] div:first-child,
    div[data-baseweb="slider"] div[class*="InnerTrack"],
    [data-baseweb="slider"] [style*="background-color: rgb"],
    .stSlider div[data-baseweb="slider"] > div > div > div:first-child {
        background-color: #64B5F6 !important;
    }
    /* 强制覆盖 streamlit 默认红色 */
    .stSlider [data-testid="stTickBar"] > div {
        background: #64B5F6 !important;
    }
    /* 滑块数值文字 */
    div[data-baseweb="slider"] div[data-testid="stThumbValue"] {
        color: #1565C0 !important;
    }
    .stButton button[kind="primary"] {
        background-color: #DDE3F0 !important;
        border-color: #DDE3F0 !important;
        color: #000000 !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("人生提款模拟器")
st.caption("基于 Trinity Study 的退休资产模拟工具 — 资产能撑多少年？")


# ============================================================
# 侧边栏：参数输入
# ============================================================

with st.sidebar:
    st.header("参数设置")

    st.subheader("A. 初始状态")
    w0 = st.number_input("初始资产总额（¥）", min_value=100000, max_value=100000000,
                         value=1000000, step=100000, format="%d")
    withdrawal_input = st.radio("提款方式", ["按提款率", "按提款金额"])
    if withdrawal_input == "按提款率":
        rate = st.slider("首年提款率", min_value=0.01, max_value=0.15, value=0.04, step=0.005, format="%.3f")
        e0 = w0 * rate
        st.info(f"首年提款金额: ¥{e0:,.0f}")
    else:
        e0 = st.number_input("首年提款金额（¥）", min_value=10000, max_value=10000000,
                             value=200000, step=10000, format="%d")
        rate = e0 / w0
        st.info(f"对应提款率: {rate:.2%}")

    st.subheader("B. 宏观环境")
    years = st.slider("规划年限（年）", min_value=5, max_value=60, value=30, step=1)
    inflation = st.slider("预期通胀率", min_value=0.0, max_value=0.10, value=0.03, step=0.005, format="%.3f")

    st.subheader("C. 资产回报")
    return_rate = st.slider("预期年化收益率（μ）", min_value=0.0, max_value=0.20, value=0.055, step=0.005, format="%.3f")

    st.subheader("D. 蒙特卡洛设置")
    enable_mc = st.checkbox("启用蒙特卡洛模拟", value=True)
    sigma = st.slider("收益率标准差（σ）", min_value=0.01, max_value=0.40, value=0.15, step=0.01, format="%.2f",
                      disabled=not enable_mc)
    num_simulations = st.select_slider("模拟次数", options=[1000, 3000, 5000, 10000, 20000, 50000],
                                       value=5000, disabled=not enable_mc)

    run_btn = st.button("开始计算", type="primary", use_container_width=True)


# ============================================================
# 计算与展示
# ============================================================

if run_btn:
    # --- 基础模式 ---
    basic_result = run_basic(w0, e0, years, inflation, return_rate)

    # 构造 DataFrame
    df_basic = pd.DataFrame([
        {
            "年份": rec.year,
            "年初资产": rec.wealth_before,
            "提款金额": rec.withdrawal,
            "年末资产": rec.wealth_after,
            "提款率": rec.withdrawal_ratio,
        }
        for rec in basic_result.records
    ])

    # --- 基础模式结果展示 ---
    st.header("基础模式（固定收益率）")

    col1, col2, col3 = st.columns(3)
    with col1:
        status = "破产" if basic_result.is_bankrupt else "成功"
        st.metric("模拟结果", status)
    with col2:
        if basic_result.is_bankrupt:
            st.metric("破产年份", f"第 {basic_result.bankrupt_year} 年")
        else:
            st.metric("最终残值", f"¥{basic_result.final_wealth:,.0f}")
    with col3:
        st.metric("固定收益率", f"{return_rate:.2%}")

    # 折线图：资产轨迹 + 提款金额
    fig_basic = make_subplots(specs=[[{"secondary_y": True}]])

    fig_basic.add_trace(
        go.Scatter(x=df_basic["年份"], y=df_basic["年末资产"],
                   name="年末资产", line=dict(color="#1565C0", width=2.5),
                   hovertemplate="¥%{y:,.0f}<extra></extra>"),
        secondary_y=False
    )
    fig_basic.add_trace(
        go.Scatter(x=df_basic["年份"], y=df_basic["提款金额"],
                   name="提款金额", line=dict(color="#FF9800", width=2),
                   hovertemplate="¥%{y:,.0f}<extra></extra>"),
        secondary_y=True
    )

    fig_basic.update_layout(
        title=dict(text="基础模式 - 资产轨迹与提款金额", font=dict(color="#000000")),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(color="#000000")),
        height=450,
        template="plotly_white",
        font=dict(color="#000000"),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff"
    )
    fig_basic.update_xaxes(title_text="年份", showgrid=False,
                           tickfont=dict(color="#000000"), title_font=dict(color="#000000"))
    fig_basic.update_yaxes(title_text="资产（¥）", secondary_y=False, tickformat=",",
                           rangemode="tozero", showgrid=False,
                           tickfont=dict(color="#000000"), title_font=dict(color="#000000"))
    fig_basic.update_yaxes(title_text="提款金额（¥）", secondary_y=True, tickformat=",",
                           showgrid=False,
                           tickfont=dict(color="#000000"), title_font=dict(color="#000000"))

    st.plotly_chart(fig_basic, use_container_width=True)

    # 提款率曲线
    fig_ratio = go.Figure()
    fig_ratio.add_trace(
        go.Scatter(x=df_basic["年份"], y=df_basic["提款率"],
                   name="实际提款率", line=dict(color="#4CAF50", width=2),
                   fill="tozeroy", fillcolor="rgba(76,175,80,0.1)")
    )
    fig_ratio.add_hline(y=rate, line_dash="dash", line_color="red",
                        annotation_text=f"初始提款率 {rate:.2%}")
    fig_ratio.update_layout(
        title="实际每年提款金额/上年末资产趋势变化",
        xaxis_title="年份",
        yaxis_title="提款率",
        yaxis_tickformat=".1%",
        height=350,
        template="plotly_white",
        font=dict(color="#000000"),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        xaxis=dict(showgrid=False, tickfont=dict(color="#000000")),
        yaxis=dict(gridcolor="rgba(200,200,200,0.4)", tickfont=dict(color="#000000"))
    )
    st.plotly_chart(fig_ratio, use_container_width=True)

    # 明细表
    with st.expander("查看逐年明细表"):
        df_display = df_basic.copy()
        df_display["年初资产"] = df_display["年初资产"].apply(lambda x: f"¥{x:,.0f}")
        df_display["提款金额"] = df_display["提款金额"].apply(lambda x: f"¥{x:,.0f}")
        df_display["年末资产"] = df_display["年末资产"].apply(lambda x: f"¥{x:,.0f}")
        df_display["提款率"] = df_display["提款率"].apply(lambda x: f"{x:.2%}")
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    # --- 蒙特卡洛模式 ---
    if enable_mc:
        st.header("蒙特卡洛模拟（随机收益率）")

        with st.spinner(f"正在进行 {num_simulations:,} 次模拟..."):
            return_params = build_return_params(years=years, mu=return_rate, sigma=sigma)
            mc_result = run_monte_carlo(
                w0=w0, e0=e0, years=years,
                inflation=inflation,
                return_params=return_params,
                num_simulations=num_simulations,
                seed=42
            )

        # 汇总指标
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("模拟次数", f"{mc_result.num_simulations:,}")
        with col2:
            st.metric("破产概率", f"{mc_result.bankrupt_probability:.1%}")
        with col3:
            st.metric("存活率", f"{1 - mc_result.bankrupt_probability:.1%}")
        with col4:
            st.metric("中位数残值", f"¥{mc_result.median_final_wealth:,.0f}")

        # 扇形图：分位数路径
        years_range = list(range(1, years + 1))
        fig_mc = go.Figure()

        # 5%-95% 区间（浅色填充）
        fig_mc.add_trace(go.Scatter(
            x=years_range, y=mc_result.percentile_paths[95],
            mode='lines', line=dict(width=0), showlegend=False, name="95%分位",
            hovertemplate="¥%{y:,.0f}<extra></extra>"
        ))
        fig_mc.add_trace(go.Scatter(
            x=years_range, y=mc_result.percentile_paths[5],
            mode='lines', line=dict(width=0),
            fill='tonexty', fillcolor='rgba(33,150,243,0.1)',
            name="5%-95% 区间",
            hovertemplate="¥%{y:,.0f}<extra></extra>"
        ))

        # 25%-75% 区间（中等填充）
        fig_mc.add_trace(go.Scatter(
            x=years_range, y=mc_result.percentile_paths[75],
            mode='lines', line=dict(width=0), showlegend=False, name="75%分位",
            hovertemplate="¥%{y:,.0f}<extra></extra>"
        ))
        fig_mc.add_trace(go.Scatter(
            x=years_range, y=mc_result.percentile_paths[25],
            mode='lines', line=dict(width=0),
            fill='tonexty', fillcolor='rgba(33,150,243,0.25)',
            name="25%-75% 区间",
            hovertemplate="¥%{y:,.0f}<extra></extra>"
        ))

        # 50% 中位线
        fig_mc.add_trace(go.Scatter(
            x=years_range, y=mc_result.percentile_paths[50],
            mode='lines', line=dict(color='#1565C0', width=2.5),
            name="中位数（50%）",
            hovertemplate="¥%{y:,.0f}<extra></extra>"
        ))

        # 基础模式对照线
        basic_wealth = [rec.wealth_after for rec in basic_result.records]
        fig_mc.add_trace(go.Scatter(
            x=years_range, y=basic_wealth,
            mode='lines', line=dict(color='#FF5722', width=2, dash='dash'),
            name="基础模式（固定收益）",
            hovertemplate="¥%{y:,.0f}<extra></extra>"
        ))

        fig_mc.update_layout(
            title=f"蒙特卡洛资产路径扇形图（N={num_simulations:,}, μ={return_rate:.1%}, σ={sigma:.1%}）",
            xaxis_title="年份",
            yaxis_title="资产（¥）",
            yaxis_tickformat=",",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        font=dict(color="#000000")),
            height=500,
            template="plotly_white",
            font=dict(color="#000000"),
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
            xaxis=dict(showgrid=False, tickfont=dict(color="#000000"),
                       title_font=dict(color="#000000")),
            yaxis=dict(gridcolor="rgba(200,200,200,0.4)", tickfont=dict(color="#000000"),
                       title_font=dict(color="#000000"))
        )
        st.plotly_chart(fig_mc, use_container_width=True)

        # 分位数表
        with st.expander("查看分位数路径数据"):
            df_mc = pd.DataFrame({
                "年份": years_range,
                "5%分位": mc_result.percentile_paths[5],
                "25%分位": mc_result.percentile_paths[25],
                "50%中位": mc_result.percentile_paths[50],
                "75%分位": mc_result.percentile_paths[75],
                "95%分位": mc_result.percentile_paths[95],
            })
            for col in ["5%分位", "25%分位", "50%中位", "75%分位", "95%分位"]:
                df_mc[col] = df_mc[col].apply(lambda x: f"¥{x:,.0f}")
            st.dataframe(df_mc, use_container_width=True, hide_index=True)

else:
    # 初始状态提示
    st.info("请在左侧设置参数，然后点击「开始计算」按钮。")

    # 显示当前参数摘要
    st.subheader("当前参数摘要")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"- 初始资产: **¥{w0:,.0f}**")
        st.write(f"- 首年提款: **¥{e0:,.0f}**（提款率 {rate:.2%}）")
        st.write(f"- 规划年限: **{years}** 年")
    with col2:
        st.write(f"- 通胀率: **{inflation:.2%}**")
        st.write(f"- 预期收益率: **{return_rate:.2%}**")
        if enable_mc:
            st.write(f"- 收益率标准差: **{sigma:.2%}**")
            st.write(f"- 模拟次数: **{num_simulations:,}**")
