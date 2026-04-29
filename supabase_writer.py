#!/usr/bin/env python3
"""
Supabase 寫入模組 v2
使用標準 urllib（不依賴 requests），確保 GitHub Actions 環境相容
"""
import os, json, urllib.request, urllib.error, urllib.parse
from datetime import datetime, date, timedelta

def _headers():
    key = os.environ.get("Supk", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal"
    }

def _base():
    return os.environ.get("SUP_link", "").rstrip("/")

def upsert_signals(signals, trade_date):
    base = _base()
    if not base:
        print("  [Supabase] SUP_link 未設定，跳過")
        return False

    rows = [{
        "trade_date":  trade_date,
        "ticker":      s["ticker"],
        "name":        s.get("name", ""),
        "market":      s.get("market", ""),
        "pattern":     s.get("pattern", ""),
        "confidence":  s.get("confidence", 0),
        "entry":       s.get("entry", 0),
        "stop_loss":   s.get("stop_loss", 0),
        "target1":     s.get("target1", 0),
        "target2":     s.get("target2", 0),
        "rr":          s.get("rr", 0),
        "neckline":    s.get("neckline", 0),
        "signal_date": s.get("signal_date", trade_date),
        "timeframe":   s.get("timeframe", "daily"),
        "framework":   s.get("framework", s.get("pattern", "")),
        "dedupe_key":  f"{trade_date}|{s['ticker']}|{s.get('framework', s.get('pattern', ''))}",
    } for s in signals]

    if not rows:
        print("  [Supabase] 無訊號可寫入")
        return True

    url = f"{base}/rest/v1/signals_history"
    body = json.dumps(rows).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"  [Supabase] ✅ 寫入 {len(rows)} 筆（HTTP {resp.status}）")
            return True
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  [Supabase] ❌ 寫入失敗 HTTP {e.code}: {err[:300]}")
        return False
    except Exception as e:
        print(f"  [Supabase] ❌ 寫入失敗: {e}")
        return False

def get_consecutive_days(signals, today_str):
    base = _base()
    if not base:
        return {}

    consecutive = {}
    today = datetime.strptime(today_str, "%Y-%m-%d").date()
    from_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")

    for s in signals:
        key     = f"{s['ticker']}|{s['pattern']}"
        ticker  = urllib.parse.quote(s["ticker"])
        pattern = urllib.parse.quote(s["pattern"])
        url = (f"{base}/rest/v1/signals_history"
               f"?ticker=eq.{ticker}&pattern=eq.{pattern}"
               f"&trade_date=gte.{from_date}"
               f"&order=trade_date.desc&select=trade_date")
        req = urllib.request.Request(url, headers=_headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                records = json.loads(resp.read().decode())
            dates = sorted([r["trade_date"] for r in records], reverse=True)
            count, prev = 0, today
            for d_str in dates:
                d = datetime.strptime(d_str, "%Y-%m-%d").date()
                if (prev - d).days <= 3:
                    count += 1
                    prev = d
                else:
                    break
            consecutive[key] = max(count, 1)
        except Exception:
            consecutive[key] = 1

    return consecutive

def get_history_summary(days=45):
    base = _base()
    if not base:
        return []
    from_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    url = (f"{base}/rest/v1/signals_history"
           f"?trade_date=gte.{from_date}"
           f"&order=trade_date.desc,confidence.desc"
           f"&select=trade_date,ticker,name,pattern,confidence,entry,stop_loss,target1,rr"
           f"&limit=2000")
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [Supabase] 取得歷史失敗: {e}")
        return []


def cleanup_signals_payload(records):
    seen = set()
    out = []
    for r in records:
        k = (r.get("trade_date"), r.get("ticker"), r.get("framework") or r.get("pattern"))
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def build_cleanup_sql(table="signals_history"):
    return f"DELETE FROM {table} a USING {table} b WHERE a.ctid < b.ctid AND a.trade_date = b.trade_date AND a.ticker = b.ticker AND COALESCE(a.framework,'') = COALESCE(b.framework,'');"
