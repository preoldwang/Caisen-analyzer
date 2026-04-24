#!/usr/bin/env python3
"""
Full Cai Sen Monthly Backtest
==============================
Uses the complete cai_sen_analyzer.py (v3.0) with all 20+ pattern detectors,
multi-timeframe analysis, and signal quality filtering.

Usage:
  python backtest_full_monthly.py <start_year> <start_month> <end_year> <end_month> <output_json>

Example:
  python backtest_full_monthly.py 2021 4 2026 3 backtest_full_60m.json

For each month:
1. Fetch 5y of historical data, truncate to cutoff date
2. Run full CaiSenAnalyzer on all 84 HK blue chips
3. Score and rank by bullish signal strength
4. Pick top 2 stocks
5. Record buy/sell prices and P&L

Output JSON includes analyzer_version metadata for traceability.
"""

import sys
import os
import json
import warnings
import traceback
import time
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings('ignore')

# Import the full Cai Sen analyzer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cai_sen_analyzer import CaiSenAnalyzer, SignalType, Pattern

# ============================================================
# HK Blue Chip Universe (84 stocks)
# ============================================================
HK_STOCKS = [
    '0002.HK', '0005.HK', '0006.HK', '0012.HK', '0016.HK', '0027.HK',
    '0066.HK', '0175.HK', '0241.HK', '0267.HK', '0288.HK', '0386.HK',
    '0388.HK', '0669.HK', '0688.HK', '0700.HK', '0728.HK', '0762.HK',
    '0788.HK', '0823.HK', '0836.HK', '0857.HK', '0883.HK', '0916.HK',
    '0939.HK', '0941.HK', '0960.HK', '0968.HK', '0981.HK', '0992.HK',
    '1024.HK', '1038.HK', '1044.HK', '1088.HK', '1093.HK', '1109.HK',
    '1113.HK', '1177.HK', '1209.HK', '1211.HK', '1299.HK', '1378.HK',
    '1398.HK', '1810.HK', '1876.HK', '1880.HK', '1928.HK', '1929.HK',
    '1997.HK', '2007.HK', '2013.HK', '2015.HK', '2020.HK', '2050.HK',
    '2269.HK', '2313.HK', '2318.HK', '2319.HK', '2331.HK', '2359.HK',
    '2382.HK', '2388.HK', '2628.HK', '2688.HK', '2822.HK', '2899.HK',
    '3328.HK', '3690.HK', '3692.HK', '3968.HK', '6030.HK', '6618.HK',
    '6690.HK', '9618.HK', '9626.HK', '9633.HK', '9698.HK', '9866.HK',
    '9888.HK', '9901.HK', '9961.HK', '9988.HK', '9999.HK'
]

