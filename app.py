import streamlit as st
import pandas as pd
import random
import plotly.express as px
import plotly.graph_objects as go
from db_manager import (
    init_db, get_all_history, 
    get_active_pursuit_task, create_pursuit_task, update_pursuit_status
)
from crawler import sync_latest_data
from ai_predictor import predict_smart_combination, backtest_strategy_rolling
from pursuit_calculator import generate_pursuit_plan, audit_pursuit_tracker

# 1. 移动端优先视口配置
st.set_page_config(
    page_title="快乐8量化系统",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)
init_db()

# 2. 深度自适应移动端样式注入
st.markdown("""
<style>
    /* 全局页面边距微调，消除手机端多余白边 */
    .stApp {
        background-color: #0b0e14;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }

    /* 标题自适应，杜绝单字掉行 */
    .mobile-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 12px;
    }
    .main-title {
        font-size: clamp(19px, 5.2vw, 25px) !important;
        font-weight: 800 !important;
        white-space: nowrap;
        background: linear-gradient(90deg, #ffffff 0%, #00e5ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: 0.5px;
        margin: 0 !important;
    }

    /* 模块卡片 */
    .metric-card {
        background: linear-gradient(135deg, #151922 0%, #1a202c 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 12px 14px;
        margin-bottom: 12px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4);
    }

    /* 号码球容器：弹性单行自适应，保证 6 球永远水平排开 */
    .balls-flex-box {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: clamp(4px, 1.8vw, 10px);
        margin: 8px 0;
        flex-wrap: nowrap;
    }
    .lotto-ball {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: clamp(36px, 10.5vw, 44px);
        height: clamp(36px, 10.5vw, 44px);
        border-radius: 50%;
        color: #ffffff;
        font-weight: 800;
        font-size: clamp(15px, 4.2vw, 18px);
        box-shadow: inset -2px -2px 6px rgba(0,0,0,0.5), 0 3px 8px rgba(0,0,0,0.4);
        flex-shrink: 0;
    }
    .ball-red { background: radial-gradient(circle at 35% 35%, #ff5252, #b71c1c); }
    .ball-blue { background: radial-gradient(circle at 35% 35%, #40c4ff, #0277bd); }

    /* 专属网点徽章 */
    .station-badge {
        display: inline-flex;
        align-items: center;
        background: linear-gradient(135deg, #ff9100 0%, #ff6d00 100%);
        color: #ffffff;
        font-weight: 700;
        font-size: 13px;
        padding: 4px 12px;
        border-radius: 16px;
        margin: 4px 0 6px 0;
    }

    /* 移动端 2x2 金融网格面板，消灭纵向瀑布流拉伸 */
    .quant-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 8px;
        margin-bottom: 10px;
    }
    .quant-box {
        background: #141822;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 9px 12px;
    }
    .quant-label { font-size: 11px; color: #8fa0b5; margin-bottom: 2px; }
    .quant-val { font-size: 16px; font-weight: 800; color: #ffffff; }
    .quant-tag-green { font-size: 11px; color: #00e676; font-weight: 600; margin-top: 2px; }
    .quant-tag-red { font-size: 11px; color: #ff5252; font-weight: 600; margin-top: 2px; }

    /* 优化 Tab 选项卡横向滚动 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        overflow-x: auto;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 6px 12px;
        font-size: 13px;
        white-space: nowrap;
    }
</style>
""", unsafe_allow_html=True)

# 侧边栏
with st.sidebar:
    st.markdown("### ⚙️ 数据同步控制台")
    if st.button("🔄 同步官网最新开奖数据", use_container_width=True):
        with st.spinner("拉取增量数据..."):
            success, msg = sync_latest_data(page_size=150)
            if success:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    
    history_df = get_all_history()
    max_history_len = len(history_df)
    st.metric("本地开奖池样本期数", f"{max_history_len} 期")
    if max_history_len < 30:
        st.warning("⚠️ 样本数据较少，请先点击同步。")
        
    st.markdown("---")
    st.markdown("### 🛡️ 防跟单分流设置")
    station_count = st.slider("可用投注站数量 (A-Z轮转)", 2, 10, 3)

