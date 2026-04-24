#!/usr/bin/env python3
"""
HK Blue Chip Monthly Rotation Backtest — Real Data Analysis
============================================================
For each assigned month:
1. Fetch actual OHLCV data from Yahoo Finance for all 83 HK blue chips
2. On the first trading day, score each stock using multi-factor analysis
3. Pick top 3 based on composite score
4. Record buy price (open on day 1) and sell price (close on last day)
5. Output JSON with picks, prices, dates, and reasoning

Usage: python3 analyze_months.py <start_year> <start_month> <num_months> <output_json>
"""

import sys, json, warnings, os
from datetime import date, timedelta
import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings('ignore')

HK_STOCKS = [
    '0002.HK','0005.HK','0006.HK','0012.HK','0016.HK','0027.HK',
    '0066.HK','0175.HK','0241.HK','0267.HK','0288.HK','0386.HK',
    '0388.HK','0669.HK','0688.HK','0700.HK','0728.HK','0762.HK',
    '0788.HK','0823.HK','0836.HK','0857.HK','0883.HK','0916.HK',
    '0939.HK','0941.HK','0960.HK','0968.HK','0981.HK','0992.HK',
    '1024.HK','1038.HK','1044.HK','1088.HK','1093.HK','1109.HK',
    '1113.HK','1177.HK','1209.HK','1211.HK','1299.HK','1378.HK',
    '1398.HK','1810.HK','1876.HK','1880.HK','1928.HK','1929.HK',
    '1997.HK','2007.HK','2013.HK','2015.HK','2020.HK','2050.HK',
    '2269.HK','2313.HK','2318.HK','2319.HK','2331.HK','2359.HK',
    '2382.HK','2388.HK','2628.HK','2688.HK','2822.HK','2899.HK',
    '3328.HK','3690.HK','3692.HK','3968.HK','6030.HK','6618.HK',
    '6690.HK','9618.HK','9626.HK','9633.HK','9698.HK','9866.HK',
    '9888.HK','9901.HK','9961.HK','9988.HK','9999.HK'
]

STOCK_NAMES = {
    '0002.HK':'CLP Holdings','0005.HK':'HSBC','0006.HK':'Power Assets',
    '0012.HK':'Henderson Land','0016.HK':'SHK Properties','0027.HK':'Galaxy Ent',
    '0066.HK':'MTR Corp','0175.HK':'Geely Auto','0241.HK':'Ali Health',
    '0267.HK':'CITIC','0288.HK':'WH Group','0386.HK':'China Petroleum',
    '0388.HK':'HKEX','0669.HK':'Techtronic Ind','0688.HK':'China Overseas',
    '0700.HK':'Tencent','0728.HK':'China Telecom','0762.HK':'China Unicom',
    '0788.HK':'China Tower','0823.HK':'Link REIT','0836.HK':'CR Power',
    '0857.HK':'PetroChina','0883.HK':'CNOOC','0916.HK':'Longfor Group',
    '0939.HK':'CCB','0941.HK':'China Mobile','0960.HK':'Longfor Group',
    '0968.HK':'Xinyi Solar','0981.HK':'SMIC','0992.HK':'Lenovo',
    '1024.HK':'Kuaishou','1038.HK':'CKI Holdings','1044.HK':'Hengan Intl',
    '1088.HK':'China Shenhua','1093.HK':'CSPC Pharma','1109.HK':'CR Land',
    '1113.HK':'CK Asset','1177.HK':'Sino Biopharm','1209.HK':'CR Mixc',
    '1211.HK':'BYD','1299.HK':'AIA Group','1378.HK':'China Hongqiao',
    '1398.HK':'ICBC','1810.HK':'Xiaomi','1876.HK':'Budweiser APAC',
    '1880.HK':'CTG Duty Free','1928.HK':'Sands China','1929.HK':'Chow Tai Fook',
    '1997.HK':'Wharf REIC','2007.HK':'Country Garden','2013.HK':'WuXi Biologics',
    '2015.HK':'Li Auto','2020.HK':'Anta Sports','2050.HK':'Sanhua Intelligent',
    '2269.HK':'WuXi Bio','2313.HK':'Shenzhou Intl','2318.HK':'Ping An',
    '2319.HK':'Mengniu Dairy','2331.HK':'Li Ning','2359.HK':'WuXi AppTec',
    '2382.HK':'Sunny Optical','2388.HK':'BOC HK','2628.HK':'China Life',
    '2688.HK':'ENN Energy','2822.HK':'CSI 300 ETF','2899.HK':'Zijin Mining',
    '3328.HK':'Bank of Comms','3690.HK':'Meituan','3692.HK':'Hansoh Pharma',
    '3968.HK':'CMB','6030.HK':'CITIC Securities','6618.HK':'JD Health',
    '6690.HK':'Haier Smart Home','9618.HK':'JD.com','9626.HK':'Bilibili',
    '9633.HK':'Nongfu Spring','9698.HK':'Wangsu Science','9866.HK':'NIO',
    '9888.HK':'Baidu','9901.HK':'New Oriental','9961.HK':'Trip.com',
    '9988.HK':'Alibaba','9999.HK':'NetEase'
}