STOCK_NAMES = {
    '0002.HK': 'CLP Holdings', '0005.HK': 'HSBC', '0006.HK': 'Power Assets',
    '0012.HK': 'Henderson Land', '0016.HK': 'SHK Properties', '0027.HK': 'Galaxy Ent',
    '0066.HK': 'MTR Corp', '0175.HK': 'Geely Auto', '0241.HK': 'Ali Health',
    '0267.HK': 'CITIC', '0288.HK': 'WH Group', '0386.HK': 'China Petroleum',
    '0388.HK': 'HKEX', '0669.HK': 'Techtronic Ind', '0688.HK': 'China Overseas',
    '0700.HK': 'Tencent', '0728.HK': 'China Telecom', '0762.HK': 'China Unicom',
    '0788.HK': 'China Tower', '0823.HK': 'Link REIT', '0836.HK': 'China Resources Power',
    '0857.HK': 'PetroChina', '0883.HK': 'CNOOC', '0916.HK': 'Longfor Group',
    '0939.HK': 'CCB', '0941.HK': 'China Mobile', '0960.HK': 'Longfor Group',
    '0968.HK': 'Xinyi Solar', '0981.HK': 'SMIC', '0992.HK': 'Lenovo',
    '1024.HK': 'Kuaishou', '1038.HK': 'CKI Holdings', '1044.HK': "Hengan Int'l",
    '1088.HK': 'China Shenhua', '1093.HK': 'CSPC Pharma', '1109.HK': 'China Resources Land',
    '1113.HK': 'CK Asset', '1177.HK': 'Sino Biopharm', '1209.HK': 'China Resources Mixc',
    '1211.HK': 'BYD', '1299.HK': 'AIA Group', '1378.HK': 'China Hongqiao',
    '1398.HK': 'ICBC', '1810.HK': 'Xiaomi', '1876.HK': 'Budweiser APAC',
    '1880.HK': 'China Tourism Group', '1928.HK': 'Sands China', '1929.HK': 'Chow Tai Fook',
    '1997.HK': 'Wharf REIC', '2007.HK': 'Country Garden', '2013.HK': 'WuXi Biologics',
    '2015.HK': 'Li Auto', '2020.HK': 'Anta Sports', '2050.HK': 'Sanhua Intelligent',
    '2269.HK': 'WuXi Bio', '2313.HK': "Shenzhou Int'l", '2318.HK': 'Ping An',
    '2319.HK': 'Mengniu Dairy', '2331.HK': 'Li Ning', '2359.HK': 'WuXi AppTec',
    '2382.HK': 'Sunny Optical', '2388.HK': 'BOC Hong Kong', '2628.HK': 'China Life',
    '2688.HK': 'ENN Energy', '2822.HK': 'CSI 300 ETF', '2899.HK': 'Zijin Mining',
    '3328.HK': 'Bank of Communications', '3690.HK': 'Meituan', '3692.HK': 'Hansoh Pharma',
    '3968.HK': 'China Merchants Bank', '6030.HK': 'CITIC Securities', '6618.HK': 'JD Health',
    '6690.HK': 'Haier Smart Home', '9618.HK': 'JD.com', '9626.HK': 'Bilibili',
    '9633.HK': 'Nongfu Spring', '9698.HK': 'Wangsu Science', '9866.HK': 'NIO-SW',
    '9888.HK': 'Baidu', '9901.HK': 'New Oriental', '9961.HK': 'Trip.com',
    '9988.HK': 'Alibaba', '9999.HK': 'NetEase'
}

# Bullish signals that contribute to scoring
BULLISH_SIGNALS = {
    "破底翻", "W底", "头肩底", "岛型反转(底)", "量先价行",
    "颈线突破", "回踩支撑", "真突破", "底部放量突破", "V型反转",
    "量价背离(上行)", "康波上行期", "月线缩量见底", "棒康多点",
}

BEARISH_SIGNALS = {
    "假突破", "颈线跌破", "头肩顶", "M顶", "岛型反转(顶)",
    "反弹无力", "跌破支撑", "量价背离(下行)", "康波下行期",
    "月线爆量翻黑", "棒康空点", "骗线确认",
}


# ============================================================
# Trading Day Helpers
# ============================================================

def get_first_trading_day(year: int, month: int) -> Optional[date]:
    """Get the first trading day of a month for HK market."""
    start = date(year, month, 1)
    end = date(year, month, 10)
    try:
        ticker = yf.Ticker('^HSI')
        hist = ticker.history(start=str(start), end=str(end + timedelta(days=1)), auto_adjust=False)
        if len(hist) > 0:
            return hist.index[0].tz_localize(None).date()
    except Exception:
        pass
    d = start
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def get_last_trading_day(year: int, month: int) -> Optional[date]:
    """Get the last trading day of a month for HK market."""
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    start = date(year, month, max(1, end.day - 10))
    try:
        ticker = yf.Ticker('^HSI')
        hist = ticker.history(start=str(start), end=str(end + timedelta(days=1)), auto_adjust=False)
        if len(hist) > 0:
            return hist.index[-1].tz_localize(None).date()
    except Exception:
        pass
    return end


