#!/usr/bin/env python3
"""
台股標的主檔（單一來源 + 快取）
"""
import json, urllib.request, os
from datetime import datetime

HEADERS = {"User-Agent": "Mozilla/5.0"}
CACHE = os.path.join(os.path.dirname(__file__), "symbol_master.json")


def _load_json(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def fetch_twse_stocks():
    data = _load_json("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL")
    stocks = {}
    for s in data:
        code = s.get("Code", "")
        name = s.get("Name", "")
        vol = float(s.get("TradeVolume", "0") or 0)
        if code.isdigit() and len(code) == 4 and not code.startswith("00") and vol > 0:
            stocks[f"{code}.TW"] = {"name": name, "market": "上市", "source": "TWSE"}
    return stocks


def fetch_tpex_stocks():
    try:
        data = _load_json("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes")
    except Exception:
        return {}
    stocks = {}
    for s in data:
        code = s.get("SecuritiesCompanyCode", "")
        name = s.get("CompanyName", "")
        vol = float(s.get("TradingShares", "0").replace(",", "") or 0)
        if code.isdigit() and len(code) == 4 and not code.startswith("00") and vol > 0:
            stocks[f"{code}.TWO"] = {"name": name, "market": "上櫃", "source": "TPEX"}
    return stocks


def load_symbol_master(force_refresh=False):
    if not force_refresh and os.path.exists(CACHE):
        try:
            with open(CACHE, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if payload.get("date"):
                return payload["data"]
        except Exception:
            pass
    twse = fetch_twse_stocks()
    tpex = fetch_tpex_stocks()
    master = dict(sorted({**twse, **tpex}.items(), key=lambda x: x[0]))
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump({"date": datetime.now().strftime("%Y-%m-%d"), "data": master}, f, ensure_ascii=False)
    return master


def yahoo_url(ticker):
    return f"https://tw.stock.yahoo.com/quote/{ticker}"
