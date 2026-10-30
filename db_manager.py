import sqlite3
import pandas as pd
from datetime import datetime

DB_FILE = "happy8_data.db"

def get_connection():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    # 历史开奖池
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lottery_history (
            issue TEXT PRIMARY KEY,
            open_date TEXT,
            numbers TEXT
        )
    ''')
    # 实盘追号任务追踪表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_pursuit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_numbers TEXT,      -- 锁定的6个号码，逗号分隔
            start_issue TEXT,         -- 起始追号期号
            max_periods INTEGER,      -- 计划最大期数（如18）
            min_profit REAL,          -- 设定的每期保底微利（如20）
            status TEXT,              -- 'RUNNING', 'HIT_STOP', 'STOPPED'
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_lottery_data(df: pd.DataFrame):
    conn = get_connection()
    df.to_sql('lottery_history', conn, if_exists='append', index=False)
    conn.close()

def get_all_history():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM lottery_history ORDER BY issue DESC", conn)
    conn.close()
    return df

def get_active_pursuit_task():
    """获取当前生效中的追号任务"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, target_numbers, start_issue, max_periods, min_profit, status, created_at FROM active_pursuit WHERE status = 'RUNNING' ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "target_numbers": row[1],
            "start_issue": row[2],
            "max_periods": row[3],
            "min_profit": row[4],
            "status": row[5],
            "created_at": row[6]
        }
    return None

def create_pursuit_task(target_nums_str, start_issue, max_periods=18, min_profit=20):
    """创建并锁定一个新的追号任务（同时停用以往未闭环任务）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE active_pursuit SET status = 'STOPPED' WHERE status = 'RUNNING'")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO active_pursuit (target_numbers, start_issue, max_periods, min_profit, status, created_at)
        VALUES (?, ?, ?, ?, 'RUNNING', ?)
    ''', (target_nums_str, start_issue, max_periods, min_profit, now_str))
    conn.commit()
    conn.close()

def update_pursuit_status(task_id, new_status):
    """更新任务状态（如 HIT_STOP 止盈或 STOPPED 手工终止）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE active_pursuit SET status = ? WHERE id = ?", (new_status, task_id))
    conn.commit()
    conn.close()