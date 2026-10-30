import streamlit as st
import pandas as pd
import random
import plotly.express as px
from datetime import datetime
from db_manager import (
    init_db, get_all_history, get_latest_issue,
    save_pursuit_task, get_all_tasks, get_running_task, update_task_status
)
from crawler import sync_latest_data, catchup_to_target_issue, add_manual_draw
from plan_engine import build_pursuit_schedule, audit_running_task

# 页面基础设定
st.set_page_config(
    page_title="快乐8选五6码计划系统",
    page_icon="🎱",
    layout="wide",
    initial_sidebar_state="expanded"
)
init_db()

# 自定义响应式 CSS
st.markdown("""
<style>
    .stApp { background-color: #0b0e14; font-family: -apple-system, sans-serif; }
    .main-title {
        font-size: clamp(20px, 4.5vw, 26px);
        font-weight: 800;
        background: linear-gradient(90deg, #ffffff 0%, #00e5ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 12px;
    }
    .metric-card {
        background: #151922;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 12px 14px;
        margin-bottom: 12px;
    }
    .lotto-ball {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 38px;
        height: 38px;
        border-radius: 50%;
        color: #fff;
        font-weight: 800;
        font-size: 16px;
        margin: 3px;
        box-shadow: inset -2px -2px 5px rgba(0,0,0,0.4), 0 3px 6px rgba(0,0,0,0.4);
    }
    .ball-red { background: radial-gradient(circle at 35% 35%, #ff5252, #b71c1c); }
    .ball-blue { background: radial-gradient(circle at 35% 35%, #40c4ff, #0277bd); }
    .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
        gap: 10px;
        margin-bottom: 14px;
    }
    .kpi-box {
        background: #141822;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 10px;
        text-align: center;
    }
    .kpi-label { font-size: 11px; color: #8fa0b5; margin-bottom: 2px; }
    .kpi-val { font-size: 17px; font-weight: 800; color: #fff; }
</style>
""", unsafe_allow_html=True)

# 侧边栏：同步开奖与补录控制台
with st.sidebar:
    st.markdown("### ⚙️ 数据中心")
    
    # 一键同步
    if st.button("🔄 同步官网最新开奖", use_container_width=True, type="primary"):
        with st.spinner("正在同步..."):
            ok, msg = sync_latest_data(auto_target=2026288)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
                
    history_df = get_all_history()
    cur_issue = get_latest_issue()
    st.metric("本地最新期号", f"第 {cur_issue} 期", f"总收录 {len(history_df)} 期")
    
    st.markdown("---")
    # 增加手动录入与快速补期面板
    with st.expander("✍️ 快速追平 / 手工录入开奖"):
        st.caption("1. 快速将期数追平至最新实际期号：")
        t_iss = st.number_input("目标最新期号", value=2026288, step=1)
        if st.button("⚡ 一键追平至此期号"):
            n = catchup_to_target_issue(int(t_iss))
            st.success(f"已补入 {n} 期数据！")
            st.rerun()
            
        st.markdown("---")
        st.caption("2. 精准录入当期真实 20 码：")
        m_issue = st.text_input("期号", value=str(int(cur_issue) + 1 if str(cur_issue).isdigit() else 2026289))
        m_date = st.date_input("开奖日期", datetime.now())
        m_nums = st.text_area("20个开奖号码（空格或逗号隔开）", placeholder="如: 01 05 08 12 18 22 25 31 35 40 44 49 52 58 63 67 71 75 78 80")
        if st.button("💾 保存当期真实开奖", use_container_width=True):
            if m_nums.strip():
                ok, res_m = add_manual_draw(m_issue, str(m_date), m_nums)
                if ok:
                    st.success(res_m)
                    st.rerun()
                else:
                    st.error(res_m)
            else:
                st.warning("请填入开奖号码！")

st.markdown("<div class='main-title'>🎱 快乐8选五6码倍投追号量化系统</div>", unsafe_allow_html=True)

# 标签页划分
tab1, tab2, tab3, tab4 = st.tabs(["🎯 选号与投注计划", "📡 活跃追号监控", "📊 投入及盈亏看板", "📋 历史开奖池"])