# 顶部标题栏
st.markdown("""
<div class="mobile-header">
    <span style="font-size:22px;">🎯</span>
    <span class="main-title">快乐8选五量化分析系统</span>
</div>
""", unsafe_allow_html=True)

# 实盘追号模块
active_task = get_active_pursuit_task()
if active_task:
    summary, audit_flow = audit_pursuit_tracker(active_task, history_df, station_count=station_count)
    t_nums = [x.strip() for x in active_task["target_numbers"].split(",") if x.strip()]
    balls_html = "".join([f"<span class='lotto-ball ball-blue'>{n}</span>" for n in t_nums])
    
    st.markdown(f"""
    <div class="metric-card">
        <div style="font-weight:800; font-size:14px; color:#ffffff;">📌 活跃实盘追号标的</div>
        <div class="balls-flex-box">{balls_html}</div>
        <div style="font-size:12px; color:#a0aec0; text-align:center;">
            起追期号: <b style="color:#fff;">{active_task['start_issue']}</b> | 计划: <b style="color:#fff;">{active_task['max_periods']} 期</b>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 紧凑四宫格面板
    profit_color_cls = "quant-tag-green" if summary['net_profit'] >= 0 else "quant-tag-red"
    st.markdown(f"""
    <div class="quant-grid">
        <div class="quant-box">
            <div class="quant-label">已追期数</div>
            <div class="quant-val">{summary['tracked_periods']} / {active_task['max_periods']}</div>
        </div>
        <div class="quant-box">
            <div class="quant-label">实投成本</div>
            <div class="quant-val">¥ {summary['total_cost']:,.0f}</div>
        </div>
        <div class="quant-box">
            <div class="quant-label">产生奖金</div>
            <div class="quant-val">¥ {summary['total_prize']:,.0f}</div>
        </div>
        <div class="quant-box">
            <div class="quant-label">实盘净利</div>
            <div class="quant-val">¥ {summary['net_profit']:+,.0f}</div>
            <div class="{profit_color_cls}">{summary['net_profit']:+} 元</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("❌ 结算并终止当前任务", use_container_width=True):
        update_pursuit_status(active_task["id"], "STOPPED")
        st.success("任务已归档！")
        st.rerun()

# 选项卡
tab1, tab2, tab3 = st.tabs(["🤖 AI预测与滚动回测", "💰 阶梯倍投测算", "📋 历史开奖池"])

with tab1:
    col1, col2 = st.columns([1, 1])
    with col1:
        strategy_option = st.selectbox(
            "分析策略引擎",
            options=["ADVANCED_ENSEMBLE", "HOT_COLD", "ML_HYBRID"],
            format_func=lambda x: {
                "ADVANCED_ENSEMBLE": "⚡ 多因子 + ExtraTrees",
                "HOT_COLD": "🔥 3热2温1冷 遗漏频次",
                "ML_HYBRID": "🌲 RandomForest 基础模型"
            }[x]
        )
    with col2:
        default_val = min(30, max(10, max_history_len - 15)) if max_history_len > 15 else 30
        backtest_window = st.number_input("自定义回测期数", min_value=10, max_value=max(10, max_history_len - 15) if max_history_len > 15 else 300, value=default_val, step=5)

    with st.spinner("AI 模型正在运算最优 6 码..."):
        latest_pred, strategy_desc = predict_smart_combination(n_select=6, strategy=strategy_option)

    # 6 码红球保证单行排开
    red_balls_html = "".join([f"<span class='lotto-ball ball-red'>{int(n):02d}</span>" for n in latest_pred])
    latest_iss = int(history_df.iloc[0]["issue"]) if not history_df.empty and str(history_df.iloc[0]["issue"]).isdigit() else 2026001
    assigned_next_station = chr(65 + random.Random(latest_iss + 1).randint(0, station_count - 1))

    st.markdown(f"""
    <div class="metric-card" style="text-align:center;">
        <div style="font-size:13px; color:#e0e6ed; margin-bottom:4px;">🔮 下期推荐 6 码复式（单倍 12 元）</div>
        <div class="balls-flex-box">{red_balls_html}</div>
        <div style="display:flex; justify-content:center;">
            <div class="station-badge">🏪 防跟单推荐：网点 {assigned_next_station}</div>
        </div>
        <div style="font-size:11px; color:#8fa0b5;">{strategy_desc}</div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🔒 一键锁定此号码开启实盘追号", use_container_width=True):
        latest_issue_str = str(history_df.iloc[0]["issue"]) if not history_df.empty else "2026001"
        pred_str = ",".join(f"{int(x):02d}" for x in latest_pred)
        create_pursuit_task(pred_str, latest_issue_str, max_periods=18, min_profit=20)
        st.success("已锁定！")
        st.rerun()

    st.markdown(f"<div style='font-size:15px; font-weight:700; margin: 14px 0 8px 0; color:#fff;'>📈 策略近 {backtest_window} 期滚动回测</div>", unsafe_allow_html=True)
    
    bt_df, err_msg = backtest_strategy_rolling(strategy=strategy_option, test_periods=backtest_window)
    if not bt_df.empty:
        total_runs = len(bt_df)
        total_invest = bt_df["投注成本(元)"].sum()
        total_payout = bt_df["获得奖金(元)"].sum()
        net_profit = total_payout - total_invest
        roi = (net_profit / total_invest) * 100 if total_invest > 0 else 0
        
        hit_counts = bt_df["命中注数"].value_counts().to_dict()
        hit3 = hit_counts.get("中 3 码", 0)
        hit4 = hit_counts.get("中 4 码", 0)
        hit5 = hit_counts.get("中 5 码", 0)
        hit6 = hit_counts.get("中 6 码", 0)
        total_profitable = hit3 + hit4 + hit5 + hit6
        win_rate = (total_profitable / total_runs) * 100 if total_runs > 0 else 0

        # 双列网格式精美指标看板（替代原来又臭又长的单列拉伸）
        roi_cls = "quant-tag-green" if net_profit >= 0 else "quant-tag-red"
        st.markdown(f"""
        <div class="quant-grid">
            <div class="quant-box">
                <div class="quant-label">回测期数</div>
                <div class="quant-val">{total_runs} 期</div>
            </div>
            <div class="quant-box">
                <div class="quant-label">累计成本</div>
                <div class="quant-val">¥ {total_invest:,.0f}</div>
            </div>
            <div class="quant-box">
                <div class="quant-label">累计奖金</div>
                <div class="quant-val">¥ {total_payout:,.0f}</div>
            </div>
            <div class="quant-box">
                <div class="quant-label">总净利润</div>
                <div class="quant-val">¥ {net_profit:+,.0f}</div>
                <div class="{roi_cls}">{roi:+.1f}% 盈亏率</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style="background: rgba(255,255,255,0.03); border-radius: 8px; padding: 8px 10px; margin-bottom: 12px; font-size: 11px; color: #a0aec0; line-height: 1.6;">
            <b>命中统计：</b>
            胜率: <b style="color:#00e5ff;">{win_rate:.1f}%</b> ({total_profitable}次) &nbsp;|&nbsp;
            中3(159元): <b>{hit3}</b> &nbsp;|&nbsp; 
            中4(254元): <b>{hit4}</b> &nbsp;|&nbsp; 
            中5(1105元): <b style="color:#ffab00;">{hit5}</b> &nbsp;|&nbsp; 
            中6(6000元): <b style="color:#ff5252;">{hit6}</b>
        </div>
        """, unsafe_allow_html=True)

        # 资金曲线图表优化：隐藏漂浮工具栏，消灭科学计数法，压缩图例
        chart_df = bt_df.sort_values("期号", ascending=True).copy()
        chart_df["累计成本"] = chart_df["投注成本(元)"].cumsum()
        chart_df["累计总奖金"] = chart_df["获得奖金(元)"].cumsum()
        chart_df["累计净利润"] = chart_df["当期盈亏(元)"].cumsum()
        # 期号转字符串显示（取后4位+“期”，如“6279期”，告别 2.0262M 乱码）
        chart_df["期号简写"] = [str(x)[-4:] + "期" for x in chart_df["期号"]]

        fig = px.line(
            chart_df, 
            x="期号简写", 
            y=["累计成本", "累计总奖金", "累计净利润"], 
            title="资金走势曲线 (元)",
            color_discrete_map={
                "累计成本": "#9e9e9e",
                "累计总奖金": "#00e5ff",
                "累计净利润": "#00e676"
            }
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#ffffff", size=11),
            margin=dict(l=10, r=10, t=35, b=25),
            xaxis=dict(type='category', nticks=5, showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10))
        )
        # config 禁用 displayModeBar，彻底消灭遮挡标题的相机、放大镜小按键
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        # 横向对比图优化
        compare_windows = [15, 30, 50]
        valid_windows = [w for w in compare_windows if w <= max_history_len - 15] or [min(30, max_history_len - 15)]

        comp_data = []
        for w in valid_windows:
            sub_slice = bt_df.head(w) if len(bt_df) >= w else bt_df
            w_runs = len(sub_slice)
            w_inv = sub_slice["投注成本(元)"].sum()
            w_pay = sub_slice["获得奖金(元)"].sum()
            w_profit = w_pay - w_inv
            w_hits = sub_slice["命中注数"].value_counts().to_dict()
            w_win = (sum([w_hits.get(k, 0) for k in ["中 3 码", "中 4 码", "中 5 码", "中 6 码"]]) / w_runs) * 100 if w_runs else 0
            comp_data.append({"周期": f"近{w}期", "净利": w_profit, "胜率": round(w_win, 1)})
            
        comp_df = pd.DataFrame(comp_data)
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(
            x=comp_df["周期"], y=comp_df["净利"], name="净利润",
            marker_color=["#00e676" if x >= 0 else "#ff5252" for x in comp_df["净利"]], yaxis="y"
        ))
        fig_comp.add_trace(go.Scatter(
            x=comp_df["周期"], y=comp_df["胜率"], name="胜率%",
            mode="lines+markers+text", text=[f"{v}%" for v in comp_df["胜率"]], textposition="top center",
            line=dict(color="#00e5ff", width=2), yaxis="y2"
        ))
        fig_comp.update_layout(
            title="多周期对比",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#ffffff", size=11),
            yaxis=dict(title="", showgrid=True, gridcolor="rgba(255,255,255,0.08)"),
            yaxis2=dict(title="", overlaying="y", side="right", showgrid=False, range=[0, 60]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)),
            margin=dict(l=10, r=10, t=35, b=25)
        )
        st.plotly_chart(fig_comp, use_container_width=True, config={'displayModeBar': False})

        # 明细表格折叠面板：隐藏冗余索引列
        with st.expander(f"查看近 {total_runs} 期中奖明细", expanded=False):
            bt_df_show = bt_df.copy()
            st_list = [chr(65 + i) for i in range(station_count)]
            bt_df_show["推荐网点"] = [f"网点 {random.Random(int(iss) if str(iss).isdigit() else 1).choice(st_list)}" for iss in bt_df_show["期号"]]
            disp_cols = ["期号", "推荐网点", "开奖日期", "预测6码", "命中注数", "当期盈亏(元)"]
            # hide_index=True 隐藏 0, 1, 2... 数字列
            st.dataframe(bt_df_show[disp_cols], use_container_width=True, hide_index=True, height=300)

with tab2:
    st.markdown("<div style='font-size:15px; font-weight:700; margin: 10px 0;'>💰 动态阶梯倍投计算器</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        max_p = st.slider("追号期数", 5, 25, 18)
    with c2:
        min_p = st.number_input("保底净利(元)", value=20, step=5)
    plan_df = generate_pursuit_plan(max_periods=max_p, min_profit=min_p)
    st.dataframe(plan_df, use_container_width=True, hide_index=True, height=350)

with tab3:
    st.markdown("<div style='font-size:15px; font-weight:700; margin: 10px 0;'>📋 历史开奖池</div>", unsafe_allow_html=True)
    if not history_df.empty:
        st.dataframe(history_df, use_container_width=True, hide_index=True, height=450)
    else:
        st.warning("暂无数据，请在侧边栏点击同步。")
