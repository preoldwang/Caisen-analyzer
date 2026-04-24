#!/usr/bin/env python3
"""
60-Month HK Blue Chip Backtest
==============================
Usage: python backtest_60m_chunk.py <start_year> <start_month> <end_year> <end_month> <output_json>

For each month in the range:
1. Fetch 2 years of historical data up to the first trading day
2. Run technical analysis (Cai Sen methodology) on all 84 HK blue chips
3. Rank and pick the top 2 stocks
4. Record buy price (open on first trading day) and sell price (close on last trading day)
5. Output JSON with full transaction details and reasoning
"""

import sys
import os
import json
import warnings
import traceback
from datetime import datetime, timedelta, date
from typing import List, Dict, Tuple, Optional

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings('ignore')

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


# ============================================================
# Data Fetching
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
    start = end - timedelta(days=5)
    try:
        ticker = yf.Ticker('^HSI')
        hist = ticker.history(start=str(start), end=str(end + timedelta(days=1)), auto_adjust=False)
        if len(hist) > 0:
            return hist.index[-1].tz_localize(None).date()
    except Exception:
        pass
    d = end
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def get_stock_price_on_date(symbol: str, target_date: date) -> Optional[Dict]:
    """Get OHLCV data for a specific date."""
    try:
        ticker = yf.Ticker(symbol)
        start = target_date - timedelta(days=5)
        end = target_date + timedelta(days=5)
        hist = ticker.history(start=str(start), end=str(end + timedelta(days=1)), auto_adjust=False)
        if hist.empty:
            return None
        hist.index = hist.index.tz_localize(None)
        target_dt = pd.Timestamp(target_date)
        if target_dt in hist.index:
            row = hist.loc[target_dt]
        else:
            idx = hist.index.get_indexer([target_dt], method='nearest')[0]
            row = hist.iloc[idx]
        return {
            'date': str(hist.index[hist.index.get_loc(row.name)].date()),
            'open': round(float(row['Open']), 4),
            'high': round(float(row['High']), 4),
            'low': round(float(row['Low']), 4),
            'close': round(float(row['Close']), 4),
            'volume': int(row['Volume'])
        }
    except Exception:
        return None


# ============================================================
# Technical Analysis Scoring
# ============================================================

