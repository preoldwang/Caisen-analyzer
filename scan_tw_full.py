#!/usr/bin/env python3
"""
全台股蔡森掃描器 — Matrix 平行版
用法: python scan_tw_full.py --chunk 1 --total 4
"""
import sys, json, os, time, argparse, urllib.request
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cai_sen_analyzer import CaiSenAnalyzer
from symbol_master import load_symbol_master, yahoo_url


def scan_stock(ticker, meta, period="1y"):
    """掃描單一股票，回傳訊號列表"""
    try:
        analyzer = CaiSenAnalyzer()
        analyzer.fetch_data(symbol=ticker, period=period)
        result = analyzer.analyze()
        signals = []
        seen = set()
        for p in result.patterns:
            framework = str(p.pattern_type.value)
            if args.framework != "ALL" and framework != args.framework:
                continue
            if p.confidence >= 0.65 and p.risk_reward_ratio >= 2.0:
                key = (ticker, framework, p.signal_date)
                if key in seen:
                    continue
                seen.add(key)
                signals.append({
                    "ticker": ticker,
                    "name": meta["name"],
                    "market": meta["market"],
                    "framework": framework,
                    "confidence": round(p.confidence, 2),
                    "entry": round(p.entry_price, 2),
                    "stop_loss": round(p.stop_loss, 2),
                    "target1": round(p.target_price, 2),
                    "target2": round(p.target_price_2, 2),
                    "rr": round(p.risk_reward_ratio, 1),
                    "neckline": round(p.neckline, 2),
                    "signal_date": p.signal_date,
                    "timeframe": getattr(p, "timeframe", "daily"),
                    "yahoo_url": yahoo_url(ticker),
                })
        return signals
    except Exception as e:
        return []

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk", type=int, default=1, help="本批次編號 (1-based)")
    parser.add_argument("--total", type=int, default=4, help="總批次數")
    parser.add_argument("--period", type=str, default="1y", help="K線資料期間：1y / 2y / 5y")
    parser.add_argument("--framework", type=str, default="ALL", help="型態框架篩選：ALL / W底 / M頭 / 頭肩底 / 頭肩頂 / 旗形 / 三角形 / 假突破 / 破底翻")
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"🔍 全台股蔡森掃描 — 批次 {args.chunk}/{args.total}")
    print(f"{'='*60}")

    # 取得全台股清單
    print("📥 載入單一標的主檔...")
    master = load_symbol_master()
    twse = {k:v for k,v in master.items() if k.endswith(".TW")}
    tpex = {k:v for k,v in master.items() if k.endswith(".TWO")}
    print(f"   上市: {len(twse)} 檔")
    print(f"   上櫃: {len(tpex)} 檔")

    all_stocks = list(master.items())
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
        "framework": args.framework,
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
