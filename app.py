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

# 1. 移动端与桌面全局布局配置
st.set_page_config(
    page_title="快乐8智能量化分析系统",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)
init_db()

# 2. 注入高对比度亮色、发光质感与移动端自适应 CSS
st.markdown("""
<style>
    .stApp {
        background-color: #0b0e14;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    .main-title {
        font-size: 28px !important;
        font-weight: 800 !important;
        background: linear-gradient(90deg, #ffffff 0%, #00e5ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 16px;
        letter-spacing: 0.5px;
    }
    
    .section-title {
        color: #f0f4f8 !important;
        font-size: 19px !important;
        font-weight: 700 !important;
        margin-top: 15px;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .metric-card {
        background: linear-gradient(135deg, #151922 0%, #1c2230 100%);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 14px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
    }
    
    .lotto-ball {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 44px;
        height: 44px;
        border-radius: 50%;
        color: #ffffff;
        font-weight: 800;
        font-size: 18px;
        margin: 4px;
        box-shadow: inset -3px -3px 6px rgba(0,0,0,0.45), 0 4px 10px rgba(0,0,0,0.4);
    }
    .ball-red {
        background: radial-gradient(circle at 35% 35%, #ff5252, #b71c1c);
    }
    .ball-blue {
        background: radial-gradient(circle at 35% 35%, #40c4ff, #0277bd);
    }
    
    .badge-status {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
    }
    .badge-success { background: rgba(0, 230, 118, 0.2); color: #00e676; border: 1px solid #00e676; }
    .badge-warning { background: rgba(255, 171, 0, 0.2); color: #ffab00; border: 1px solid #ffab00; }
    .badge-running { background: rgba(0, 176, 255, 0.2); color: #00b0ff; border: 1px solid #00b0ff; }

    /* 投注站专属醒目金色徽章 */
    .station-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: linear-gradient(135deg, #ff9100 0%, #ff6d00 100%);
        color: #ffffff;
        font-weight: 800;
        font-size: 15px;
        padding: 6px 14px;
        border-radius: 20px;
        box-shadow: 0 2px 10px rgba(255, 145, 0, 0.35);
        margin: 8px 0;
    }

    [data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] {
        color: #a0aec0 !important;
        font-weight: 500 !important;
    }
</style>
""", unsafe_allow_html=True)

# 侧边栏：同步控制与投注站配置
with st.sidebar:
    st.markdown("### ⚙️ 数据同步控制台")
    if st.button("🔄 同步官网最新开奖数据", use_container_width=True):
        with st.spinner("从官网拉取增量数据..."):
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
    station_count = st.slider("可用投注站数量 (按 A-Z 轮转)", min_value=2, max_value=10, value=3, step=1)
    available_stations = [f"网点 {chr(65 + i)}" for i in range(station_count)]
    st.caption(f"当前启用网点池: {', '.join(available_stations)}")

# 醒目大标题
st.markdown("<div class='main-title'>🎯 快乐8选五量化分析系统</div>", unsafe_allow_html=True)

# ----------------- 模块 A：实盘追号任务卡片 -----------------
active_task = get_active_pursuit_task()