def analyze_stock_at_date(symbol: str, as_of_date: date) -> Dict:
    """
    Analyze a stock using Cai Sen methodology up to a given date.
    Returns a score and signal details.
    """
    try:
        ticker = yf.Ticker(symbol)
        end_dt = as_of_date + timedelta(days=1)
        start_dt = as_of_date - timedelta(days=730)
        hist = ticker.history(start=str(start_dt), end=str(end_dt), auto_adjust=False)

        if hist.empty or len(hist) < 20:
            return {'symbol': symbol, 'score': -999, 'signals': [], 'error': 'insufficient data'}

        hist.index = hist.index.tz_localize(None)
        close = hist['Close'].values
        volume = hist['Volume'].values
        high = hist['High'].values
        low = hist['Low'].values
        open_price = hist['Open'].values
        n = len(close)

        # Moving averages
        ma5 = np.mean(close[-5:]) if n >= 5 else close[-1]
        ma10 = np.mean(close[-10:]) if n >= 10 else close[-1]
        ma20 = np.mean(close[-20:]) if n >= 20 else close[-1]
        ma60 = np.mean(close[-60:]) if n >= 60 else close[-1]
        ma120 = np.mean(close[-120:]) if n >= 120 else close[-1]
        ma250 = np.mean(close[-250:]) if n >= 250 else close[-1]

        current_price = close[-1]
        current_vol = volume[-1] if volume[-1] > 0 else 1
        avg_vol_20 = np.mean(volume[-20:]) if n >= 20 else np.mean(volume)
        vol_ratio = current_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0

        score = 0
        signals = []

        # --- 1. Trend Analysis (max +6) ---
        if current_price > ma20 > ma60:
            score += 2
            signals.append({'type': '趋势多头', 'description': f'价格({current_price:.2f}) > MA20({ma20:.2f}) > MA60({ma60:.2f})', 'confidence': 0.7})
        elif current_price < ma20 < ma60:
            score -= 2
            signals.append({'type': '趋势空头', 'description': f'价格({current_price:.2f}) < MA20({ma20:.2f}) < MA60({ma60:.2f})', 'confidence': 0.7})

        if n >= 120 and ma20 > ma60 > ma120:
            score += 2
            signals.append({'type': '均线多头排列', 'description': 'MA20 > MA60 > MA120', 'confidence': 0.8})

        if n >= 250 and current_price > ma250:
            score += 1
            signals.append({'type': '年线上方', 'description': f'价格在250日线上方', 'confidence': 0.6})
        elif n >= 250 and current_price < ma250:
            score -= 1

        if current_price > ma5 > ma10 > ma20:
            score += 1
            signals.append({'type': '短期均线多头', 'description': 'MA5 > MA10 > MA20', 'confidence': 0.6})

        # --- 2. Volume Analysis (max +3) ---
        if vol_ratio > 1.5 and close[-1] > close[-2]:
            score += 2
            signals.append({'type': '放量上涨', 'description': f'成交量是20日均量的{vol_ratio:.1f}倍', 'confidence': 0.7})
        elif vol_ratio > 2.0:
            score += 1
            signals.append({'type': '异常放量', 'description': f'成交量是20日均量的{vol_ratio:.1f}倍', 'confidence': 0.6})

        # Volume-price divergence
        if n >= 10:
            price_trend = close[-1] - close[-10]
            vol_trend = np.mean(volume[-5:]) - np.mean(volume[-10:-5])
            if price_trend < 0 and vol_trend > 0 and vol_ratio > 1.3:
                score += 1
                signals.append({'type': '量价背离(上行)', 'description': '价格下跌但成交量萎缩，可能见底', 'confidence': 0.6})

        # --- 3. Support/Resistance (max +3) ---
        if n >= 20:
            recent_low = np.min(low[-20:])
            if current_price <= recent_low * 1.03:
                score += 1
                signals.append({'type': '接近支撑', 'description': f'接近20日低点{recent_low:.2f}', 'confidence': 0.6})

        if n >= 60:
            low_60 = np.min(low[-60:])
            if current_price <= low_60 * 1.05:
                score += 1
                signals.append({'type': '接近中期支撑', 'description': f'接近60日低点{low_60:.2f}', 'confidence': 0.5})

        # Breakout detection
        if n >= 20:
            high_20 = np.max(high[-20:-1])
            if current_price > high_20:
                score += 2
                signals.append({'type': '突破20日高点', 'description': f'突破前高{high_20:.2f}', 'confidence': 0.7})

        # --- 4. Pattern Detection (max +4) ---
        # W Bottom detection
        if n >= 40:
            for lookback in [40, 60]:
                if n < lookback:
                    continue
                seg = close[-lookback:]
                seg_low = low[-lookback:]
                min_price = np.min(seg_low)
                min_idx = np.argmin(seg_low)

                if 5 < min_idx < len(seg) - 5:
                    # Check for two bottoms
                    first_half = seg_low[:min_idx]
                    second_half = seg_low[min_idx:]
                    if len(first_half) > 5 and len(second_half) > 5:
                        first_min = np.min(first_half)
                        second_min = min_price
                        if abs(first_min - second_min) / first_min < 0.03:
                            neckline = np.max(high[-lookback:][min_idx:])
                            if current_price > neckline * 0.98:
                                score += 3
                                signals.append({
                                    'type': 'W底',
                                    'description': f'W底形态，两底{first_min:.2f}/{second_min:.2f}，颈线{neckline:.2f}',
                                    'confidence': 0.75,
                                    'neckline': round(neckline, 2)
                                })

        # Bottom reversal (破底翻)
        if n >= 60:
            for lookback in [40, 60, 90]:
                if n < lookback + 10:
                    continue
                seg = close[-lookback-10:-10]
                seg_low = low[-lookback-10:-10]
                min_price = np.min(seg_low)
                min_idx = np.argmin(seg_low)
                if 5 < min_idx < len(seg) - 5:
                    recovery = np.max(high[-lookback-10:][min_idx:])
                    recent_low = np.min(low[-10:])
                    if recent_low < min_price * 0.985 and close[-1] > min_price:
                        score += 3
                        signals.append({
                            'type': '破底翻',
                            'description': f'跌破{min_price:.2f}后收回，可能反转',
                            'confidence': 0.7,
                            'neckline': round(recovery, 2)
                        })

        # Neckline breakout
        if n >= 30:
            recent_high = np.max(high[-30:])
            if current_price > recent_high * 0.99 and vol_ratio > 1.2:
                score += 2
                signals.append({
                    'type': '颈线突破',
                    'description': f'突破30日高点{recent_high:.2f}，成交量确认',
                    'confidence': 0.7,
                    'neckline': round(recent_high, 2)
                })

        # M Top detection
        if n >= 40:
            for lookback in [40, 60]:
                if n < lookback:
                    continue
                seg_high = high[-lookback:]
                max_price = np.max(seg_high)
                max_idx = np.argmax(seg_high)
                if 5 < max_idx < len(seg) - 5:
                    first_half = seg_high[:max_idx]
                    second_half = seg_high[max_idx:]
                    if len(first_half) > 5 and len(second_half) > 5:
                        first_max = np.max(first_half)
                        second_max = max_price
                        if abs(first_max - second_max) / first_max < 0.03:
                            neckline = np.min(low[-lookback:][max_idx:])
                            if current_price < neckline * 1.02:
                                score -= 3
                                signals.append({
                                    'type': 'M顶',
                                    'description': f'M顶形态，两顶{first_max:.2f}/{second_max:.2f}，颈线{neckline:.2f}',
                                    'confidence': 0.7
                                })

        # --- 5. Momentum (max +2) ---
        if n >= 14:
            deltas = np.diff(close[-15:])
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses) if np.mean(losses) > 0 else 1e-10
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            if 30 < rsi < 50:
                score += 1
                signals.append({'type': 'RSI超卖回升', 'description': f'RSI={rsi:.1f}，从超卖区回升', 'confidence': 0.6})
            elif rsi > 70:
                score -= 1
                signals.append({'type': 'RSI超买', 'description': f'RSI={rsi:.1f}，超买', 'confidence': 0.6})

        # --- 6. Risk-Reward (max +1) ---
        if n >= 20:
            support = np.min(low[-20:])
            resistance = np.max(high[-20:])
            risk = current_price - support
            reward = resistance - current_price
            if risk > 0:
                rr = reward / risk
                if rr >= 2.0:
                    score += 1
                    signals.append({'type': '风险回报比佳', 'description': f'R:R = {rr:.1f}:1', 'confidence': 0.6})

        # MACD
        if n >= 35:
            s = pd.Series(close)
            ema12 = s.ewm(span=12, adjust=False).mean()
            ema26 = s.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            if macd_line.iloc[-1] > signal_line.iloc[-1] and macd_line.iloc[-2] <= signal_line.iloc[-2]:
                score += 1
                signals.append({'type': 'MACD金叉', 'description': 'MACD线上穿信号线', 'confidence': 0.6})

        return {
            'symbol': symbol,
            'name': STOCK_NAMES.get(symbol, symbol),
            'score': score,
            'signals': signals,
            'signal_count': len(signals),
            'vol_ratio': round(vol_ratio, 2),
            'current_price': round(current_price, 4),
            'ma20': round(ma20, 4),
            'ma60': round(ma60, 4)
        }

    except Exception as e:
        return {'symbol': symbol, 'score': -999, 'signals': [], 'error': str(e)}