def get_stock_price_on_date(symbol: str, target_date: date) -> Optional[Dict]:
    """Get open/close price for a stock on a specific date."""
    try:
        ticker = yf.Ticker(symbol)
        start = target_date - timedelta(days=5)
        end = target_date + timedelta(days=5)
        hist = ticker.history(start=str(start), end=str(end + timedelta(days=1)), auto_adjust=False)
        if hist.empty:
            return None
        hist.index = hist.index.tz_localize(None)
        # Find closest trading day
        for delta in range(0, 6):
            for d in [target_date + timedelta(days=delta), target_date - timedelta(days=delta)]:
                if d in hist.index:
                    row = hist.loc[d]
                    return {'open': float(row['Open']), 'close': float(row['Close']),
                            'high': float(row['High']), 'low': float(row['Low']),
                            'date': str(d)}
        # Fallback: use first available
        row = hist.iloc[0]
        return {'open': float(row['Open']), 'close': float(row['Close']),
                'high': float(row['High']), 'low': float(row['Low']),
                'date': str(hist.index[0].date())}
    except Exception:
        return None


# ============================================================
# Full Cai Sen Analysis
# ============================================================

def analyze_stock_full(symbol: str, cutoff_date: date) -> Dict:
    """
    Analyze a stock using the full CaiSenAnalyzer up to cutoff_date.
    Returns a dict with score, signals, and metadata.
    """
    try:
        analyzer = CaiSenAnalyzer(lookback_months=12)

        # Fetch 5y of data
        ticker = yf.Ticker(symbol)
        end_dt = cutoff_date + timedelta(days=1)
        hist = ticker.history(start=str(cutoff_date - timedelta(days=1825)),
                              end=str(end_dt), auto_adjust=False)

        if hist.empty or len(hist) < 20:
            return {'symbol': symbol, 'score': -999, 'signals': [], 'error': 'insufficient data'}

        # Truncate to cutoff date
        hist.index = hist.index.tz_localize(None)
        hist = hist[hist.index <= pd.Timestamp(cutoff_date)]

        # SAFETY: Drop Adj Close to guarantee unadjusted raw data only
        for col in ['Adj Close', 'Dividends', 'Stock Splits']:
            if col in hist.columns:
                hist = hist.drop(columns=[col])

        if len(hist) < 20:
            return {'symbol': symbol, 'score': -999, 'signals': [], 'error': 'insufficient data before cutoff'}

        # Data quality check: reject if too many zero-volume days
        zero_vol_days = (hist['Volume'] == 0).sum()
        if zero_vol_days > len(hist) * 0.1:
            return {'symbol': symbol, 'score': -999, 'signals': [],
                    'error': f'poor data quality: {zero_vol_days}/{len(hist)} zero-volume days'}

        # Load into analyzer
        analyzer.load_data(symbol, hist)

        # Run full analysis
        result = analyzer.analyze(symbol)

        # Convert patterns to score
        score = 0
        signals = []

        for p in result.patterns:
            sig_type = p.pattern_type.value
            signal = {
                'type': sig_type,
                'description': p.description,
                'confidence': p.confidence,
                'neckline': p.neckline,
                'entry_price': p.entry_price,
                'stop_loss': p.stop_loss,
                'target_price': p.target_price,
                'target_price_2': p.target_price_2,
                'rr_ratio': p.risk_reward_ratio,
                'timeframe': p.timeframe,
                'quality': p.signal_quality,
            }
            signals.append(signal)

            # Score calculation
            if sig_type in BULLISH_SIGNALS:
                base = 3 if p.confidence >= 0.7 else 2 if p.confidence >= 0.5 else 1
                # Quality bonus
                if p.signal_quality == "基本面":
                    base += 1
                elif p.signal_quality == "呬爛面":
                    base -= 1
                # R:R bonus
                if p.risk_reward_ratio >= 3.0:
                    base += 1
                elif p.risk_reward_ratio >= 2.0:
                    base += 0.5
                # Multi-timeframe bonus
                if p.timeframe in ("weekly", "monthly"):
                    base += 1
                score += base

            elif sig_type in BEARISH_SIGNALS:
                base = 3 if p.confidence >= 0.7 else 2 if p.confidence >= 0.5 else 1
                if p.signal_quality == "基本面":
                    base += 1
                score -= base

        # Trend bonus
        if result.daily_trend == "多头":
            score += 1
        elif result.daily_trend == "空头":
            score -= 1

        if result.weekly_trend == "多头":
            score += 1
        elif result.weekly_trend == "空头":
            score -= 1

        if result.monthly_trend == "多头":
            score += 1
        elif result.monthly_trend == "空头":
            score -= 1

        # Volume-price bonus
        if result.volume_leads_price:
            score += 1
        if result.volume_price_divergence:
            score += 1

        return {
            'symbol': symbol,
            'name': STOCK_NAMES.get(symbol, symbol),
            'score': round(score, 1),
            'signals': signals,
            'signal_count': len(signals),
            'bullish_count': len([s for s in signals if s['type'] in BULLISH_SIGNALS]),
            'bearish_count': len([s for s in signals if s['type'] in BEARISH_SIGNALS]),
            'daily_trend': result.daily_trend,
            'weekly_trend': result.weekly_trend,
            'monthly_trend': result.monthly_trend,
            'kangbo_phase': result.kangbo_phase,
            'key_support': result.key_support,
            'key_resistance': result.key_resistance,
            'current_price': result.current_price,
        }

    except Exception as e:
        return {'symbol': symbol, 'score': -999, 'signals': [], 'error': str(e)}


