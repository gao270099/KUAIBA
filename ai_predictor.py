import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from db_manager import get_all_history
from pursuit_calculator import calculate_ticket_reward

def parse_full_matrix(df: pd.DataFrame):
    """将开奖历史（按期号升序）转换为 0-1 矩阵 (N期 x 80号)"""
    df_sorted = df.copy().sort_values("issue", ascending=True).reset_index(drop=True)
    n_rows = len(df_sorted)
    matrix = np.zeros((n_rows, 80), dtype=int)
    
    for i, row in df_sorted.iterrows():
        nums = [int(x) for x in str(row["numbers"]).split(",") if x.strip()]
        for n in nums:
            if 1 <= n <= 80:
                matrix[i, n - 1] = 1
                
    return df_sorted, matrix

def extract_advanced_features(matrix_slice: np.ndarray):
    """提取 80 个号码的时序特征：短期加权、中期频次、遗漏值、动量斜率"""
    total_len = len(matrix_slice)
    features = np.zeros((80, 4))
    
    w5_len = min(5, total_len)
    w5 = np.linspace(0.5, 1.0, w5_len)
    features[:, 0] = np.dot(w5, matrix_slice[-w5_len:, :])
    
    w20 = min(20, total_len)
    features[:, 1] = matrix_slice[-w20:, :].sum(axis=0)
    
    for num_idx in range(80):
        col = matrix_slice[:, num_idx]
        hit_indices = np.where(col == 1)[0]
        if len(hit_indices) == 0:
            features[num_idx, 2] = total_len
        else:
            features[num_idx, 2] = total_len - 1 - hit_indices[-1]
            
    if total_len >= 15:
        p1 = matrix_slice[-5:, :].sum(axis=0)
        p2 = matrix_slice[-10:-5, :].sum(axis=0)
        features[:, 3] = p1 - p2
        
    return features

def is_valid_shape(comb):
    """组合形态学软约束校验"""
    odd_count = sum(1 for x in comb if x % 2 != 0)
    if odd_count < 1 or odd_count > 5:
        return False
    span = max(comb) - min(comb)
    if span < 25:
        return False
    s = sum(comb)
    if s < 130 or s > 350:
        return False
    return True

def run_model_on_slice(matrix_slice: np.ndarray, strategy="ADVANCED_ENSEMBLE", n_select=6):
    """针对历史截面预测下一期 6 码，保证任何分支绝不返回 None"""
    total_len = len(matrix_slice)
    # 历史样本过少时的保底
    if total_len < 25:
        np.random.seed(42 + total_len)
        return sorted([int(x) for x in np.random.choice(range(1, 81), n_select, replace=False)])
    
    # 策略 1: 3热2温1冷
    if strategy == "HOT_COLD":
        window = min(30, total_len)
        freq = matrix_slice[-window:].sum(axis=0)
        hot_pool = np.argsort(freq)[-20:] + 1
        cold_pool = np.argsort(freq)[:20] + 1
        warm_pool = np.argsort(freq)[20:60] + 1
        
        np.random.seed(42 + total_len)
        pick_hot = list(np.random.choice(hot_pool, 3, replace=False))
        pick_warm = list(np.random.choice(warm_pool, 2, replace=False))
        pick_cold = list(np.random.choice(cold_pool, 1, replace=False))
        return sorted([int(x) for x in (pick_hot + pick_warm + pick_cold)])

    # 策略 2: RandomForest 基础模型
    elif strategy == "ML_HYBRID":
        lookback = 4
        X, Y = [], []
        start_idx = max(lookback, total_len - 50)
        for i in range(start_idx, total_len):
            X.append(matrix_slice[i - lookback:i].flatten())
            Y.append(matrix_slice[i])
        clf = ExtraTreesClassifier(n_estimators=40, random_state=42, n_jobs=-1)
        clf.fit(np.array(X), np.array(Y))
        X_curr = matrix_slice[-lookback:].flatten().reshape(1, -1)
        preds = clf.predict_proba(X_curr)
        prob_scores = np.array([p[0, 1] if p.shape[1] > 1 else p[0, 0] for p in preds])
        return sorted([int(idx + 1) for idx in np.argsort(prob_scores)[-n_select:]])

    # 策略 3: 多因子特征 + ExtraTrees 多核并行集成模型
    else:
        feat = extract_advanced_features(matrix_slice)
        
        # 统计得分
        freq_30 = matrix_slice[-min(30, total_len):].sum(axis=0)
        stat_score = (freq_30 - freq_30.min()) / (freq_30.max() - freq_30.min() + 1e-6)
        
        # 遗漏回补因子
        omission = feat[:, 2]
        rebound_score = np.where((omission >= 3) & (omission <= 15), 1.2, 0.8)
        
        # 时序动量 ExtraTrees
        lookback = 5
        X, Y = [], []
        start_idx = max(lookback, total_len - 60)
        for i in range(start_idx, total_len):
            X.append(matrix_slice[i - lookback:i].flatten())
            Y.append(matrix_slice[i])
            
        clf = ExtraTreesClassifier(n_estimators=80, max_depth=12, random_state=42 + total_len, n_jobs=-1)
        clf.fit(np.array(X), np.array(Y))
        preds = clf.predict_proba(matrix_slice[-lookback:].flatten().reshape(1, -1))
        ml_score = np.array([p[0, 1] if p.shape[1] > 1 else 0 for p in preds])
        
        # 综合打分
        final_scores = (stat_score * 0.35) + (ml_score * 0.45) + (rebound_score * 0.20)
        
        # 挑选 Top 18 构成候选池
        top_candidates = np.argsort(final_scores)[-18:] + 1
        
        # 带有形态过滤的组合搜寻
        np.random.seed(99 + total_len)
        for _ in range(300):
            sample = sorted([int(x) for x in np.random.choice(top_candidates, n_select, replace=False)])
            if is_valid_shape(sample):
                return sample
                
        # 若形态过滤未命中，确定兜底返回打分最高的前 6 个号码，杜绝返回 None
        return sorted([int(idx + 1) for idx in np.argsort(final_scores)[-n_select:]])