# ============================================================
# Main Backtest Loop
# ============================================================

def run_backtest(start_year: int, start_month: int, end_year: int, end_month: int, output_file: str):
    """Run monthly backtest for the given range."""
    results = []

    # Generate month list
    months = []
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    total = len(months)
    print(f"Starting backtest: {total} months from {start_year}-{start_month:02d} to {end_year}-{end_month:02d}")
    print(f"Stocks to analyze per month: {len(HK_STOCKS)}")
    print()

    for idx, (year, month) in enumerate(months):
        month_label = f"{year}-{month:02d}"
        print(f"[{idx+1}/{total}] Processing {month_label}...")

        first_day = get_first_trading_day(year, month)
        last_day = get_last_trading_day(year, month)

        if not first_day or not last_day:
            print(f"  Skipping {month_label}: could not determine trading days")
            continue

        print(f"  First trading day: {first_day}, Last: {last_day}")

        # Analyze all stocks
        analyses = []
        failed = 0
        for sym in HK_STOCKS:
            result = analyze_stock_at_date(sym, first_day)
            if result['score'] > -999:
                analyses.append(result)
            else:
                failed += 1
            if (len(analyses) + failed) % 20 == 0:
                print(f"    Analyzed {len(analyses) + failed}/{len(HK_STOCKS)}...")

        # Sort by score descending
        analyses.sort(key=lambda x: x['score'], reverse=True)
        print(f"  Valid analyses: {len(analyses)}, Failed: {failed}")

        # Pick top 2
        top2 = analyses[:2]

        trades = []
        for pick in top2:
            buy_data = get_stock_price_on_date(pick['symbol'], first_day)
            sell_data = get_stock_price_on_date(pick['symbol'], last_day)

            if buy_data and sell_data:
                buy_price = buy_data['open']  # Buy at open on first trading day
                sell_price = sell_data['close']  # Sell at close on last trading day
                pnl_pct = round((sell_price - buy_price) / buy_price * 100, 2)

                # Build reason string
                reason_parts = []
                for sig in pick['signals']:
                    if sig['confidence'] >= 0.65:
                        reason_parts.append(f"★ {sig['type']}: {sig['description']}")
                    else:
                        reason_parts.append(f"{sig['type']}: {sig['description']}")
                reason = ' | '.join(reason_parts) if reason_parts else '综合评分最高'

                trades.append({
                    'symbol': pick['symbol'],
                    'name': pick['name'],
                    'buy_date': str(buy_data['date']),
                    'buy_price': buy_price,
                    'sell_date': str(sell_data['date']),
                    'sell_price': sell_price,
                    'pnl_pct': pnl_pct,
                    'score': pick['score'],
                    'signals': pick['signals'],
                    'signal_count': pick['signal_count'],
                    'vol_ratio': pick['vol_ratio'],
                    'reason': reason
                })
                print(f"  Pick: {pick['symbol']} ({pick['name']}) Score={pick['score']} | Buy@{buy_price} Sell@{sell_price} P&L={pnl_pct:+.2f}%")
            else:
                print(f"  WARNING: Could not get price data for {pick['symbol']}")

        avg_pnl = round(np.mean([t['pnl_pct'] for t in trades]), 2) if trades else 0

        results.append({
            'month': month_label,
            'first_trading_day': str(first_day),
            'last_trading_day': str(last_day),
            'trades': trades,
            'avg_pnl': avg_pnl,
            'all_analyses_count': len(analyses),
            'top2_scores': [a['score'] for a in top2]
        })
        print(f"  Month avg P&L: {avg_pnl:+.2f}%")
        print()

    # Save results
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nBacktest complete! {len(results)} months saved to {output_file}")
    return results


if __name__ == '__main__':
    if len(sys.argv) != 6:
        print("Usage: python backtest_60m_chunk.py <start_year> <start_month> <end_year> <end_month> <output_json>")
        sys.exit(1)

    start_year = int(sys.argv[1])
    start_month = int(sys.argv[2])
    end_year = int(sys.argv[3])
    end_month = int(sys.argv[4])
    output_file = sys.argv[5]

    run_backtest(start_year, start_month, end_year, end_month, output_file)
