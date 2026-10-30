import pandas as pd
import random

def calculate_ticket_reward(picked_nums, open_nums):
    """计算选五 6 码复式（6注）命中结果与收益"""
    hits = set(picked_nums).intersection(set(open_nums))
    hit_count = len(hits)
    
    if hit_count == 3:
        prize = 3 * 53 # 159元
    elif hit_count == 4:
        prize = 2 * 21 + 4 * 53 # 254元
    elif hit_count == 5:
        prize = 1 * 1000 + 5 * 21 # 1105元
    elif hit_count == 6:
        prize = 6 * 1000 # 6000元
    else:
        prize = 0
        
    return hit_count, prize

def generate_pursuit_plan(max_periods=18, min_profit=20):
    """生成阶梯倍投追号表"""
    plan = []
    accum_cost = 0
    
    for period in range(1, max_periods + 1):
        multiplier = 1
        while True:
            total_cost_temp = accum_cost + multiplier * 12
            potential_net = (multiplier * 159) - total_cost_temp
            if potential_net >= min_profit or multiplier >= 99:
                break
            multiplier += 1
            
        period_cost = multiplier * 12
        accum_cost += period_cost
        prize = multiplier * 159
        net_profit = prize - accum_cost
        
        plan.append({
            "期数": period,
            "投注倍数": multiplier,
            "当期投入(元)": period_cost,
            "累计投入(元)": accum_cost,
            "保底返奖(元)": prize,
            "保底净利(元)": net_profit
        })
    return pd.DataFrame(plan)

def audit_pursuit_tracker(task_dict, history_df, station_count=3):
    """
    对账引擎：根据锁定的任务期号和号码，扫描开奖池计算实盘流水，并记录随机分流网点
    """
    if not task_dict or history_df.empty:
        return None, pd.DataFrame()

    target_nums = [int(x.strip()) for x in task_dict["target_numbers"].split(",") if x.strip()]
    start_issue = str(task_dict["start_issue"])
    plan_df = generate_pursuit_plan(max_periods=task_dict["max_periods"], min_profit=task_dict["min_profit"])
    mult_dict = dict(zip(plan_df["期数"], plan_df["投注倍数"]))

    history_asc = history_df.sort_values("issue", ascending=True).reset_index(drop=True)
    sub_df = history_asc[history_asc["issue"] >= start_issue].copy()
    
    records = []
    total_cost = 0
    total_prize = 0
    has_hit = False

    stations = [chr(65 + i) for i in range(min(26, max(1, station_count)))]

    for idx, (_, row) in enumerate(sub_df.iterrows()):
        period_idx = idx + 1
        if period_idx > task_dict["max_periods"]:
            break
            
        mult = mult_dict.get(period_idx, 1)
        period_cost = mult * 12
        total_cost += period_cost

        open_nums = [int(x) for x in str(row["numbers"]).split(",") if x.strip()]
        hits_set = set(target_nums).intersection(set(open_nums))
        hit_count = len(hits_set)
        _, base_prize = calculate_ticket_reward(target_nums, open_nums)
        actual_prize = base_prize * mult
        total_prize += actual_prize

        if hit_count >= 3:
            has_hit = True

        # 固定种子保证同一期的网点分配一致
        rng = random.Random(int(row["issue"]) if str(row["issue"]).isdigit() else period_idx)
        assigned_station = f"网点 {rng.choice(stations)}"

        records.append({
            "已追序号": f"第 {period_idx} 期",
            "开奖期号": row["issue"],
            "分配投注站": assigned_station,
            "开奖日期": row["open_date"],
            "跟投倍数": f"{mult} 倍",
            "投入(元)": period_cost,
            "命中情况": f"中 {hit_count} 码 ({','.join(f'{n:02d}' for n in sorted(hits_set)) if hit_count else '-'})",
            "产生奖金(元)": actual_prize,
            "累计净利润(元)": total_prize - total_cost
        })
        
        if has_hit:
            break

    flow_df = pd.DataFrame(records)
    summary = {
        "tracked_periods": len(flow_df),
        "total_cost": total_cost,
        "total_prize": total_prize,
        "net_profit": total_prize - total_cost,
        "is_hit": has_hit,
        "is_expired": len(flow_df) >= task_dict["max_periods"] and not has_hit
    }
    return summary, flow_df