def predict_smart_combination(n_select=6, strategy="ADVANCED_ENSEMBLE"):
    """最新一期实时预测"""
    df = get_all_history()
    if len(df) < 25:
        return [1, 2, 3, 4, 5, 6], "历史开奖数据不足，请在侧边栏同步数据。"
        
    df_sorted, matrix = parse_full_matrix(df)
    chosen = run_model_on_slice(matrix, strategy=strategy, n_select=n_select)
    
    # 强制防守检查，确保 chosen 是合规的 6 个整数列表
    if not chosen or len(chosen) != n_select:
        chosen = sorted([int(x) for x in np.random.choice(range(1, 81), n_select, replace=False)])
        
    desc_map = {
        "ADVANCED_ENSEMBLE": "⚡ 多因子特征工程 + ExtraTrees 多核集成 + 形态学过滤",
        "HOT_COLD": "🔥 3热2温1冷 遗漏频次分布模型",
        "ML_HYBRID": "🌲 RandomForest 基础机器学习模型"
    }
    return chosen, desc_map.get(strategy, "自定义模型")

def backtest_strategy_rolling(strategy="ADVANCED_ENSEMBLE", test_periods=30):
    df = get_all_history()
    total_records = len(df)
    if total_records < 20:
        return pd.DataFrame(), "历史数据池期数少于 20 期，无法进行回测，请先同步开奖数据！"
    
    df_sorted, matrix = parse_full_matrix(df)
    # 动态适应自定义输入的任意期数
    actual_test_len = min(int(test_periods), max(1, total_records - 15))
    start_test_idx = len(df_sorted) - actual_test_len
    
    results = []
    for idx in range(start_test_idx, len(df_sorted)):
        target_row = df_sorted.iloc[idx]
        target_issue = target_row["issue"]
        target_date = target_row["open_date"]
        actual_open_nums = [int(x) for x in str(target_row["numbers"]).split(",") if x.strip()]
        
        history_slice = matrix[:idx]
        pred_nums = run_model_on_slice(history_slice, strategy=strategy, n_select=6)
        if not pred_nums or len(pred_nums) != 6:
            pred_nums = [1, 2, 3, 4, 5, 6]
        
        hits_set = set(pred_nums).intersection(set(actual_open_nums))
        hit_count = len(hits_set)
        _, prize = calculate_ticket_reward(pred_nums, actual_open_nums)
        
        cost = 12
        net_profit = prize - cost
        
        results.append({
            "期号": target_issue,
            "开奖日期": target_date,
            "预测6码": ",".join(f"{n:02d}" for n in pred_nums),
            "开奖20码": target_row["numbers"],
            "命中注数": f"中 {hit_count} 码",
            "命中号码": ",".join(f"{n:02d}" for n in sorted(list(hits_set))) if hit_count > 0 else "-",
            "投注成本(元)": cost,
            "获得奖金(元)": prize,
            "当期盈亏(元)": net_profit
        })
        
    res_df = pd.DataFrame(results).sort_values("期号", ascending=False).reset_index(drop=True)
    return res_df, ""