def get_month_range(year, month):
    """Get first and last trading days of a month."""
    start = date(year, month, 1)
    if month == 12:
        end = date(year+1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month+1, 1) - timedelta(days=1)
    
    # Use HSI to find actual trading days
    ticker = yf.Ticker('^HSI')
    hist = ticker.history(start=str(start - timedelta(days=5)), end=str(end + timedelta(days=5)), auto_adjust=False)
    
    month_days = [d.date() for d in hist.index if d.date() >= start and d.date() <= end]
    if len(month_days) < 2:
        return None, None
    return month_days[0], month_days[-1]


def fetch_stock_data(symbol, start_date, end_date):
    """Fetch OHLCV data for a stock. Returns DataFrame or None."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=str(start_date - timedelta(days=120)), 
                             end=str(end_date + timedelta(days=5)), auto_adjust=False)
        if hist is None or len(hist) < 20:
            return None
        return hist
    except Exception:
        return None


def compute_score(df, eval_date):
    """
    Compute multi-factor score for a stock as of eval_date.
    Returns (score, reasoning_list) or (None, []).
    """
    # Get data up to eval_date
    mask = df.index.date <= eval_date
    data = df[mask].copy()
    if len(data) < 20:
        return None, []
    
    close = data['Close'].values
    volume = data['Volume'].values
    high = data['High'].values
    low = data['Low'].values
    
    score = 0.0
    reasons = []
    
    # --- 1. Momentum (30%) ---
    # Prior 20-day return (roughly 1 month)
    if len(close) >= 20:
        ret_20d = (close[-1] / close[-20] - 1) * 100
        # Score: positive momentum gets points, capped
        mom_score = min(max(ret_20d, -15), 15) / 15 * 30
        score += mom_score
        if ret_20d > 5:
            reasons.append(f"Strong momentum: +{ret_20d:.1f}% over prior 20 days")
        elif ret_20d > 0:
            reasons.append(f"Positive momentum: +{ret_20d:.1f}% over prior 20 days")
        elif ret_20d > -5:
            reasons.append(f"Slight weakness: {ret_20d:.1f}% over prior 20 days")
        else:
            reasons.append(f"Weak momentum: {ret_20d:.1f}% over prior 20 days")
    
    # --- 2. Volume trend (20%) ---
    if len(volume) >= 40:
        vol_recent = np.mean(volume[-20:])
        vol_prior = np.mean(volume[-40:-20])
        if vol_prior > 0:
            vol_ratio = vol_recent / vol_prior
            vol_score = min(max((vol_ratio - 0.5) / 1.5, 0), 1) * 20
            score += vol_score
            if vol_ratio > 1.5:
                reasons.append(f"Volume surge: {vol_ratio:.1f}x vs prior month — strong interest")
            elif vol_ratio > 1.0:
                reasons.append(f"Above-average volume: {vol_ratio:.1f}x — moderate interest")
            else:
                reasons.append(f"Below-average volume: {vol_ratio:.1f}x — declining interest")
    
    # --- 3. Trend strength (25%) ---
    ma_scores = 0
    ma5 = np.mean(close[-5:]) if len(close) >= 5 else close[-1]
    ma10 = np.mean(close[-10:]) if len(close) >= 10 else close[-1]
    ma20 = np.mean(close[-20:]) if len(close) >= 20 else close[-1]
    ma60 = np.mean(close[-60:]) if len(close) >= 60 else close[-1]
    
    price = close[-1]
    above_count = sum([price > ma for ma in [ma5, ma10, ma20, ma60]])
    ma_alignment = (ma5 > ma10 > ma20 > ma60)
    
    trend_score = (above_count / 4) * 15
    if ma_alignment:
        trend_score += 10
        reasons.append("Bullish MA alignment (MA5 > MA10 > MA20 > MA60)")
    elif above_count >= 3:
        reasons.append(f"Price above {above_count}/4 moving averages — uptrend")
    elif above_count >= 2:
        reasons.append(f"Price above {above_count}/4 moving averages — mixed")
    else:
        reasons.append(f"Price below most MAs — downtrend")
    score += trend_score
    
    # --- 4. Risk-reward (15%) ---
    if len(close) >= 20:
        recent_high = np.max(high[-20:])
        recent_low = np.min(low[-20:])
        range_pct = recent_high - recent_low
        if range_pct > 0:
            position = (price - recent_low) / range_pct
            # Better R:R when price is closer to support (lower position)
            rr_score = (1 - position) * 15
            score += rr_score
            if position < 0.3:
                reasons.append(f"Near 20-day support — favorable risk/reward")
            elif position < 0.6:
                reasons.append(f"Mid-range — balanced risk/reward")
            else:
                reasons.append(f"Near 20-day high — reduced upside room")
    
    # --- 5. Reversal signals (10%) ---
    reversal_score = 0
    
    # W-bottom detection
    if len(low) >= 20:
        lows = low[-20:]
        min1_idx = np.argmin(lows[:10])
        min2_idx = np.argmin(lows[10:]) + 10
        if abs(lows[min1_idx] - lows[min2_idx]) / lows[min1_idx] < 0.03:
            if close[-1] > max(lows[min1_idx], lows[min2_idx]) * 1.02:
                reversal_score += 5
                reasons.append("W-bottom pattern detected — bullish reversal")
    
    # Volume-price divergence (price down but volume shrinking)
    if len(close) >= 10 and len(volume) >= 10:
        price_trend = close[-1] - close[-10]
        vol_trend = np.mean(volume[-5:]) - np.mean(volume[-10:-5])
        if price_trend < 0 and vol_trend < 0:
            reversal_score += 3
            reasons.append("Bullish volume divergence (price down, volume shrinking)")
    
    # Recovery from recent low
    if len(low) >= 5:
        recent_low_5 = np.min(low[-5:])
        if price > recent_low_5 * 1.03 and close[-2] <= recent_low_5 * 1.01:
            reversal_score += 2
            reasons.append("Bouncing off recent low — potential reversal")
    
    score += min(reversal_score, 10)
    
    return round(score, 1), reasons


def analyze_month(year, month):
    """Analyze all stocks for a given month. Returns top 3 picks."""
    first_day, last_day = get_month_range(year, month)
    if first_day is None:
        return None
    
    print(f"  Trading days: {first_day} to {last_day}")
    
    results = []
    for i, sym in enumerate(HK_STOCKS):
        print(f"  [{i+1}/{len(HK_STOCKS)}] {sym}...", end=" ", flush=True)
        
        df = fetch_stock_data(sym, first_day, last_day)
        if df is None:
            print("skip (no data)")
            continue
        
        # Get buy price (open on first trading day)
        buy_mask = df.index.date >= first_day
        sell_mask = df.index.date <= last_day
        month_data = df[buy_mask & sell_mask]
        
        if len(month_data) < 2:
            print("skip (insufficient month data)")
            continue
        
        buy_price = float(month_data['Open'].iloc[0])
        sell_price = float(month_data['Close'].iloc[-1])
        buy_date_actual = month_data.index[0].date()
        sell_date_actual = month_data.index[-1].date()
        
        # Score on first trading day
        score, reasons = compute_score(df, first_day)
        if score is None:
            print("skip (insufficient history)")
            continue
        
        pnl_pct = (sell_price / buy_price - 1) * 100
        
        results.append({
            'symbol': sym,
            'name': STOCK_NAMES.get(sym, sym),
            'score': score,
            'buy_date': str(buy_date_actual),
            'buy_price': round(buy_price, 2),
            'sell_date': str(sell_date_actual),
            'sell_price': round(sell_price, 2),
            'pnl_pct': round(pnl_pct, 2),
            'reasons': reasons
        })
        print(f"score={score:.1f} P&L={pnl_pct:+.1f}%")
    
    # Sort by score descending, take top 3
    results.sort(key=lambda x: x['score'], reverse=True)
    top3 = results[:3]
    
    return {
        'month': f"{year}-{month:02d}",
        'first_trading_day': str(first_day),
        'last_trading_day': str(last_day),
        'total_stocks_analyzed': len(results),
        'trades': top3,
        'avg_pnl': round(np.mean([t['pnl_pct'] for t in top3]), 2) if top3 else 0,
        'all_scores_top10': [(r['symbol'], r['name'], r['score']) for r in results[:10]]
    }


def main():
    if len(sys.argv) != 5:
        print("Usage: python3 analyze_months.py <start_year> <start_month> <num_months> <output_json>")
        sys.exit(1)
    
    start_year = int(sys.argv[1])
    start_month = int(sys.argv[2])
    num_months = int(sys.argv[3])
    output_file = sys.argv[4]
    
    # Generate month list
    months = []
    y, m = start_year, start_month
    for _ in range(num_months):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    
    print(f"="*60)
    print(f"HK Blue Chip Monthly Rotation Backtest")
    print(f"Period: {months[0][0]}-{months[0][1]:02d} to {months[-1][0]}-{months[-1][1]:02d} ({len(months)} months)")
    print(f"="*60)
    
    all_results = []
    for y, m in months:
        print(f"\n{'='*60}")
        print(f"📅 Analyzing {y}-{m:02d}")
        print(f"{'='*60}")
        result = analyze_month(y, m)
        if result:
            all_results.append(result)
            print(f"\n  🏆 Top 3 Picks:")
            for t in result['trades']:
                emoji = "📈" if t['pnl_pct'] >= 0 else "📉"
                print(f"     {emoji} {t['symbol']} ({t['name']})")
                print(f"        Buy:  {t['buy_date']} @ {t['buy_price']}")
                print(f"        Sell: {t['sell_date']} @ {t['sell_price']}")
                print(f"        P&L:  {t['pnl_pct']:+.2f}% | Score: {t['score']}")
                print(f"        Reasons: {' | '.join(t['reasons'])}")
        else:
            print(f"  ⚠️ No data available for {y}-{m:02d}")
    
    # Save results
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📊 OVERALL SUMMARY")
    print(f"{'='*60}")
    total_trades = sum(len(r['trades']) for r in all_results)
    winners = sum(1 for r in all_results for t in r['trades'] if t['pnl_pct'] >= 0)
    losers = total_trades - winners
    all_pnls = [t['pnl_pct'] for r in all_results for t in r['trades']]
    
    print(f"Total months: {len(all_results)}")
    print(f"Total trades: {total_trades}")
    print(f"Winners: {winners} | Losers: {losers}")
    print(f"Win rate: {winners/total_trades*100:.1f}%" if total_trades > 0 else "N/A")
    print(f"Average P&L per trade: {np.mean(all_pnls):.2f}%" if all_pnls else "N/A")
    print(f"Best trade: {max(all_pnls):+.2f}%" if all_pnls else "N/A")
    print(f"Worst trade: {min(all_pnls):+.2f}%" if all_pnls else "N/A")
    
    # Monthly breakdown
    print(f"\nMonthly P&L:")
    for r in all_results:
        pnl = r['avg_pnl']
        emoji = "📈" if pnl >= 0 else "📉"
        print(f"  {emoji} {r['month']}: {pnl:+.2f}% avg (3 picks)")
    
    cumulative = sum(r['avg_pnl'] for r in all_results)
    print(f"\nCumulative (sum of monthly avg): {cumulative:+.2f}%")
    
    print(f"\n💾 Results saved to: {output_file}")


if __name__ == '__main__':
    main()
