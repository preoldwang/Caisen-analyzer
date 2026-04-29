#!/usr/bin/env python3
"""
台股標的主檔（單一來源）
- 統一上市/上櫃代碼與 Yahoo 連結
- 提供給掃描、回測、報告共用
"""
import json, urllib.request

HEADERS = {"User-Agent": "Mozilla/5.0"}

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


def load_symbol_master():
    twse = fetch_twse_stocks()
    tpex = fetch_tpex_stocks()
    master = {**twse, **tpex}
    return dict(sorted(master.items(), key=lambda x: x[0]))


def yahoo_url(ticker):
    return f"https://tw.stock.yahoo.com/quote/{ticker}"
