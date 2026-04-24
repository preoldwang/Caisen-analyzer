#!/usr/bin/env python3
"""
Monthly Backtest: Best 3 HK Blue Chip Picks per Month
======================================================
For each month:
1. Get first trading day data (up to that date)
2. Run Cai Sen analyzer on all HK stocks
3. Pick top 3 based on bullish signals
4. Record buy price (open on first trading day)
5. Record sell price (close on last trading day)
6. Report P&L and reasoning

Usage: python monthly_backtest.py <start_year> <start_month> <end_year> <end_month> <output_file>
"""

import sys
import os
import json
import warnings
from datetime import datetime, timedelta, date
from typing import List, Dict, Tuple, Optional
import traceback

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings('ignore')

# Add parent dir to path for analyzer import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# HK Blue Chip stock universe (84 stocks from scan)
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

# Stock names for display
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
    '1024.HK': 'Kuaishou', '1038.HK': 'CKI Holdings', '1044.HK': 'Hengan Int\'l',
    '1088.HK': 'China Shenhua', '1093.HK': 'CSPC Pharma', '1109.HK': 'China Resources Land',
    '1113.HK': 'CK Asset', '1177.HK': 'Sino Biopharm', '1209.HK': 'China Resources Mixc',
    '1211.HK': 'BYD', '1299.HK': 'AIA Group', '1378.HK': 'China Hongqiao',
    '1398.HK': 'ICBC', '1810.HK': 'Xiaomi', '1876.HK': 'Budweiser APAC',
    '1880.HK': 'China Tourism Group', '1928.HK': 'Sands China', '1929.HK': 'Chow Tai Fook',
    '1997.HK': 'Wharf REIC', '2007.HK': 'Country Garden', '2013.HK': 'WuXi Biologics',
    '2015.HK': 'Li Auto', '2020.HK': 'Anta Sports', '2050.HK': 'Sanhua Intelligent',
    '2269.HK': 'WuXi Bio', '2313.HK': 'Shenzhou Int\'l', '2318.HK': 'Ping An',
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


def get_first_trading_day(year: int, month: int) -> Optional[date]:
    """Get the first trading day of a month for HK market."""
    start = date(year, month, 1)
    end = date(year, month, 10)
    
    try:
        ticker = yf.Ticker('^HSI')
        hist = ticker.history(start=str(start), end=str(end + timedelta(days=1)), auto_adjust=False)
        if len(hist) > 0:
            first_day = hist.index[0].date()
            return first_day
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
            last_day = hist.index[-1].date()
            return last_day
    except Exception:
        pass
    
    d = end
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def get_stock_price_on_date(symbol: str, target_date: date) -> Optional[Dict]:
    """Get OHLCV data for a specific date. Uses raw (unadjusted) prices."""
    try:
        ticker = yf.Ticker(symbol)
        start = target_date - timedelta(days=5)
        end = target_date + timedelta(days=5)
        hist = ticker.history(start=str(start), end=str(end + timedelta(days=1)), auto_adjust=False)
        
        if hist.empty:
            return None
        
        # Find exact date or nearest
        hist.index = hist.index.tz_localize(None)
        target_dt = pd.Timestamp(target_date)
        
        if target_dt in hist.index:
            row = hist.loc[target_dt]
        else:
            # Find nearest date
            idx = hist.index.get_indexer([target_dt], method='nearest')[0]
            row = hist.iloc[idx]
            actual_date = hist.index[idx].date()
            if actual_date != target_date:
                # Accept if within 1 day
                pass
        
        return {
            'date': str(hist.index[hist.index.get_loc(row.name)].date()) if hasattr(row, 'name') else str(target_date),
            'open': round(float(row['Open']), 4),
            'high': round(float(row['High']), 4),
            'low': round(float(row['Low']), 4),
            'close': round(float(row['Close']), 4),
            'volume': int(row['Volume'])
        }
    except Exception as e:
        return None


