#!/usr/bin/env python3
"""
Supabase 寫入模組
負責：
  1. 每日訊號寫入 signals_history 表
  2. 查詢訊號持續天數
  3. 產出歷史摘要供 history.html 使用
"""
import os, json, urllib.request, urllib.error
from datetime import datetime, date, timedelta

def get_headers():
    key = os.environ.get("Supk", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def get_base_url():
    return os.environ.get("SUP_link", "").rstrip("/")

def ensure_table():
    """建立資料表（若不存在）— 透過 Supabase REST API"""
    # 用 rpc 呼叫 SQL 建表
    url = f"{get_base_url()}/rest/v1/rpc/create_signals_table_if_not_exists"
    # 直接嘗試寫入，若表不存在再提示
    pass

def upsert_signals(signals, trade_date):
    """
    寫入今日訊號到 signals_history
    使用 upsert（ticker + pattern + date 相同則更新）
    """
    base_url = get_base_url()
    if not base_url:
        print("  [警告] SUP_link 未設定，跳過 DB 寫入")
        return False

    rows = []
    for s in signals:
        rows.append({
            "trade_date":  trade_date,
            "ticker":      s["ticker"],
            "name":        s["name"],
            "market":      s["market"],
            "pattern":     s["pattern"],
            "confidence":  s["confidence"],
            "entry":       s["entry"],
            "stop_loss":   s["stop_loss"],
            "target1":     s["target1"],
            "target2":     s["target2"],
            "rr":          s["rr"],
            "neckline":    s.get("neckline", 0),
            "signal_date": s.get("signal_date", trade_date),
            "timeframe":   s.get("timeframe", "daily"),
        })

    if not rows:
        print("  無訊號可寫入")
        return True

    url = f"{base_url}/rest/v1/signals_history"
    body = json.dumps(rows).encode("utf-8")
    headers = get_headers()
    headers["Prefer"] = "resolution=merge-duplicates,return=minimal"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"  ✅ 寫入 Supabase：{len(rows)} 筆訊號（HTTP {resp.status}）")
            return True
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  ❌ Supabase 寫入失敗 HTTP {e.code}: {err[:200]}")
        return False

def get_consecutive_days(signals, today_str):
    """
    查詢每個訊號連續出現幾天
    回傳：{ticker+pattern: consecutive_days}
    """
    base_url = get_base_url()
    if not base_url:
        return {}

    consecutive = {}
    today = datetime.strptime(today_str, "%Y-%m-%d").date()
    check_back = 20  # 最多往回查 20 個交易日

    for s in signals:
        key = f"{s['ticker']}|{s['pattern']}"
        ticker  = s["ticker"]
        pattern = s["pattern"]

        # 查詢該 ticker + pattern 最近的連續天數
        from_date = (today - timedelta(days=check_back)).strftime("%Y-%m-%d")
        url = (f"{base_url}/rest/v1/signals_history"
               f"?ticker=eq.{urllib.parse.quote(ticker)}"
               f"&pattern=eq.{urllib.parse.quote(pattern)}"
               f"&trade_date=gte.{from_date}"
               f"&order=trade_date.desc"
               f"&select=trade_date")

        req = urllib.request.Request(url, headers=get_headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                records = json.loads(resp.read().decode())
            dates = sorted([r["trade_date"] for r in records], reverse=True)

            # 計算從今天往回連續天數
            count = 0
            prev = today
            for d_str in dates:
                d = datetime.strptime(d_str, "%Y-%m-%d").date()
                diff = (prev - d).days
                if diff <= 3:  # 允許週末間隔
                    count += 1
                    prev = d
                else:
                    break
            consecutive[key] = count
        except Exception:
            consecutive[key] = 1

    return consecutive

def get_history_summary(days=30):
    """取得最近 N 天的歷史摘要（給 history.html 用）"""
    base_url = get_base_url()
    if not base_url:
        return []

    from_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    url = (f"{base_url}/rest/v1/signals_history"
           f"?trade_date=gte.{from_date}"
           f"&order=trade_date.desc,confidence.desc"
           f"&select=trade_date,ticker,name,pattern,confidence,entry,stop_loss,target1,rr")

    req = urllib.request.Request(url, headers=get_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [警告] 取得歷史資料失敗: {e}")
        return []

import urllib.parse

if __name__ == "__main__":
    print("Supabase 連線測試...")
    base_url = get_base_url()
    if base_url:
        print(f"  URL: {base_url}")
        print("  ✅ 設定正常")
    else:
        print("  ❌ SUP_link 未設定")
