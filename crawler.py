import requests
import pandas as pd
import json
from db_manager import get_connection

def sync_latest_data(page_size=30):
    """
    拉取官方开奖数据接口（以福彩通用公开接口规范为例）
    """
    url = f"http://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=kl8&pageNo=1&pageSize={page_size}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "http://www.cwl.gov.cn/ygfw/rqzz/kl8/"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        items = data.get("result", [])
        
        conn = get_connection()
        cursor = conn.cursor()
        
        new_count = 0
        for item in items:
            issue = item.get("code")
            open_date = item.get("date")
            # 格式化中奖号码（取前20个正选号）
            raw_nums = item.get("red", "").replace(",", " ").strip()
            num_list = sorted([int(n) for n in raw_nums.split() if n.isdigit()])
            num_str = ",".join(f"{n:02d}" for n in num_list)
            
            cursor.execute("SELECT issue FROM lottery_history WHERE issue = ?", (issue,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO lottery_history (issue, open_date, numbers) VALUES (?, ?, ?)",
                    (issue, open_date, num_str)
                )
                new_count += 1
                
        conn.commit()
        conn.close()
        return True, f"同步成功，新增 {new_count} 期开奖数据。"
    except Exception as e:
        return False, f"数据同步异常: {str(e)}"