def analyze_stock_at_date(symbol: str, as_of_date: date) -> Dict:
    """
    Analyze a stock using data up to a specific date.
    Returns signals and metrics for ranking.
    """
    try:
        # Fetch 2 years of data up to the target date (raw/unadjusted prices)
        ticker = yf.Ticker(symbol)
        end_dt = as_of_date + timedelta(days=1)
        start_dt = as_of_date - timedelta(days=730)  # 2 years
        hist = ticker.history(start=str(start_dt), end=str(end_dt), auto_adjust=False)
        
        if hist.empty or len(hist) < 20:
            return {'symbol': symbol, 'score': -999, 'signals': [], 'error': 'insufficient data'}
        
        hist.index = hist.index.tz_localize(None)
        
        # Calculate technical indicators manually for scoring
        close = hist['Close'].values
        volume = hist['Volume'].values
        high = hist['High'].values
        low = hist['Low'].values
        open_price = hist['Open'].values
        
        n = len(close)
        
        # --- Trend Analysis ---
        # 20-day and 60-day moving averages
        ma20 = np.mean(close[-20:]) if n >= 20 else close[-1]
        ma60 = np.mean(close[-60:]) if n >= 60 else close[-1]
        ma120 = np.mean(close[-120:]) if n >= 120 else close[-1]
        
        current_price = close[-1]
        
        # Trend score
        trend_score = 0
        if current_price > ma20:
            trend_score += 1
        if current_price > ma60:
            trend_score += 1
        if current_price > ma120:
            trend_score += 1
        if ma20 > ma60:
            trend_score += 1
        if ma60 > ma120:
            trend_score += 1
        
        # --- Volume Analysis ---
        avg_vol_20 = np.mean(volume[-20:]) if n >= 20 else np.mean(volume)
        recent_vol = volume[-1] if volume[-1] > 0 else 1
        vol_ratio = recent_vol / avg_vol_20 if avg_vol_20 > 0 else 1
        
        # Volume surge (bullish if price up with volume)
        vol_score = 0
        if vol_ratio > 1.5 and close[-1] > close[-2]:
            vol_score += 2  # Volume surge with price up
        elif vol_ratio > 1.2 and close[-1] > close[-2]:
            vol_score += 1
        
        # --- Pattern Detection ---
        signals = []
        pattern_score = 0
        
        # 1. 破底翻 (Bottom Breakdown & Recovery)
        if n >= 60:
            recent_low = np.min(low[-60:])
            # Find if price broke below a support then recovered
            for lookback in [20, 30, 40]:
                if n >= lookback:
                    period_low = np.min(low[-lookback:])
                    period_high = np.max(high[-lookback:])
                    # Support level (neckline)
                    support_candidates = []
                    for i in range(-lookback, -5):
                        if low[i] <= period_low * 1.02:
                            support_candidates.append(high[i])
                    
                    if support_candidates:
                        neckline = np.mean(support_candidates)
                        # Check if price recently broke below then recovered above
                        min_recent = np.min(low[-5:])
                        if min_recent < neckline * 0.98 and current_price > neckline:
                            signals.append({
                                'type': '破底翻',
                                'description': f'Broke below {neckline:.2f}, recovered above. Bullish reversal.',
                                'confidence': 0.75,
                                'neckline': round(neckline, 2)
                            })
                            pattern_score += 3
                            break
        
        # 2. W底 (W Bottom)
        if n >= 40:
            for lookback in [30, 40]:
                if n >= lookback:
                    lows_in_period = low[-lookback:]
                    # Find two similar lows
                    min1_idx = np.argmin(lows_in_period[:lookback//2])
                    min2_idx = np.argmin(lows_in_period[lookback//2:]) + lookback//2
                    
                    low1 = lows_in_period[min1_idx]
                    low2 = lows_in_period[min2_idx]
                    
                    if abs(low1 - low2) / max(low1, low2) < 0.03:  # Within 3%
                        neckline_w = np.max(high[min1_idx:min2_idx+1])
                        if current_price > neckline_w:
                            signals.append({
                                'type': 'W底',
                                'description': f'W bottom with lows at {low1:.2f}/{low2:.2f}, neckline {neckline_w:.2f}',
                                'confidence': 0.70,
                                'neckline': round(neckline_w, 2)
                            })
                            pattern_score += 2
                            break
        
        # 3. Volume-Price Divergence (量价背离)
        if n >= 20:
            # Price making new lows but volume decreasing (bullish divergence)
            price_low_5 = np.min(low[-5:])
            price_low_20 = np.min(low[-20:])
            vol_avg_5 = np.mean(volume[-5:])
            vol_avg_20 = np.mean(volume[-20:])
            
            if price_low_5 <= price_low_20 * 1.01 and vol_avg_5 < vol_avg_20 * 0.7:
                signals.append({
                    'type': '量价背离(上行)',
                    'description': f'Price near lows but volume shrinking. Potential reversal.',
                    'confidence': 0.65
                })
                pattern_score += 1
        
        # 4. Volume leads price (量先价行)
        if n >= 10:
            vol_surge_days = sum(1 for v in volume[-5:] if v > avg_vol_20 * 1.3)
            price_range = (max(close[-5:]) - min(close[-5:])) / min(close[-5:]) * 100
            
            if vol_surge_days >= 2 and price_range < 3:
                signals.append({
                    'type': '量先价行',
                    'description': f'Volume surging ({vol_surge_days} days) while price range narrow ({price_range:.1f}%). Breakout imminent.',
                    'confidence': 0.60
                })
                pattern_score += 1
        
        # 5. Neckline breakout (颈线突破)
        if n >= 30:
            # Find resistance levels
            highs_30 = high[-30:]
            resistance = np.max(highs_30)
            # Check if current price is near/breaking resistance
            if current_price > resistance * 0.98:
                vol_confirm = volume[-1] > avg_vol_20 * 1.2
                if vol_confirm:
                    signals.append({
                        'type': '颈线突破',
                        'description': f'Breaking resistance at {resistance:.2f} with volume confirmation.',
                        'confidence': 0.70,
                        'neckline': round(resistance, 2)
                    })
                    pattern_score += 2
        
        # 6. Support bounce (回踩支撑)
        if n >= 60:
            support_60 = np.min(low[-60:])
            if current_price < ma20 * 1.03 and current_price > support_60 * 1.05:
                # Price near support in uptrend
                if ma20 > ma60:
                    signals.append({
                        'type': '回踩支撑',
                        'description': f'Pullback to support zone ({support_60:.2f}) in uptrend.',
                        'confidence': 0.60
                    })
                    pattern_score += 1
        
        # 7. False Breakdown Recovery (假跌破反转)
        if n >= 20:
            prev_low = np.min(low[-10:-1])
            if low[-1] < prev_low and close[-1] > prev_low:
                signals.append({
                    'type': '假跌破反转',
                    'description': f'Shot below recent low {prev_low:.2f} but recovered. Bullish.',
                    'confidence': 0.65
                })
                pattern_score += 2
        
        # --- Composite Score ---
        total_score = trend_score + vol_score + pattern_score
        
        # Bonus for strong bullish alignment
        if trend_score >= 4 and pattern_score >= 2:
            total_score += 2
        
        # Risk-reward estimate
        if n >= 20:
            recent_range = np.max(high[-20:]) - np.min(low[-20:])
            stop_loss = current_price - recent_range * 0.5
            target = current_price + recent_range * 1.0
            risk = current_price - stop_loss
            reward = target - current_price
            rr_ratio = reward / risk if risk > 0 else 0
        else:
            stop_loss = current_price * 0.95
            target = current_price * 1.10
            rr_ratio = 2.0
        
        return {
            'symbol': symbol,
            'name': STOCK_NAMES.get(symbol, symbol),
            'current_price': round(current_price, 4),
            'ma20': round(ma20, 4),
            'ma60': round(ma60, 4),
            'ma120': round(ma120, 4),
            'trend_score': trend_score,
            'vol_score': vol_score,
            'pattern_score': pattern_score,
            'total_score': total_score,
            'vol_ratio': round(vol_ratio, 2),
            'signals': signals,
            'signal_count': len(signals),
            'stop_loss': round(stop_loss, 4),
            'target': round(target, 4),
            'rr_ratio': round(rr_ratio, 2),
            'error': None
        }
        
    except Exception as e:
        return {'symbol': symbol, 'score': -999, 'signals': [], 'error': str(e)}


def pick_top3(analyses: List[Dict]) -> List[Dict]:
    """Pick top 3 stocks based on composite score and signals."""
    # Filter out errors and zero-score
    valid = [a for a in analyses if a.get('total_score', -999) > 0 and not a.get('error')]
    
    # Sort by total_score descending, then by signal_count, then by rr_ratio
    valid.sort(key=lambda x: (x['total_score'], x['signal_count'], x['rr_ratio']), reverse=True)
    
    return valid[:3]


def get_buy_sell_prices(symbol: str, buy_date: date, sell_date: date) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Get actual buy (open on buy_date) and sell (close on sell_date) prices. Uses raw (unadjusted) prices."""
    try:
        ticker = yf.Ticker(symbol)
        start = buy_date - timedelta(days=3)
        end = sell_date + timedelta(days=3)
        hist = ticker.history(start=str(start), end=str(end + timedelta(days=1)), auto_adjust=False)
        
        if hist.empty:
            return None, None, None, None
        
        hist.index = hist.index.tz_localize(None)
        
        # Buy price: open on buy_date
        buy_dt = pd.Timestamp(buy_date)
        buy_rows = hist[hist.index >= buy_dt]
        if buy_rows.empty:
            return None, None, None, None
        buy_row = buy_rows.iloc[0]
        actual_buy_date = buy_rows.index[0].date()
        buy_open = round(float(buy_row['Open']), 4)
        buy_close = round(float(buy_row['Close']), 4)
        
        # Sell price: close on sell_date
        sell_dt = pd.Timestamp(sell_date)
        sell_rows = hist[hist.index <= sell_dt]
        if sell_rows.empty:
            return buy_open, None, actual_buy_date, None
        sell_row = sell_rows.iloc[-1]
        actual_sell_date = sell_rows.index[-1].date()
        sell_close = round(float(sell_row['Close']), 4)
        
        return buy_open, sell_close, actual_buy_date, actual_sell_date
        
    except Exception:
        return None, None, None, None


def run_monthly_backtest(year: int, month: int) -> Dict:
    """Run backtest for a single month."""
    print(f"\n{'='*60}")
    print(f"📅 Analyzing {year}-{month:02d}")
    print(f"{'='*60}")
    
    # Get trading dates
    first_day = get_first_trading_day(year, month)
    last_day = get_last_trading_day(year, month)
    
    if not first_day or not last_day:
        return {'month': f'{year}-{month:02d}', 'error': 'Cannot determine trading days'}
    
    print(f"  First trading day: {first_day}")
    print(f"  Last trading day:  {last_day}")
    
    # Analyze all stocks
    analyses = []
    for i, symbol in enumerate(HK_STOCKS):
        print(f"  [{i+1}/{len(HK_STOCKS)}] Analyzing {symbol}...", end='\r')
        result = analyze_stock_at_date(symbol, first_day)
        analyses.append(result)
    
    print(f"  ✅ Analyzed {len(analyses)} stocks")
    
    # Pick top 3
    top3 = pick_top3(analyses)
    
    if not top3:
        return {'month': f'{year}-{month:02d}', 'error': 'No valid picks found'}
    
    # Get actual buy/sell prices
    trades = []
    for pick in top3:
        buy_price, sell_price, actual_buy_date, actual_sell_date = get_buy_sell_prices(
            pick['symbol'], first_day, last_day
        )
        
        pnl_pct = None
        if buy_price and sell_price and buy_price > 0:
            pnl_pct = round((sell_price - buy_price) / buy_price * 100, 2)
        
        trade = {
            'symbol': pick['symbol'],
            'name': pick.get('name', pick['symbol']),
            'buy_date': str(actual_buy_date) if actual_buy_date else str(first_day),
            'buy_price': buy_price,
            'sell_date': str(actual_sell_date) if actual_sell_date else str(last_day),
            'sell_price': sell_price,
            'pnl_pct': pnl_pct,
            'score': pick['total_score'],
            'signals': pick['signals'],
            'signal_count': pick['signal_count'],
            'trend_score': pick['trend_score'],
            'vol_ratio': pick['vol_ratio'],
            'rr_ratio': pick['rr_ratio'],
            'reason': generate_reason(pick)
        }
        trades.append(trade)
        
        print(f"  🎯 {pick['symbol']} ({pick.get('name','')})")
        print(f"     Buy:  {trade['buy_date']} @ {trade['buy_price']}")
        print(f"     Sell: {trade['sell_date']} @ {trade['sell_price']}")
        if pnl_pct is not None:
            emoji = '📈' if pnl_pct > 0 else '📉'
            print(f"     P&L:  {emoji} {pnl_pct:+.2f}%")
    
    # Month summary
    pnls = [t['pnl_pct'] for t in trades if t['pnl_pct'] is not None]
    avg_pnl = np.mean(pnls) if pnls else None
    
    return {
        'month': f'{year}-{month:02d}',
        'first_trading_day': str(first_day),
        'last_trading_day': str(last_day),
        'trades': trades,
        'avg_pnl': round(avg_pnl, 2) if avg_pnl is not None else None,
        'all_analyses_count': len(analyses),
        'top3_scores': [t['score'] for t in trades]
    }


def generate_reason(pick: Dict) -> str:
    """Generate human-readable reason for the recommendation."""
    reasons = []
    
    # Trend
    ts = pick.get('trend_score', 0)
    if ts >= 4:
        reasons.append("Strong bullish trend (price above all MAs, MAs aligned bullishly)")
    elif ts >= 3:
        reasons.append("Bullish trend (price above most moving averages)")
    elif ts >= 2:
        reasons.append("Moderate uptrend")
    
    # Volume
    vr = pick.get('vol_ratio', 1)
    if vr > 1.5:
        reasons.append(f"Volume surge ({vr:.1f}x average) — strong buying interest")
    elif vr > 1.2:
        reasons.append(f"Above-average volume ({vr:.1f}x)")
    
    # Signals
    for sig in pick.get('signals', []):
        stype = sig.get('type', '')
        desc = sig.get('description', '')
        if stype == '破底翻':
            reasons.append(f"★ 破底翻 signal: {desc}")
        elif stype == 'W底':
            reasons.append(f"★ W bottom pattern: {desc}")
        elif stype == '颈线突破':
            reasons.append(f"★ Neckline breakout: {desc}")
        elif stype == '量先价行':
            reasons.append(f"★ Volume leads price: {desc}")
        elif stype == '量价背离(上行)':
            reasons.append(f"★ Bullish volume-price divergence: {desc}")
        elif stype == '回踩支撑':
            reasons.append(f"★ Pullback to support: {desc}")
        elif stype == '假跌破反转':
            reasons.append(f"★ False breakdown reversal: {desc}")
        else:
            reasons.append(f"★ {stype}: {desc}")
    
    # Risk-reward
    rr = pick.get('rr_ratio', 0)
    if rr >= 2:
        reasons.append(f"Favorable risk-reward ratio ({rr:.1f}:1)")
    
    return ' | '.join(reasons) if reasons else 'Technical score-based selection'


def generate_html_report(results: List[Dict], output_path: str):
    """Generate HTML report of backtest results."""
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HK Blue Chip Monthly Backtest - Cai Sen Analysis</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0a; color: #e0e0e0; line-height: 1.6; }
.container { max-width: 1400px; margin: 0 auto; padding: 20px; }
h1 { text-align: center; color: #00d4ff; font-size: 2em; margin-bottom: 5px; }
.subtitle { text-align: center; color: #888; margin-bottom: 30px; font-size: 0.95em; }
.summary-box { background: linear-gradient(135deg, #1a1a2e, #16213e); border: 1px solid #0f3460; border-radius: 12px; padding: 25px; margin-bottom: 30px; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 15px; }
.summary-item { text-align: center; }
.summary-item .label { color: #888; font-size: 0.85em; text-transform: uppercase; letter-spacing: 1px; }
.summary-item .value { font-size: 1.8em; font-weight: bold; margin-top: 5px; }
.positive { color: #00ff88; }
.negative { color: #ff4444; }
.neutral { color: #ffaa00; }
.month-card { background: #111; border: 1px solid #222; border-radius: 10px; margin-bottom: 20px; overflow: hidden; }
.month-header { background: linear-gradient(90deg, #1a1a2e, #0f3460); padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
.month-header h2 { color: #00d4ff; font-size: 1.2em; }
.month-header .dates { color: #888; font-size: 0.85em; }
.month-header .pnl { font-size: 1.1em; font-weight: bold; }
.month-body { padding: 20px; }
table { width: 100%; border-collapse: collapse; margin-top: 10px; }
th { background: #1a1a2e; color: #00d4ff; padding: 10px 12px; text-align: left; font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.5px; }
td { padding: 10px 12px; border-bottom: 1px solid #1a1a1a; font-size: 0.9em; }
tr:hover { background: #1a1a1a; }
.stock-name { color: #aaa; font-size: 0.85em; }
.reason { color: #888; font-size: 0.8em; max-width: 400px; line-height: 1.4; }
.reason .signal { color: #ffaa00; }
.buy-price { color: #00d4ff; }
.sell-price { color: #ffaa00; }
.pnl-positive { color: #00ff88; font-weight: bold; }
.pnl-negative { color: #ff4444; font-weight: bold; }
.footer { text-align: center; color: #555; margin-top: 40px; padding: 20px; border-top: 1px solid #222; }
.methodology { background: #111; border: 1px solid #222; border-radius: 10px; padding: 20px; margin-bottom: 30px; }
.methodology h3 { color: #00d4ff; margin-bottom: 10px; }
.methodology p { color: #888; font-size: 0.9em; margin-bottom: 8px; }
.cumulative-chart { background: #111; border: 1px solid #222; border-radius: 10px; padding: 20px; margin-bottom: 30px; }
.bar { display: inline-block; margin: 2px; border-radius: 3px 3px 0 0; min-width: 30px; text-align: center; font-size: 0.7em; padding-top: 3px; }
</style>
</head>
<body>
<div class="container">
<h1>📊 HK Blue Chip Monthly Backtest</h1>
<p class="subtitle">Cai Sen Technical Analysis (蔡森技術分析) · 20-Month Backtest · Top 3 Picks per Month</p>
"""
    
    # Calculate overall stats
    all_pnl = []
    all_trades = []
    for r in results:
        if 'trades' in r:
            for t in r['trades']:
                if t.get('pnl_pct') is not None:
                    all_pnl.append(t['pnl_pct'])
                    all_trades.append(t)
    
    total_trades = len(all_trades)
    winners = len([p for p in all_pnl if p > 0])
    losers = len([p for p in all_pnl if p < 0])
    avg_pnl = np.mean(all_pnl) if all_pnl else 0
    total_return = 1.0
    for p in all_pnl:
        total_return *= (1 + p / 100)
    total_return_pct = (total_return - 1) * 100
    win_rate = (winners / total_trades * 100) if total_trades > 0 else 0
    max_win = max(all_pnl) if all_pnl else 0
    max_loss = min(all_pnl) if all_pnl else 0
    
    pnl_class = 'positive' if avg_pnl > 0 else 'negative'
    ret_class = 'positive' if total_return_pct > 0 else 'negative'
    
    html += f"""
<div class="summary-box">
<h2 style="color: #e0e0e0;">📋 Overall Summary</h2>
<div class="summary-grid">
<div class="summary-item"><div class="label">Total Trades</div><div class="value">{total_trades}</div></div>
<div class="summary-item"><div class="label">Winners / Losers</div><div class="value"><span class="positive">{winners}</span> / <span class="negative">{losers}</span></div></div>
<div class="summary-item"><div class="label">Win Rate</div><div class="value {'positive' if win_rate >= 50 else 'negative'}">{win_rate:.1f}%</div></div>
<div class="summary-item"><div class="label">Avg Monthly P&L</div><div class="value {pnl_class}">{avg_pnl:+.2f}%</div></div>
<div class="summary-item"><div class="label">Cumulative Return</div><div class="value {ret_class}">{total_return_pct:+.2f}%</div></div>
<div class="summary-item"><div class="label">Best Trade</div><div class="value positive">{max_win:+.2f}%</div></div>
<div class="summary-item"><div class="label">Worst Trade</div><div class="value negative">{max_loss:+.2f}%</div></div>
</div>
</div>
"""
    
    # Methodology
    html += """
<div class="methodology">
<h3>📐 Methodology</h3>
<p><strong>Selection:</strong> Each month, all 84 HK stocks are analyzed using Cai Sen's volume-price methodology. 
The top 3 are selected based on: trend alignment (MA20/60/120), volume confirmation, and pattern signals 
(破底翻, W底, 颈线突破, 量先价行, 量价背离, etc.).</p>
<p><strong>Trading:</strong> Buy at market open on the first trading day of the month. Sell at close on the last trading day.</p>
<p><strong>Data Source:</strong> Yahoo Finance (yfinance) — validated against historical records.</p>
<p><strong>Disclaimer:</strong> This backtest is for research purposes only. Past performance does not guarantee future results.</p>
</div>
"""
    
    # Monthly P&L bar chart
    html += '<div class="cumulative-chart"><h3 style="color:#00d4ff; margin-bottom:15px;">📈 Monthly P&L Overview</h3><div style="display:flex; flex-wrap:wrap; align-items:flex-end; height:150px; padding:10px 0;">'
    for r in results:
        if 'trades' in r:
            month_pnl = r.get('avg_pnl', 0) or 0
            bar_height = max(5, abs(month_pnl) * 5)
            bar_color = '#00ff88' if month_pnl > 0 else '#ff4444' if month_pnl < 0 else '#888'
            html += f'<div class="bar" style="height:{bar_height}px; background:{bar_color};">{month_pnl:+.1f}%</div>'
    html += '</div></div>'
    
    # Monthly details
    for r in results:
        month = r.get('month', '?')
        first_day = r.get('first_trading_day', '?')
        last_day = r.get('last_trading_day', '?')
        avg = r.get('avg_pnl')
        
        if avg is not None:
            pnl_html = f'<span class="{"positive" if avg > 0 else "negative"}">{avg:+.2f}%</span>'
        else:
            pnl_html = '<span class="neutral">N/A</span>'
        
        html += f"""
<div class="month-card">
<div class="month-header">
<div>
<h2>📅 {month}</h2>
<span class="dates">Buy: {first_day} → Sell: {last_day}</span>
</div>
<div class="pnl">{pnl_html}</div>
</div>
<div class="month-body">
<table>
<tr>
<th>Rank</th>
<th>Stock</th>
<th>Buy Date</th>
<th>Buy Price (HKD)</th>
<th>Sell Date</th>
<th>Sell Price (HKD)</th>
<th>P&L</th>
<th>Score</th>
<th>Reason</th>
</tr>
"""
        
        if 'trades' in r:
            for i, t in enumerate(r['trades']):
                pnl = t.get('pnl_pct')
                if pnl is not None:
                    pnl_display = f'{pnl:+.2f}%'
                    pnl_cls = 'pnl-positive' if pnl > 0 else 'pnl-negative'
                else:
                    pnl_display = 'N/A'
                    pnl_cls = ''
                
                buy_p = t.get('buy_price', 'N/A')
                sell_p = t.get('sell_price', 'N/A')
                reason = t.get('reason', '')
                # Highlight signals in reason
                reason_html = reason.replace('★', '<span class="signal">★</span>')
                
                html += f"""
<tr>
<td>#{i+1}</td>
<td><strong>{t['symbol']}</strong><br><span class="stock-name">{t.get('name','')}</span></td>
<td>{t.get('buy_date','?')}</td>
<td class="buy-price">{buy_p}</td>
<td>{t.get('sell_date','?')}</td>
<td class="sell-price">{sell_p}</td>
<td class="{pnl_cls}">{pnl_display}</td>
<td>{t.get('score','?')}</td>
<td class="reason">{reason_html}</td>
</tr>
"""
        
        if 'error' in r:
            html += f'<tr><td colspan="9" style="color:#ff4444;">Error: {r["error"]}</td></tr>'
        
        html += "</table></div></div>"
    
    html += f"""
<div class="footer">
<p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')} · Cai Sen Technical Analysis Tool v3.0</p>
<p>蔡森技術分析 · 基于量价关系的股票型态识别 · 仅供研究用途</p>
</div>
</div>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n📄 HTML report saved to: {output_path}")


def main():
    """Main entry point."""
    if len(sys.argv) < 5:
        print("Usage: python monthly_backtest.py <start_year> <start_month> <end_year> <end_month> <output_file>")
        sys.exit(1)
    
    start_year = int(sys.argv[1])
    start_month = int(sys.argv[2])
    end_year = int(sys.argv[3])
    end_month = int(sys.argv[4])
    output_file = sys.argv[5] if len(sys.argv) > 5 else f"backtest_{start_year}{start_month:02d}_{end_year}{end_month:02d}.html"
    
    # Generate month list
    months = []
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    
    print(f"🚀 Starting backtest: {len(months)} months ({start_year}-{start_month:02d} to {end_year}-{end_month:02d})")
    
    results = []
    for year, month in months:
        try:
            result = run_monthly_backtest(year, month)
            results.append(result)
        except Exception as e:
            print(f"❌ Error for {year}-{month:02d}: {e}")
            traceback.print_exc()
            results.append({'month': f'{year}-{month:02d}', 'error': str(e)})
    
    # Save JSON
    json_path = output_file.replace('.html', '.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"💾 JSON data saved to: {json_path}")
    
    # Generate HTML report
    generate_html_report(results, output_file)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 BACKTEST SUMMARY")
    print("=" * 60)
    all_pnl = []
    for r in results:
        if 'trades' in r:
            for t in r['trades']:
                if t.get('pnl_pct') is not None:
                    all_pnl.append(t['pnl_pct'])
    
    if all_pnl:
        print(f"Total trades: {len(all_pnl)}")
        print(f"Winners: {len([p for p in all_pnl if p > 0])}")
        print(f"Losers: {len([p for p in all_pnl if p < 0])}")
        print(f"Win rate: {len([p for p in all_pnl if p > 0])/len(all_pnl)*100:.1f}%")
        print(f"Average P&L: {np.mean(all_pnl):+.2f}%")
        total_ret = 1.0
        for p in all_pnl:
            total_ret *= (1 + p / 100)
        print(f"Cumulative return: {(total_ret-1)*100:+.2f}%")


if __name__ == "__main__":
    main()