# ----------------- TAB 1: 选号盘与计划推演 -----------------
with tab1:
    st.markdown("##### 1. 选号盘（80个号码球 · 严格每行10球）")
    
    if "selected_balls" not in st.session_state:
        st.session_state.selected_balls = set()

    btn_c1, btn_c2, _ = st.columns([1, 1, 2])
    with btn_c1:
        if st.button("🎲 随机机选 6 码", use_container_width=True):
            st.session_state.selected_balls = set(random.sample(range(1, 81), 6))
            st.rerun()
    with btn_c2:
        if st.button("🧹 清空已选号码", use_container_width=True):
            st.session_state.selected_balls = set()
            st.rerun()

    # 10球一行的选号盘布局
    for r in range(8):
        cols = st.columns(10)
        for c in range(10):
            ball_num = r * 10 + c + 1
            is_active = ball_num in st.session_state.selected_balls
            btn_label = f"🔴{ball_num:02d}" if is_active else f"{ball_num:02d}"
            if cols[c].button(btn_label, key=f"ball_{ball_num}", use_container_width=True):
                if is_active:
                    st.session_state.selected_balls.remove(ball_num)
                else:
                    if len(st.session_state.selected_balls) < 6:
                        st.session_state.selected_balls.add(ball_num)
                    else:
                        st.warning("选五6码复式只能选择 6 个号码！")
                st.rerun()

    sel_list = sorted(list(st.session_state.selected_balls))
    sel_html = "".join([f"<span class='lotto-ball ball-red'>{n:02d}</span>" for n in sel_list])
    st.markdown(f"<div style='margin:12px 0;'>当前锁定（{len(sel_list)}/6 码）：{sel_html if sel_list else '<span style=\"color:#888;\">未选号码</span>'}</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### 2. 阶梯倍投参数设置")
    
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        target_hit_opt = st.selectbox("保底设奖目标", [4, 5], format_func=lambda x: "🎯 保底中 4 码（52元）" if x == 4 else "🔥 保底中 5 码（1100元）")
    with col_p2:
        max_p = st.slider("计划追号期数", min_value=5, max_value=25, value=12)
    with col_p3:
        min_p = st.number_input("单期保底纯利润 (元)", value=30, step=10)

    plan_df = build_pursuit_schedule(max_periods=max_p, min_profit=min_p, target_hit=target_hit_opt)
    st.dataframe(plan_df, use_container_width=True, hide_index=True)

    if st.button("🚀 锁定当前 6 码，开启中奖即停实盘追号", use_container_width=True, type="primary"):
        if len(sel_list) != 6:
            st.error("请先在选号盘中选满 6 个号码！")
        else:
            nums_str = ",".join(f"{n:02d}" for n in sel_list)
            next_issue = str(int(cur_issue) + 1 if str(cur_issue).isdigit() else 2026289)
            p_name = f"选五6码方案_{next_issue}"
            save_pursuit_task(p_name, nums_str, next_issue, max_p, target_hit_opt, min_p)
            st.success(f"已创建实盘任务！起追期号: {next_issue}，中奖即停！")
            st.rerun()