if active_task:
    summary, audit_flow = audit_pursuit_tracker(active_task, history_df, station_count=station_count)
    t_nums = [x.strip() for x in active_task["target_numbers"].split(",") if x.strip()]
    balls_html = "".join([f"<span class='lotto-ball ball-blue'>{n}</span>" for n in t_nums])
    
    if summary["is_hit"]:
        status_badge = "<span class='badge-status badge-success'>已中出 · 达成止盈</span>"
    elif summary["is_expired"]:
        status_badge = "<span class='badge-status badge-warning'>达到上限 · 触发止损</span>"
    else:
        status_badge = "<span class='badge-status badge-running'>实时监控追踪中</span>"

    st.markdown(f"""
    <div class="metric-card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <span style="font-weight:800; font-size:16px; color:#ffffff;">📌 活跃实盘追号标的</span>
            {status_badge}
        </div>
        <div style="margin: 10px 0;">{balls_html}</div>
        <div style="font-size:13px; color:#a0aec0;">
            起追期号: <b style="color:#ffffff;">{active_task['start_issue']}</b> | 追号计划: <b style="color:#ffffff;">{active_task['max_periods']} 期</b>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("已追期数", f"{summary['tracked_periods']} / {active_task['max_periods']}")
    m2.metric("实投成本", f"¥ {summary['total_cost']:,.0f}")
    m3.metric("产生奖金", f"¥ {summary['total_prize']:,.0f}")
    m4.metric("实盘净利", f"¥ {summary['net_profit']:+,.0f}", delta=f"{summary['net_profit']:+} 元")

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("❌ 结算并终止当前任务"):
            update_pursuit_status(active_task["id"], "STOPPED")
            st.success("任务已归档！")
            st.rerun()
    with col_btn2:
        with st.expander("📄 查看实盘每期流水及分流投注站"):
            if not audit_flow.empty:
                st.dataframe(audit_flow, use_container_width=True)
else:
    st.markdown("""
    <div class="metric-card" style="text-align:center; padding:18px;">
        <span style="font-size:14px; color:#a0aec0;">💡 当前暂无锁定任务，可在下方预测中直接一键开启实盘追踪</span>
    </div>
    """, unsafe_allow_html=True)

# ----------------- 模块 B：选项卡导航 -----------------
tab1, tab2, tab3 = st.tabs(["🤖 AI预测与滚动回测", "💰 阶梯倍投测算", "📋 历史开奖池"])

# Tab 1: AI 预测与百期滚动验证
with tab1:
    c_s1, c_s2 = st.columns([3, 2])
    with c_s1:
        strategy_option = st.selectbox(
            "分析策略引擎",
            options=["ADVANCED_ENSEMBLE", "HOT_COLD", "ML_HYBRID"],
            format_func=lambda x: {
                "ADVANCED_ENSEMBLE": "⚡ 多因子 + ExtraTrees (算力强化)",
                "HOT_COLD": "🔥 3热2温1冷 遗漏频次模型",
                "ML_HYBRID": "🌲 RandomForest 基础模型"
            }[x]
        )
    with c_s2:
        default_val = min(30, max(10, max_history_len - 15)) if max_history_len > 15 else 30
        backtest_window = st.number_input(
            "自定义回测期数 (输入任意数字)", 
            min_value=10, 
            max_value=max(10, max_history_len - 15) if max_history_len > 15 else 300, 
            value=default_val, 
            step=5
        )

    # 实时预测计算
    with st.spinner("AI 模型正在计算最优 6 码组合并随机调度防跟单投注站..."):
        latest_pred, strategy_desc = predict_smart_combination(n_select=6, strategy=strategy_option)
    
    if not latest_pred or not isinstance(latest_pred, (list, tuple)) or len(latest_pred) != 6:
        import numpy as np
        latest_pred = sorted(list(np.random.choice(range(1, 81), 6, replace=False)))
        strategy_desc = (strategy_desc or "") + " (兜底安全组合)"

    red_balls_html = "".join([f"<span class='lotto-ball ball-red'>{int(n):02d}</span>" for n in latest_pred])
    
    # 基于开奖期数生成当期随机推荐的网点（A-Z）
    latest_iss_num = int(history_df.iloc[0]["issue"]) if not history_df.empty and str(history_df.iloc[0]["issue"]).isdigit() else 2026001
    rnd_gen = random.Random(latest_iss_num + 1)
    assigned_next_station = chr(65 + rnd_gen.randint(0, station_count - 1))

    st.markdown(f"""
    <div class="metric-card" style="text-align:center;">
        <div style="font-size:15px; font-weight:700; color:#e0e6ed; margin-bottom:8px;">🔮 下期推荐 6 码复式（单倍 12 元）</div>
        <div>{red_balls_html}</div>
        <div style="display:flex; justify-content:center; margin-top:8px;">
            <div class="station-badge">🏪 防跟单推荐投注站：网点 {assigned_next_station}</div>
        </div>
        <div style="font-size:12px; color:#8fa0b5; margin-top:4px;">{strategy_desc}</div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🔒 一键锁定此号码开启实盘追号", use_container_width=True):
        latest_issue_str = str(history_df.iloc[0]["issue"]) if not history_df.empty else "2026001"
        pred_str = ",".join(f"{int(x):02d}" for x in latest_pred)
        create_pursuit_task(pred_str, latest_issue_str, max_periods=18, min_profit=20)
        st.success("已锁定！")
        st.rerun()

    # 回测区域
    st.markdown(f"<div class='section-title'>📈 策略近 {backtest_window} 期滚动回测详细表现</div>", unsafe_allow_html=True)
    
    with st.spinner(f"正在进行近 {backtest_window} 期前向滚动验证..."):
        bt_df, err_msg = backtest_strategy_rolling(strategy=strategy_option, test_periods=backtest_window)
    
    if err_msg:
        st.warning(err_msg)
    elif not bt_df.empty:
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

        # 五大核心指标卡
        bm1, bm2, bm3, bm4, bm5 = st.columns(5)
        bm1.metric("回测期数", f"{total_runs} 期")
        bm2.metric("累计投注成本", f"¥ {total_invest:,.0f}")
        bm3.metric("累计中奖总额", f"¥ {total_payout:,.0f}")
        bm4.metric("总净利润", f"¥ {net_profit:+,.0f}", delta=f"{roi:+.1f}% 盈亏率")
        bm5.metric("盈利周期胜率", f"{win_rate:.1f}%", f"{total_profitable}次中奖")
        
        st.markdown(f"""
        <div style="background: rgba(255,255,255,0.03); border-radius: 8px; padding: 10px 14px; margin: 10px 0 16px 0; font-size: 13px; color: #a0aec0;">
            <b style="color: #ffffff;">各奖档命中统计：</b>
            中3码(159元): <b style="color:#00e5ff;">{hit3}</b> 次 &nbsp;|&nbsp; 
            中4码(254元): <b style="color:#00e5ff;">{hit4}</b> 次 &nbsp;|&nbsp; 
            中5码(1105元): <b style="color:#ffab00;">{hit5}</b> 次 &nbsp;|&nbsp; 
            中6码(6000元): <b style="color:#ff5252;">{hit6}</b> 次
        </div>
        """, unsafe_allow_html=True)

        # 资金走势图
        chart_df = bt_df.sort_values("期号", ascending=True).copy()
        chart_df["累计成本"] = chart_df["投注成本(元)"].cumsum()
        chart_df["累计总奖金"] = chart_df["获得奖金(元)"].cumsum()
        chart_df["累计净利润"] = chart_df["当期盈亏(元)"].cumsum()
        
        fig = px.line(
            chart_df, 
            x="期号", 
            y=["累计成本", "累计总奖金", "累计净利润"], 
            title=f"资金曲线：近 {total_runs} 期累计成本 vs 累计总奖金 vs 累计净利润 (元)",
            color_discrete_map={
                "累计成本": "#9e9e9e",
                "累计总奖金": "#00e5ff",
                "累计净利润": "#00e676"
            }
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#ffffff"),
            margin=dict(l=10, r=10, t=35, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

        # 多周期快速对比
        st.markdown("<div class='section-title'>📊 策略多周期胜率与盈亏快速横向对比</div>", unsafe_allow_html=True)
        compare_windows = [15, 30, 50, 100]
        valid_windows = [w for w in compare_windows if w <= max_history_len - 15]
        if not valid_windows:
            valid_windows = [min(30, max_history_len - 15)]

        comp_data = []
        for w in valid_windows:
            sub_slice = bt_df.head(w) if len(bt_df) >= w else bt_df
            w_runs = len(sub_slice)
            w_inv = sub_slice["投注成本(元)"].sum()
            w_pay = sub_slice["获得奖金(元)"].sum()
            w_profit = w_pay - w_inv
            w_roi = (w_profit / w_inv) * 100 if w_inv > 0 else 0
            
            w_hits = sub_slice["命中注数"].value_counts().to_dict()
            w_hit_num = w_hits.get("中 3 码", 0) + w_hits.get("中 4 码", 0) + w_hits.get("中 5 码", 0) + w_hits.get("中 6 码", 0)
            w_winrate = (w_hit_num / w_runs) * 100 if w_runs > 0 else 0
            
            comp_data.append({
                "统计周期": f"近 {w} 期",
                "胜率(%)": round(w_winrate, 1),
                "净利润(元)": round(w_profit, 0),
                "投资回报率(%)": round(w_roi, 1),
                "累计投入": w_inv,
                "总中奖金额": w_pay
            })
            
        comp_df = pd.DataFrame(comp_data)
        
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(
            x=comp_df["统计周期"],
            y=comp_df["净利润(元)"],
            name="净利润 (元)",
            marker_color=["#00e676" if x >= 0 else "#ff5252" for x in comp_df["净利润(元)"]],
            yaxis="y"
        ))
        fig_comp.add_trace(go.Scatter(
            x=comp_df["统计周期"],
            y=comp_df["胜率(%)"],
            name="中奖胜率 (%)",
            mode="lines+markers+text",
            text=[f"{v}%" for v in comp_df["胜率(%)"]],
            textposition="top center",
            line=dict(color="#00e5ff", width=3),
            marker=dict(size=8, color="#ffffff"),
            yaxis="y2"
        ))
        
        fig_comp.update_layout(
            title="各周期净利润与胜率横向对比",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#ffffff"),
            yaxis=dict(title="净利润 (元)", showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
            yaxis2=dict(title="胜率 (%)", overlaying="y", side="right", range=[0, 50], showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=10, r=10, t=35, b=10)
        )
        st.plotly_chart(fig_comp, use_container_width=True)

        # 历史记录明细折叠表格（附带当时随机轮选的网点）
        with st.expander(f"查看近 {total_runs} 期逐期开奖与中奖明细", expanded=False):
            def highlight_profit(row):
                if row["获得奖金(元)"] > 0:
                    return ["background-color: #1b5e20; color: #ffffff; font-weight: bold;"] * len(row)
                return [""] * len(row)
            
            # 为历史记录按期号附带当时分配的网点
            bt_df_show = bt_df.copy()
            st_list = [chr(65 + i) for i in range(station_count)]
            bt_df_show["推荐网点"] = [
                f"网点 {random.Random(int(iss) if str(iss).isdigit() else 1).choice(st_list)}" 
                for iss in bt_df_show["期号"]
            ]
            
            disp_cols = ["期号", "推荐网点", "开奖日期", "预测6码", "命中注数", "获得奖金(元)", "当期盈亏(元)"]
            styled_bt = bt_df_show[disp_cols].style.apply(highlight_profit, axis=1)
            st.dataframe(styled_bt, use_container_width=True, height=350)

# Tab 2: 动态倍投追号测算器
with tab2:
    st.markdown("<div class='section-title'>💰 动态阶梯倍投计算器</div>", unsafe_allow_html=True)
    c_p1, c_p2 = st.columns(2)
    with c_p1:
        max_p = st.slider("追号计划期数", 5, 25, 18)
    with c_p2:
        min_p = st.number_input("最低保底单期净利 (元)", value=20, step=5)
        
    plan_df = generate_pursuit_plan(max_periods=max_p, min_profit=min_p)
    st.dataframe(plan_df, use_container_width=True, height=400)

# Tab 3: 官网历史开奖池
with tab3:
    st.markdown("<div class='section-title'>📋 官网历史开奖数据池</div>", unsafe_allow_html=True)
    if not history_df.empty:
        st.dataframe(history_df, use_container_width=True, height=500)
    else:
        st.warning("暂无数据，请在侧边栏点击同步。")