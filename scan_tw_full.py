#!/usr/bin/env python3
"""
全台股蔡森掃描器 — Matrix 平行版
用法: python scan_tw_full.py --chunk 1 --total 4
"""
import sys, json, os, time, argparse, urllib.request
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cai_sen_analyzer import CaiSenAnalyzer

def fetch_twse_stocks():
    """從 TWSE OpenAPI 取得上市股票清單"""
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    stocks = {}
    for s in data:
        code = s.get("Code", "")
        name = s.get("Name", "")
        vol  = float(s.get("TradeVolume", "0") or 0)
        # 純4碼股票，排除ETF(00開頭)，需有成交量
        if code.isdigit() and len(code) == 4 and not code.startswith("00") and vol > 0:
            stocks[f"{code}.TW"] = name
    return stocks

def fetch_tpex_stocks():
    """從 TPEX OpenAPI 取得上櫃股票清單"""
    url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        stocks = {}
        for s in data:
            code = s.get("SecuritiesCompanyCode", "")
            name = s.get("CompanyName", "")
            vol  = float(s.get("TradingShares", "0").replace(",", "") or 0)
            if code.isdigit() and len(code) == 4 and not code.startswith("00") and vol > 0:
                stocks[f"{code}.TWO"] = name
        return stocks
    except Exception as e:
        print(f"  [警告] TPEX 取得失敗: {e}")
        return {}

def scan_stock(ticker, name, period="1y"):
    """掃描單一股票，回傳訊號列表"""
    try:
        analyzer = CaiSenAnalyzer()
        analyzer.fetch_data(symbol=ticker, period=period)
        result = analyzer.analyze()
        signals = []
        for p in result.patterns:
            if p.confidence >= 0.65 and p.risk_reward_ratio >= 2.0:
                signals.append({
                    "ticker": ticker,
                    "name": name,
                    "market": "上市" if ticker.endswith(".TW") else "上櫃",
                    "pattern": p.pattern_type.value,
                    "confidence": round(p.confidence, 2),
                    "entry": round(p.entry_price, 2),
                    "stop_loss": round(p.stop_loss, 2),
                    "target1": round(p.target_price, 2),
                    "target2": round(p.target_price_2, 2),
                    "rr": round(p.risk_reward_ratio, 1),
                    "neckline": round(p.neckline, 2),
                    "signal_date": p.signal_date,
                    "timeframe": getattr(p, "timeframe", "daily"),
                })
        return signals
    except Exception as e:
        return []

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk", type=int, default=1, help="本批次編號 (1-based)")
    parser.add_argument("--total", type=int, default=4, help="總批次數")
    parser.add_argument("--period", type=str, default="1y", help="K線資料期間：1y / 2y / 5y")
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"🔍 全台股蔡森掃描 — 批次 {args.chunk}/{args.total}")
    print(f"{'='*60}")

    # 取得全台股清單
    print("📥 取得上市股票清單 (TWSE)...")
    twse = fetch_twse_stocks()
    print(f"   上市: {len(twse)} 檔")

    print("📥 取得上櫃股票清單 (TPEX)...")
    tpex = fetch_tpex_stocks()
    print(f"   上櫃: {len(tpex)} 檔")

    all_stocks = list({**twse, **tpex}.items())
    all_stocks.sort(key=lambda x: x[0])
    total_count = len(all_stocks)

    # 切分本批次
    chunk_size = (total_count + args.total - 1) // args.total
    start = (args.chunk - 1) * chunk_size
    end   = min(start + chunk_size, total_count)
    my_stocks = all_stocks[start:end]

    print(f"\n📊 本批次: {start+1}–{end} 共 {len(my_stocks)} 檔（全市場 {total_count} 檔）")
    print(f"{'─'*60}")

    all_signals = []
    for i, (ticker, name) in enumerate(my_stocks, 1):
        signals = scan_stock(ticker, name, period=args.period)
        if signals:
            all_signals.extend(signals)
            for s in signals:
                print(f"  ✅ [{i:4d}/{len(my_stocks)}] {name}({ticker}) {s['pattern']} 信心:{s['confidence']*100:.0f}% R:R={s['rr']}")
        else:
            if i % 50 == 0:
                print(f"  ⏳ [{i:4d}/{len(my_stocks)}] 掃描中...")

        # Rate limit 保護：每100檔暫停2秒
        if i % 100 == 0:
            time.sleep(2)

    all_signals.sort(key=lambda x: x["confidence"], reverse=True)

    output = {
        "chunk": args.chunk,
        "total_chunks": args.total,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "scanned": len(my_stocks),
        "signal_count": len(all_signals),
        "signals": all_signals
    }

    period_tag = f"_{args.period}" if args.period != "1y" else ""
    out_path = f"signals_chunk_{args.chunk}{period_tag}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 批次 {args.chunk} 完成：{len(all_signals)} 個訊號 → {out_path}")

if __name__ == "__main__":
    main()