# ----------------- TAB 2: 活跃追号与自动停机监控 -----------------
with tab2:
    active_task = get_running_task()
    if active_task:
        summary, audit_flow = audit_running_task(active_task, history_df)
        
        if summary and summary["status"] != "RUNNING":
            update_task_status(
                active_task["id"], summary["status"], 
                summary["total_cost"], summary["total_prize"], summary["net_profit"]
            )
            st.rerun()

        t_balls = [int(x) for x in active_task["target_numbers"].split(",")]
        t_html = "".join([f"<span class='lotto-ball ball-blue'>{n:02d}</span>" for n in t_balls])
        
        status_text = "🟢 正在监控开奖池追踪中"
        if summary["status"] == "HIT_STOP":
            status_text = "🎉 已中出目标大奖 · 自动停机止盈"
        elif summary["status"] == "EXPIRED":
            status_text = "⚠️ 达到最大追号期数 · 触发保护止损"

        st.markdown(f"""
        <div class="metric-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <b style="color:#fff; font-size:16px;">{active_task['plan_name']}</b>
                <span style="color:#00e5ff; font-weight:700;">{status_text}</span>
            </div>
            <div style="margin:8px 0;">{t_html}</div>
            <div style="font-size:12px; color:#8fa0b5;">
                起追期号: <b>{active_task['start_issue']}</b> | 目标: <b>中 {active_task['target_hit']} 码即停</b> | 计划上限: <b>{active_task['max_periods']} 期</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("已开期数", f"{summary['tracked_count']} / {active_task['max_periods']}")
        k2.metric("实投本金", f"¥ {summary['total_cost']:,.0f}")
        k3.metric("累计获得奖金", f"¥ {summary['total_prize']:,.0f}")
        k4.metric("当前净盈亏", f"¥ {summary['net_profit']:+,.0f}", delta=f"{summary['net_profit']:+} 元")

        if st.button("🛑 手动强行终止此任务"):
            update_task_status(active_task["id"], "MANUAL_STOP", summary["total_cost"], summary["total_prize"], summary["net_profit"])
            st.warning("任务已归档终止。")
            st.rerun()

        st.markdown("##### 逐期开奖对账明细流水")
        if audit_flow:
            flow_df = pd.DataFrame(audit_flow)
            st.dataframe(flow_df, use_container_width=True, hide_index=True)
        else:
            st.info("起追期号尚未开出，系统正在等待最新开奖数据更新...")
    else:
        st.info("💡 当前暂无进行中的追号任务，请在【选号与投注计划】页面选号并开启任务。")

# ----------------- TAB 3: 投入及盈亏综合看板 -----------------
with tab3:
    st.markdown("##### 📈 历史追号全盘资金看板")
    all_tasks = get_all_tasks()
    
    if not all_tasks.empty:
        total_spent = all_tasks["total_invest"].sum()
        total_won = all_tasks["total_prize"].sum()
        net_all = total_won - total_spent
        hit_stop_cnt = len(all_tasks[all_tasks["status"] == "HIT_STOP"])
        total_task_cnt = len(all_tasks)
        success_rate = (hit_stop_cnt / total_task_cnt) * 100 if total_task_cnt > 0 else 0

        st.markdown(f"""
        <div class="dashboard-grid">
            <div class="kpi-box">
                <div class="kpi-label">历史总投入</div>
                <div class="kpi-val">¥ {total_spent:,.0f}</div>
            </div>
            <div class="kpi-box">
                <div class="kpi-label">累计总奖金</div>
                <div class="kpi-val" style="color:#00e5ff;">¥ {total_won:,.0f}</div>
            </div>
            <div class="kpi-box">
                <div class="kpi-label">全盘总净利润</div>
                <div class="kpi-val" style="color:{'#00e676' if net_all >= 0 else '#ff5252'};">¥ {net_all:+,.0f}</div>
            </div>
            <div class="kpi-box">
                <div class="kpi-label">追号成功止盈率</div>
                <div class="kpi-val">{success_rate:.1f}%</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        chart_data = all_tasks.sort_values("id", ascending=True).copy()
        chart_data["累计净利润"] = chart_data["net_profit"].cumsum()
        chart_data["任务序号"] = [f"第{i+1}次计划" for i in range(len(chart_data))]
        
        fig = px.line(
            chart_data, x="任务序号", y="累计净利润",
            title="累计净利润演变曲线 (元)",
            markers=True
        )
        fig.update_traces(line_color="#00e676" if net_all >= 0 else "#ff5252")
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#ffffff"), margin=dict(l=10, r=10, t=35, b=10)
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        st.markdown("##### 全部追号历史台账")
        st.dataframe(all_tasks, use_container_width=True, hide_index=True)
    else:
        st.info("暂无历史执行计划，请开启第一笔追号！")

# ----------------- TAB 4: 历史开奖池 -----------------
with tab4:
    st.markdown("##### 📋 官网开奖历史数据库")
    if not history_df.empty:
        st.dataframe(history_df, use_container_width=True, hide_index=True, height=500)
    else:
        st.warning("暂无开奖数据，请在侧边栏点击【同步官网开奖数据】。")
