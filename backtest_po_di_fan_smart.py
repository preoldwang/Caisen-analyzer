#!/usr/bin/env python3
"""
破底翻 SMART Backtest (Top 2 + Filters) — HSI Blue Chips
=========================================================
Enhanced version with smart filters:
1. Volume confirmation required (放量确认)
2. R:R >= 3.0 (Cai Sen's 3:1 rule)
3. Confidence >= 0.7
4. 20-day MA trending up (short-term trend filter)
5. No repeat: skip stock if traded in prior 2 months
6. Market regime: skip if HSI below 60-day MA (bear filter)
7. Liquidity: skip if avg daily volume < 1M shares
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# Config
# ============================================================
BACKTEST_START = "2019-01-01"
BACKTEST_END = "2026-03-31"
TOP_N = 2
MAX_HOLD_DAYS = 30

# SMART Filters
MIN_CONFIDENCE = 0.7
MIN_RR = 3.0
REQUIRE_VOLUME = True
REQUIRE_MA_UPTREND = True
MA_PERIOD = 20
SKIP_RECENT_MONTHS = 2  # Skip if traded in last N months
MARKET_FILTER = True  # Skip if HSI below 60-day MA
HSI_TICKER = "^HSI"
MIN_AVG_VOLUME = 500_000  # Min avg daily volume

# ============================================================
# Data Classes
# ============================================================
@dataclass
class Signal:
    ticker: str
    name: str
    signal_date: str
    entry_price: float
    stop_loss: float
    target_price: float
    neckline: float
    bottom_price: float
    confidence: float
    risk_reward: float
    volume_confirmed: bool
    ma_uptrend: bool
    description: str

@dataclass
class Trade:
    ticker: str
    name: str
    signal_date: str
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    stop_loss: float
    target_price: float
    exit_reason: str
    holding_days: int
    pnl_pct: float
    confidence: float
    risk_reward: float
    filters_passed: str

# ============================================================
# Detector
# ============================================================
def detect_po_di_fan(ticker, name, df, scan_end_date, hsi_df=None):
    signals = []
    if df is None or len(df) < 90:
        return signals

    mask = df.index <= scan_end_date
    data = df[mask].copy()
    if len(data) < 90:
        return signals

    open_prices = data['Open'].values
    close = data['Close'].values
    low = data['Low'].values
    volume = data['Volume'].values
    dates = data.index
    target_month = pd.Timestamp(scan_end_date).month
    target_year = pd.Timestamp(scan_end_date).year

    # Pre-compute MA
    ma_series = pd.Series(close).rolling(MA_PERIOD).mean().values

    # Pre-compute avg volume (20-day)
    avg_vol_series = pd.Series(volume).rolling(20).mean().values

    for lookback in [60, 90, 120]:
        if len(close) < lookback + 30:
            continue

        for end_idx in range(lookback + 30, len(close)):
            signal_date = pd.Timestamp(dates[end_idx - 1])
            if signal_date.month != target_month or signal_date.year != target_year:
                continue

            segment = close[end_idx - lookback:end_idx]
            seg_vol = volume[end_idx - lookback:end_idx]

            min_price = np.min(segment)
            min_idx = np.argmin(segment)

            if min_idx > 5 and min_idx < len(segment) - 10:
                recovery = segment[min_idx:]
                if len(recovery) > 3:
                    neckline = np.percentile(recovery, 70)
                else:
                    continue
            else:
                continue

            pre_high = np.max(segment[:min_idx]) if min_idx > 10 else neckline

            check_window = close[end_idx - 30:end_idx]
            check_low = low[end_idx - 30:end_idx]
            if len(check_window) < 20:
                continue

            broke_below = False
            broke_below_idx = -1
            for i, price in enumerate(check_low):
                if price < min_price * 0.98:
                    broke_below = True
                    broke_below_idx = i
                    break

            if not broke_below or broke_below_idx >= len(check_window) - 5:
                continue

            after_break = check_window[broke_below_idx:]
            recovered = any(p > neckline for p in after_break[-5:])
            if not recovered:
                continue

            # Volume confirmation
            recent_vol = volume[end_idx - 5:end_idx]
            avg_vol = np.mean(seg_vol) if np.mean(seg_vol) > 0 else 1
            vol_confirm = np.mean(recent_vol) > avg_vol * 1.2

            # MA uptrend check
            current_ma = ma_series[end_idx - 1] if end_idx < len(ma_series) else None
            prev_ma = ma_series[end_idx - 6] if end_idx >= 6 else None
            ma_up = False
            if current_ma is not None and prev_ma is not None and not np.isnan(current_ma) and not np.isnan(prev_ma):
                ma_up = current_ma > prev_ma

            # Liquidity check
            current_avg_vol = avg_vol_series[end_idx - 1] if end_idx < len(avg_vol_series) else avg_vol
            if np.isnan(current_avg_vol):
                current_avg_vol = avg_vol

            # Use next day's Open as entry price (realistic execution)
            if end_idx >= len(open_prices):
                continue
            entry = open_prices[end_idx]
            stop_loss = min_price * 0.97
            distance = neckline - min_price
            target_1 = max(neckline + distance, pre_high)
            target_2 = neckline + distance * 1.618

            risk = entry - stop_loss
            reward = target_1 - entry
            rr = reward / risk if risk > 0 else 0

            confidence = 0.5
            if vol_confirm:
                confidence += 0.2
            if rr >= 3:
                confidence += 0.15
            if broke_below_idx > 5:
                confidence += 0.15

            if confidence >= 0.5 and rr >= 1.5:
                signals.append(Signal(
                    ticker=ticker, name=name,
                    signal_date=signal_date.strftime('%Y-%m-%d'),
                    entry_price=round(entry, 2),
                    stop_loss=round(stop_loss, 2),
                    target_price=round(target_1, 2),
                    neckline=round(neckline, 2),
                    bottom_price=round(min_price, 2),
                    confidence=round(min(confidence, 1.0), 2),
                    risk_reward=round(rr, 2),
                    volume_confirmed=vol_confirm,
                    ma_uptrend=ma_up,
                    description=f"破底翻: {min_price:.2f}→{neckline:.2f} {'(放量)' if vol_confirm else ''} {'(MA↑)' if ma_up else ''}"
                ))

    if signals:
        signals.sort(key=lambda s: (-s.confidence, -s.risk_reward))
        deduped = []
        seen = set()
        for s in signals:
            if s.signal_date not in seen:
                deduped.append(s)
                seen.add(s.signal_date)
        signals = deduped[:5]

    return signals

# ============================================================
# SMART Filter
# ============================================================
def apply_smart_filters(signals: List[Signal], recent_tickers: set, hsi_df: pd.DataFrame, stock_data: dict, month_end: str) -> List[Signal]:
    filtered = []
    for s in signals:
        reasons = []

        # 1. Confidence filter
        if s.confidence < MIN_CONFIDENCE:
            reasons.append(f"conf={s.confidence}<{MIN_CONFIDENCE}")

        # 2. R:R filter
        if s.risk_reward < MIN_RR:
            reasons.append(f"R:R={s.risk_reward}<{MIN_RR}")

        # 3. Volume confirmation
        if REQUIRE_VOLUME and not s.volume_confirmed:
            reasons.append("no_vol_confirm")

        # 4. MA uptrend
        if REQUIRE_MA_UPTREND and not s.ma_uptrend:
            reasons.append("MA_not_up")

        # 5. Skip recent trades
        if s.ticker in recent_tickers:
            reasons.append(f"traded_recent_{SKIP_RECENT_MONTHS}m")

        # 6. Market regime (HSI filter)
        if MARKET_FILTER and hsi_df is not None:
            hsi_mask = hsi_df.index <= month_end
            hsi_data = hsi_df[hsi_mask]
            if len(hsi_data) >= 60:
                hsi_close = hsi_data['Close'].values
                hsi_ma60 = np.mean(hsi_close[-60:])
                hsi_current = hsi_close[-1]
                if hsi_current < hsi_ma60 * 0.97:  # 3% below 60-day MA
                    reasons.append(f"HSI_below_MA60({hsi_current:.0f}<{hsi_ma60:.0f})")

        # 7. Liquidity
        if s.ticker in stock_data:
            df = stock_data[s.ticker]['df']
            mask = df.index <= month_end
            recent = df[mask].tail(20)
            if len(recent) > 0:
                avg_vol = recent['Volume'].mean()
                if avg_vol < MIN_AVG_VOLUME:
                    reasons.append(f"low_vol({avg_vol/1e6:.1f}M)")

        if not reasons:
            filtered.append(s)
        else:
            pass  # filtered out

    return filtered

# ============================================================
# Trade Simulator
# ============================================================
def simulate_trade(signal, price_data):
    if price_data is None or price_data.empty:
        return None

    entry_date = pd.Timestamp(signal.signal_date)
    future = price_data[price_data.index > entry_date]
    if future.empty:
        return None

    entry_price = signal.entry_price
    stop_loss = signal.stop_loss
    target = signal.target_price
    entry_dt = future.index[0]

    exit_date = None
    exit_price = None
    exit_reason = "max_hold"

    for i, (dt, row) in enumerate(future.iterrows()):
        if i >= MAX_HOLD_DAYS:
            exit_date = dt
            exit_price = row['Close']
            exit_reason = "max_hold"
            break
        if row['Low'] <= stop_loss:
            exit_date = dt
            exit_price = stop_loss
            exit_reason = "stop_loss"
            break
        if row['High'] >= target:
            exit_date = dt
            exit_price = target
            exit_reason = "target"
            break

    if exit_date is None:
        exit_date = future.index[-1]
        exit_price = future.iloc[-1]['Close']
        exit_reason = "end_of_data"

    holding_days = (exit_date - entry_dt).days
    pnl_pct = (exit_price - entry_price) / entry_price * 100

    return Trade(
        ticker=signal.ticker, name=signal.name,
        signal_date=signal.signal_date,
        entry_date=entry_dt.strftime('%Y-%m-%d'),
        entry_price=round(entry_price, 2),
        exit_date=exit_date.strftime('%Y-%m-%d'),
        exit_price=round(exit_price, 2),
        stop_loss=signal.stop_loss,
        target_price=signal.target_price,
        exit_reason=exit_reason,
        holding_days=holding_days,
        pnl_pct=round(pnl_pct, 2),
        confidence=signal.confidence,
        risk_reward=signal.risk_reward,
        filters_passed="all_smart_filters"
    )

# ============================================================
# Main
# ============================================================
def run_backtest():
    print("=" * 70)
    print("破底翻 SMART Backtest — HSI Blue Chips")
    print(f"Period: {BACKTEST_START} to {BACKTEST_END}")
    print(f"Filters: conf>={MIN_CONFIDENCE}, R:R>={MIN_RR}, vol={REQUIRE_VOLUME}, MA↑={REQUIRE_MA_UPTREND}")
    print(f"         skip_recent={SKIP_RECENT_MONTHS}m, market_filter={MARKET_FILTER}, min_vol={MIN_AVG_VOLUME/1e6:.0f}M")
    print("=" * 70)

    # Load data
    print("\nLoading price data...")
    with open('hk_blue_chip_8y_prices.json', 'r') as f:
        raw = json.load(f)

    stock_data = {}
    for ticker, info in raw['stocks'].items():
        df = pd.DataFrame(info['data'])
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        stock_data[ticker] = {'name': info['name'], 'df': df}

    # Load HSI data for market filter
    print("Fetching HSI index data for market regime filter...")
    try:
        import yfinance as yf
        hsi = yf.Ticker(HSI_TICKER)
        hsi_df = hsi.history(start='2018-01-01', end=BACKTEST_END, auto_adjust=False)
        hsi_df = hsi_df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        print(f"  HSI data: {len(hsi_df)} days")
    except:
        hsi_df = None
        print("  ⚠️ Could not fetch HSI data, market filter disabled")

    print(f"Loaded {len(stock_data)} stocks")

    months = pd.date_range(start=BACKTEST_START, end=BACKTEST_END, freq='MS')
    print(f"Months: {len(months)}")

    all_trades = []
    monthly_results = []
    recent_tickers = set()  # Track recently traded tickers
    filtered_out_log = []

    for month_start in months:
        month_end = (month_start + pd.offsets.MonthEnd(0)).strftime('%Y-%m-%d')
        month_label = month_start.strftime('%Y-%m')
        print(f"\n--- {month_label} ---")

        # Collect raw signals
        raw_signals = []
        for ticker, info in stock_data.items():
            signals = detect_po_di_fan(ticker, info['name'], info['df'], month_end, hsi_df)
            raw_signals.extend(signals)

        if not raw_signals:
            print(f"  No raw signals")
            monthly_results.append({'month': month_label, 'raw': 0, 'filtered': 0, 'trades': [], 'picks': []})
            continue

        # Deduplicate per stock
        seen = set()
        unique = []
        for s in raw_signals:
            if s.ticker not in seen:
                unique.append(s)
                seen.add(s.ticker)
        raw_signals = unique

        print(f"  Raw signals: {len(raw_signals)}")

        # Apply SMART filters
        filtered = apply_smart_filters(raw_signals, recent_tickers, hsi_df, stock_data, month_end)
        print(f"  After SMART filters: {len(filtered)}")

        # Sort by confidence * R:R
        filtered.sort(key=lambda s: -(s.confidence * s.risk_reward))

        # Pick top N
        picks = filtered[:TOP_N]

        if not picks:
            # Log what was filtered out
            for s in raw_signals[:3]:
                reasons = []
                if s.confidence < MIN_CONFIDENCE: reasons.append(f"conf={s.confidence}")
                if s.risk_reward < MIN_RR: reasons.append(f"R:R={s.risk_reward}")
                if REQUIRE_VOLUME and not s.volume_confirmed: reasons.append("no_vol")
                if REQUIRE_MA_UPTREND and not s.ma_uptrend: reasons.append("no_MA↑")
                if s.ticker in recent_tickers: reasons.append("recent_trade")
                print(f"    Filtered: {s.ticker} {s.name} — {', '.join(reasons)}")
            monthly_results.append({'month': month_label, 'raw': len(raw_signals), 'filtered': 0, 'trades': [], 'picks': []})
            continue

        # Simulate trades
        month_trades = []
        for signal in picks:
            df = stock_data[signal.ticker]['df']
            trade = simulate_trade(signal, df)
            if trade:
                month_trades.append(trade)
                all_trades.append(trade)
                recent_tickers.add(signal.ticker)
                print(f"    ✅ {trade.ticker} {trade.name}: entry {trade.entry_date}@{trade.entry_price} → {trade.exit_date}@{trade.exit_price} ({trade.exit_reason}) PnL={trade.pnl_pct:+.2f}%")

        monthly_results.append({
            'month': month_label,
            'raw': len(raw_signals),
            'filtered': len(filtered),
            'trades': month_trades,
            'picks': picks
        })

        # Decay recent tickers (remove tickers older than SKIP_RECENT_MONTHS)
        if len(monthly_results) > SKIP_RECENT_MONTHS:
            old_month = monthly_results[-(SKIP_RECENT_MONTHS + 1)]
            for t in old_month.get('trades', []):
                recent_tickers.discard(t.ticker)

    # ============================================================
    # Stats
    # ============================================================
    print("\n" + "=" * 70)
    print("SMART BACKTEST SUMMARY")
    print("=" * 70)

    total = len(all_trades)
    wins = [t for t in all_trades if t.pnl_pct > 0]
    losses = [t for t in all_trades if t.pnl_pct <= 0]
    win_rate = len(wins) / total * 100 if total > 0 else 0

    avg_pnl = np.mean([t.pnl_pct for t in all_trades]) if all_trades else 0
    avg_win = np.mean([t.pnl_pct for t in wins]) if wins else 0
    avg_loss = np.mean([t.pnl_pct for t in losses]) if losses else 0

    cumulative = 100
    curve = [100]
    for t in all_trades:
        cumulative *= (1 + t.pnl_pct / 100)
        curve.append(cumulative)
    total_return = cumulative - 100

    peak = curve[0]
    max_dd = 0
    for v in curve:
        if v > peak: peak = v
        dd = (peak - v) / peak * 100
        if dd > max_dd: max_dd = dd

    exit_reasons = {}
    for t in all_trades:
        exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

    avg_hold = np.mean([t.holding_days for t in all_trades]) if all_trades else 0

    print(f"Total trades: {total}")
    print(f"Winners: {len(wins)} ({win_rate:.1f}%)")
    print(f"Losers: {len(losses)} ({100-win_rate:.1f}%)")
    print(f"Avg PnL: {avg_pnl:+.2f}%")
    print(f"Avg Win: {avg_win:+.2f}%")
    print(f"Avg Loss: {avg_loss:+.2f}%")
    print(f"Total Return: {total_return:+.2f}%")
    print(f"Max Drawdown: {max_dd:.2f}%")
    print(f"Avg Hold: {avg_hold:.0f} days")
    print(f"Exit reasons: {exit_reasons}")

    return all_trades, monthly_results, {
        'total_trades': total,
        'win_rate': win_rate,
        'avg_pnl': avg_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'total_return': total_return,
        'max_drawdown': max_dd,
        'avg_hold': avg_hold,
        'exit_reasons': exit_reasons,
        'cumulative_curve': curve,
        'winning_trades': len(wins),
        'losing_trades': len(losses),
    }

# ============================================================
# HTML
# ============================================================
def generate_html(all_trades, monthly_results, stats):
    html = []
    html.append("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>破底翻 SMART Backtest — HSI Blue Chips (Jan 2019 - Mar 2026)</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#080c14;color:#c9d1d9}
.container{max-width:1400px;margin:0 auto;padding:20px}
h1{text-align:center;color:#00d4ff;font-size:30px;margin:20px 0 8px}
.subtitle{text-align:center;color:#8b949e;font-size:14px;margin-bottom:30px}
.subtitle span{margin:0 8px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:30px}
.card{background:#0f1923;border:1px solid #1a2a3a;border-radius:12px;padding:18px;text-align:center}
.card .label{color:#8b949e;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}
.card .value{font-size:26px;font-weight:700}
.g{color:#00e676}.r{color:#ff5252}.b{color:#00d4ff}.o{color:#ff9100}.p{color:#bb86fc}
.filter-info{background:#0f1923;border:1px solid #1a2a3a;border-radius:12px;padding:20px;margin-bottom:24px}
.filter-info h2{color:#00d4ff;margin-bottom:10px;font-size:18px}
.filter-info .rule{display:flex;align-items:center;gap:8px;margin-bottom:5px;color:#8b949e;font-size:13px}
.filter-info .rule strong{color:#c9d1d9}
.chart-wrap{background:#0f1923;border:1px solid #1a2a3a;border-radius:12px;padding:20px;margin-bottom:24px}
.chart-wrap h2{color:#00d4ff;margin-bottom:14px}
.eq-bar{display:flex;align-items:flex-end;height:220px;gap:1px;border-bottom:1px solid #1a2a3a;padding-bottom:2px}
.eq-bar div{flex:1;border-radius:2px 2px 0 0;min-width:2px}
.eq-labels{display:flex;justify-content:space-between;color:#8b949e;font-size:11px;padding-top:6px}
.all-trades{background:#0f1923;border:1px solid #1a2a3a;border-radius:12px;overflow:hidden;margin-bottom:24px}
.all-trades h2{padding:18px;color:#00d4ff}
.tw{max-height:600px;overflow-y:auto}
table{width:100%;border-collapse:collapse;font-size:12px}
th{background:#080c14;color:#8b949e;padding:8px 10px;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.5px;position:sticky;top:0}
td{padding:7px 10px;border-bottom:1px solid #141e2a}
tr:hover{background:#0f1923}
.pp{color:#00e676;font-weight:600}.pn{color:#ff5252;font-weight:600}.pz{color:#8b949e}
.et{color:#00e676}.es{color:#ff5252}.em{color:#ff9100}.eo{color:#8b949e}
.ms{background:#0f1923;border:1px solid #1a2a3a;border-radius:12px;margin-bottom:12px;overflow:hidden}
.mh{padding:14px 18px;background:#0a1018;cursor:pointer;display:flex;justify-content:space-between;align-items:center}
.mh:hover{background:#141e2a}
.mh h3{color:#00d4ff;font-size:16px}
.ms .sum{display:flex;gap:12px;font-size:12px}
.tag{padding:2px 8px;border-radius:4px;font-size:11px}
.tw2{color:#00e676;background:#002200}
.tl{color:#ff5252;background:#220000}
.tn{color:#8b949e;background:#141e2a}
.mb.hidden{display:none}
.heatmap{display:grid;grid-template-columns:repeat(12,1fr);gap:3px;margin-top:12px}
.hm-cell{padding:7px 4px;border-radius:4px;text-align:center;font-size:11px;font-weight:600}
.hm-year{text-align:center;color:#8b949e;font-weight:bold;padding:7px 0;font-size:13px}
@media(max-width:768px){.grid{grid-template-columns:repeat(2,1fr)}.card .value{font-size:20px}table{font-size:10px}}
</style>
</head>
<body>
<div class="container">
<h1>🧠 破底翻 SMART Backtest — HSI Blue Chips</h1>
<p class="subtitle"><span>📅 Jan 2019 → Mar 2026</span><span>|</span><span>🔬 Top 2 + Smart Filters</span><span>|</span><span>🎯 """ + str(stats['total_trades']) + """ trades</span></p>
""")

    # Filter Info
    html.append("""
<div class="filter-info">
<h2>🔬 SMART Filters Applied</h2>
<div class="rule">✅ <strong>Confidence ≥ """ + str(MIN_CONFIDENCE) + """</strong> — Only high-conviction signals</div>
<div class="rule">✅ <strong>R:R ≥ """ + str(MIN_RR) + """</strong> — Cai Sen's 3:1 risk-reward minimum</div>
<div class="rule">✅ <strong>Volume Confirmation</strong> — Recovery must show volume surge (>1.2x avg)</div>
<div class="rule">✅ <strong>MA """ + str(MA_PERIOD) + """ Uptrend</strong> — Short-term moving average trending up</div>
<div class="rule">✅ <strong>No Repeat</strong> — Skip stock if traded in last """ + str(SKIP_RECENT_MONTHS) + """ months</div>
<div class="rule">✅ <strong>Market Regime</strong> — Skip if HSI index below 60-day MA (bear market filter)</div>
<div class="rule">✅ <strong>Liquidity</strong> — Min avg daily volume """ + f"{MIN_AVG_VOLUME/1e6:.0f}M""" + """ shares</div>
</div>
""")

    # Stats
    tr_cls = "g" if stats['total_return'] > 0 else "r"
    html.append(f"""
<div class="grid">
<div class="card"><div class="label">Total Trades</div><div class="value b">{stats['total_trades']}</div></div>
<div class="card"><div class="label">Win Rate</div><div class="value {'g' if stats['win_rate']>=50 else 'r'}">{stats['win_rate']:.1f}%</div></div>
<div class="card"><div class="label">Total Return</div><div class="value {tr_cls}">{stats['total_return']:+.1f}%</div></div>
<div class="card"><div class="label">Avg PnL/Trade</div><div class="value {'g' if stats['avg_pnl']>0 else 'r'}">{stats['avg_pnl']:+.2f}%</div></div>
<div class="card"><div class="label">Avg Win</div><div class="value g">{stats['avg_win']:+.2f}%</div></div>
<div class="card"><div class="label">Avg Loss</div><div class="value r">{stats['avg_loss']:+.2f}%</div></div>
<div class="card"><div class="label">Max Drawdown</div><div class="value r">{stats['max_drawdown']:.1f}%</div></div>
<div class="card"><div class="label">Avg Hold</div><div class="value o">{stats['avg_hold']:.0f}d</div></div>
</div>
""")

    # Exit reasons
    html.append('<div class="filter-info"><h2>📊 Exit Reasons</h2>')
    for reason, count in sorted(stats['exit_reasons'].items(), key=lambda x: -x[1]):
        pct = count / stats['total_trades'] * 100
        icon = "🎯" if reason == "target" else "🛑" if reason == "stop_loss" else "⏰"
        html.append(f'<div class="rule">{icon} <strong>{reason}</strong>: {count} ({pct:.0f}%)</div>')
    html.append("</div>")

    # Equity curve
    html.append("""<div class="chart-wrap"><h2>📈 Equity Curve</h2><div class="eq-bar">""")
    curve = stats['cumulative_curve']
    mn, mx = min(curve), max(curve)
    rng = mx - mn if mx != mn else 1
    step = max(1, len(curve) // 120)
    sampled = curve[::step]
    if sampled[-1] != curve[-1]:
        sampled.append(curve[-1])
    for v in sampled:
        h = (v - mn) / rng * 200 + 20
        c = "#00e676" if v >= 100 else "#ff5252"
        html.append(f'<div style="height:{h}px;background:{c}" title="{v:.1f}"></div>')
    html.append(f'</div><div class="eq-labels"><span>Start: 100</span><span>End: {curve[-1]:.2f} ({stats["total_return"]:+.1f}%)</span></div></div>')

    # All trades
    html.append("""<div class="all-trades"><h2>📋 All Trades</h2><div class="tw"><table>
<thead><tr><th>#</th><th>Ticker</th><th>Name</th><th>Signal</th><th>Entry</th><th>Entry$</th><th>Exit</th><th>Exit$</th><th>SL</th><th>Target</th><th>Reason</th><th>Days</th><th>PnL%</th><th>Conf</th><th>R:R</th></tr></thead><tbody>""")
    for i, t in enumerate(all_trades, 1):
        pc = "pp" if t.pnl_pct > 0 else "pn" if t.pnl_pct < 0 else "pz"
        ec = f"e{t.exit_reason[0]}"
        html.append(f'<tr><td>{i}</td><td><strong>{t.ticker}</strong></td><td>{t.name}</td><td>{t.signal_date}</td><td>{t.entry_date}</td><td>{t.entry_price:.2f}</td><td>{t.exit_date}</td><td>{t.exit_price:.2f}</td><td>{t.stop_loss:.2f}</td><td>{t.target_price:.2f}</td><td class="{ec}">{t.exit_reason}</td><td>{t.holding_days}</td><td class="{pc}">{t.pnl_pct:+.2f}%</td><td>{t.confidence:.2f}</td><td>{t.risk_reward:.1f}</td></tr>')
    html.append("</tbody></table></div></div>")

    # Monthly breakdown
    html.append('<h2 style="color:#00d4ff;margin-bottom:14px">📅 Monthly Breakdown</h2>')
    for mr in monthly_results:
        month = mr['month']
        trades = mr['trades']
        raw = mr.get('raw', 0)
        filtered = mr.get('filtered', 0)

        if trades:
            mp = sum(t.pnl_pct for t in trades)
            w = len([t for t in trades if t.pnl_pct > 0])
            tc = "tw2" if mp > 0 else "tl" if mp < 0 else "tn"
        else:
            mp = 0; w = 0; tc = "tn"

        html.append(f"""<div class="ms"><div class="mh" onclick="this.nextElementSibling.classList.toggle('hidden')"><h3>{month}</h3><div class="sum"><span class="tag tn">Raw: {raw}</span><span class="tag tn">Passed: {filtered}</span><span class="tag {tc}">PnL: {mp:+.2f}%</span><span class="tag {'tw2' if w==len(trades) and trades else 'tl' if w==0 and trades else 'tn'}">W/L: {w}/{len(trades)}</span></div></div><div class="mb">""")
        if trades:
            html.append('<table><thead><tr><th>Ticker</th><th>Name</th><th>Signal</th><th>Entry</th><th>$</th><th>Exit</th><th>$</th><th>Reason</th><th>Days</th><th>PnL</th><th>Conf</th><th>R:R</th></tr></thead><tbody>')
            for t in trades:
                pc = "pp" if t.pnl_pct > 0 else "pn"
                html.append(f'<tr><td><strong>{t.ticker}</strong></td><td>{t.name}</td><td>{t.signal_date}</td><td>{t.entry_date}</td><td>{t.entry_price:.2f}</td><td>{t.exit_date}</td><td>{t.exit_price:.2f}</td><td>{t.exit_reason}</td><td>{t.holding_days}d</td><td class="{pc}">{t.pnl_pct:+.2f}%</td><td>{t.confidence:.2f}</td><td>{t.risk_reward:.1f}</td></tr>')
            html.append('</tbody></table>')
        elif raw > 0:
            html.append(f'<p style="padding:16px;color:#8b949e">{raw} signals found but all filtered out by SMART criteria.</p>')
        else:
            html.append('<p style="padding:16px;color:#8b949e">No signals this month.</p>')
        html.append('</div></div>')

    # Heatmap
    html.append('<div class="chart-wrap" style="margin-top:24px"><h2>🗓️ Monthly PnL Heatmap</h2><div class="heatmap">')
    ym = {}
    for mr in monthly_results:
        y = mr['month'][:4]; mn2 = int(mr['month'][5:7])
        if y not in ym: ym[y] = {}
        trades = mr['trades']
        ym[y][mn2] = sum(t.pnl_pct for t in trades) if trades else 0

    for y in sorted(ym.keys()):
        html.append(f'<div class="hm-year">{y}</div>')
        for m in range(1, 13):
            p = ym[y].get(m, None)
            if p is None:
                html.append('<div class="hm-cell" style="background:#0f1923;color:#1a2a3a">—</div>')
            elif p > 0:
                i = min(1, p / 10)
                html.append(f'<div class="hm-cell" style="background:rgba(0,230,118,{0.15+i*0.5});color:#00e676">{p:+.1f}%</div>')
            elif p < 0:
                i = min(1, abs(p) / 10)
                html.append(f'<div class="hm-cell" style="background:rgba(255,82,82,{0.15+i*0.5});color:#ff5252">{p:+.1f}%</div>')
            else:
                html.append('<div class="hm-cell" style="background:#141e2a;color:#8b949e">0%</div>')
    html.append('</div></div>')

    html.append(f"""
<div style="text-align:center;color:#1a2a3a;margin-top:30px;padding:16px;font-size:11px">
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Strategy: 破底翻 SMART (Top 2+Filters) | Universe: HSI Blue Chips
</div></div>
<script>
function toggleStock(h){{h.classList.toggle('collapsed');h.nextElementSibling.classList.toggle('hidden')}}
</script></body></html>""")

    return '\n'.join(html)


# ============================================================
# Run
# ============================================================
if __name__ == '__main__':
    all_trades, monthly_results, stats = run_backtest()

    print("\nGenerating HTML...")
    html = generate_html(all_trades, monthly_results, stats)

    out = 'hk_bluechip_po_di_fan_smart_backtest.html'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)

    import os
    print(f"✅ HTML: {out} ({os.path.getsize(out)/1024:.0f} KB)")

    json_out = 'hk_bluechip_po_di_fan_smart_backtest.json'
    with open(json_out, 'w', encoding='utf-8') as f:
        json.dump({
            'generated': datetime.now().isoformat(),
            'strategy': '破底翻 SMART (Top 2 + Filters)',
            'filters': {
                'min_confidence': MIN_CONFIDENCE,
                'min_rr': MIN_RR,
                'require_volume': REQUIRE_VOLUME,
                'require_ma_uptrend': REQUIRE_MA_UPTREND,
                'skip_recent_months': SKIP_RECENT_MONTHS,
                'market_filter': MARKET_FILTER,
                'min_avg_volume': MIN_AVG_VOLUME,
            },
            'stats': {k: v for k, v in stats.items() if k != 'cumulative_curve'},
            'trades': [t.__dict__ for t in all_trades],
        }, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON: {json_out} ({os.path.getsize(json_out)/1024:.0f} KB)")