# ============================================================
# Main Backtest Loop
# ============================================================

def month_range(start_year, start_month, end_year, end_month):
    """Generate (year, month) tuples from start to end inclusive."""
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def run_backtest(start_year, start_month, end_year, end_month, output_file):
    months = list(month_range(start_year, start_month, end_year, end_month))
    print(f"Starting FULL Cai Sen backtest: {len(months)} months "
          f"from {start_year}-{start_month:02d} to {end_year}-{end_month:02d}")
    print(f"Stocks to analyze per month: {len(HK_STOCKS)}")
    print(f"Analyzer: cai_sen_analyzer.py v3.0 (full 20+ pattern detectors)")
    print()

    results = []
    total_start = time.time()

    for i, (year, month) in enumerate(months):
        month_start = time.time()
        month_label = f"{year}-{month:02d}"
        print(f"[{i+1}/{len(months)}] Processing {month_label}...")

        first_day = get_first_trading_day(year, month)
        last_day = get_last_trading_day(year, month)
        if not first_day or not last_day:
            print(f"  SKIP: Could not determine trading days")
            continue
        print(f"  First trading day: {first_day}, Last: {last_day}")

        # Analyze all stocks
        analyses = []
        failed = 0
        for j, sym in enumerate(HK_STOCKS):
            result = analyze_stock_full(sym, first_day)
            if result['score'] > -999:
                analyses.append(result)
            else:
                failed += 1
            if (j + 1) % 20 == 0:
                print(f"    Analyzed {j+1}/{len(HK_STOCKS)}...")
            # Small delay to avoid rate limiting
            if (j + 1) % 10 == 0:
                time.sleep(0.5)

        # Sort by score descending
        analyses.sort(key=lambda x: x['score'], reverse=True)
        print(f"  Valid analyses: {len(analyses)}, Failed: {failed}")

        # Show top 5 for context
        print(f"  Top 5 scores:")
        for a in analyses[:5]:
            bullish_sigs = [s['type'] for s in a['signals'] if s['type'] in BULLISH_SIGNALS]
            print(f"    {a['symbol']:10s} {a['name']:25s} Score={a['score']:5.1f} "
                  f"Bullish={len(bullish_sigs)} Signals={','.join(bullish_sigs[:3])}")

        # Pick top 2
        top2 = analyses[:2]

        trades = []
        for pick in top2:
            buy_data = get_stock_price_on_date(pick['symbol'], first_day)
            sell_data = get_stock_price_on_date(pick['symbol'], last_day)

            if buy_data and sell_data:
                buy_price = buy_data['open']
                sell_price = sell_data['close']
                pnl_pct = round((sell_price - buy_price) / buy_price * 100, 2)

                # Build reason from bullish signals
                reason_parts = []
                for sig in pick['signals']:
                    if sig['type'] in BULLISH_SIGNALS and sig['confidence'] >= 0.5:
                        quality_tag = f" [{sig['quality']}]" if sig['quality'] != '待定' else ""
                        tf_tag = f" ({sig['timeframe']})" if sig['timeframe'] != 'daily' else ""
                        reason_parts.append(
                            f"★ {sig['type']}{tf_tag}: {sig['description'][:60]}{quality_tag}"
                        )

                trade = {
                    'symbol': pick['symbol'],
                    'name': pick['name'],
                    'buy_date': str(first_day),
                    'buy_price': buy_price,
                    'sell_date': str(last_day),
                    'sell_price': sell_price,
                    'pnl_pct': pnl_pct,
                    'score': pick['score'],
                    'signals': pick['signals'],
                    'signal_count': pick['signal_count'],
                    'bullish_count': pick['bullish_count'],
                    'bearish_count': pick['bearish_count'],
                    'daily_trend': pick['daily_trend'],
                    'weekly_trend': pick['weekly_trend'],
                    'monthly_trend': pick['monthly_trend'],
                    'kangbo_phase': pick['kangbo_phase'],
                    'reason': ' | '.join(reason_parts) if reason_parts else 'High composite score',
                }
                trades.append(trade)
                flag = '✅' if pnl_pct > 0 else '❌'
                print(f"  Pick: {pick['symbol']} ({pick['name']}) Score={pick['score']} "
                      f"| Buy@{buy_price} Sell@{sell_price} P&L={pnl_pct:+.2f}% {flag}")
            else:
                print(f"  WARNING: Could not get price data for {pick['symbol']}")

        avg_pnl = round(np.mean([t['pnl_pct'] for t in trades]), 2) if trades else 0
        month_time = time.time() - month_start
        print(f"  Month avg P&L: {avg_pnl:+.2f}% ({month_time:.0f}s)")
        print()

        entry = {
            'month': month_label,
            'first_trading_day': str(first_day),
            'last_trading_day': str(last_day),
            'trades': trades,
            'avg_pnl': avg_pnl,
            'all_analyses_count': len(analyses),
            'top2_scores': [a['score'] for a in top2],
            'top5_scores': [a['score'] for a in analyses[:5]],
        }
        results.append(entry)

    # Save results with metadata
    total_time = time.time() - total_start
    output = {
        'meta': {
            'analyzer': 'cai_sen_full_v3.0',
            'script': 'backtest_full_monthly.py',
            'generated': datetime.now().isoformat(),
            'total_months': len(results),
            'total_time_seconds': round(total_time),
            'stocks_per_month': len(HK_STOCKS),
            'data_source': 'Yahoo Finance (yfinance) — auto_adjust=False, raw unadjusted OHLCV',
            'data_notes': 'Close/Open/High/Low = raw unadjusted prices. Adj Close dropped. Volume = raw unadjusted.',
        },
        'transactions': results,
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    # Print summary
    all_trades = [t for r in results for t in r['trades']]
    if all_trades:
        pnls = [t['pnl_pct'] for t in all_trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        cum = 1.0
        for p in pnls:
            cum *= (1 + p / 100)

        print("=" * 60)
        print(f"FULL CAI SEN BACKTEST COMPLETE")
        print(f"=" * 60)
        print(f"Months: {len(results)}")
        print(f"Total trades: {len(all_trades)}")
        print(f"Win rate: {len(wins)}/{len(pnls)} ({len(wins)/len(pnls)*100:.1f}%)")
        print(f"Avg P&L/trade: {np.mean(pnls):+.2f}%")
        print(f"Cumulative: {(cum-1)*100:+.2f}%")
        print(f"Profit factor: {abs(sum(wins)/sum(losses)):.2f}x" if losses else "Profit factor: ∞")
        print(f"Best trade: {max(pnls):+.2f}%")
        print(f"Worst trade: {min(pnls):+.2f}%")
        print(f"Time: {total_time:.0f}s ({total_time/60:.1f} min)")
        print(f"Saved to: {output_file}")
    else:
        print("No trades generated!")


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: python backtest_full_monthly.py <start_year> <start_month> <end_year> <end_month> <output_json>")
        print("Example: python backtest_full_monthly.py 2021 4 2026 3 backtest_full_60m.json")
        sys.exit(1)

    start_year = int(sys.argv[1])
    start_month = int(sys.argv[2])
    end_year = int(sys.argv[3])
    end_month = int(sys.argv[4])
    output_file = sys.argv[5]

    run_backtest(start_year, start_month, end_year, end_month, output_file)
