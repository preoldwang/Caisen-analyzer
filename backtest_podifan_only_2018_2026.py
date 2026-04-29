#!/usr/bin/env python3
"""
破底翻-ONLY Backtest — HSI Blue Chips (Apr 2018 – Mar 2026)
============================================================
Pure 破底翻 signal, Top 2 per month, no additional smart filters.
Uses local hk_blue_chip_8y_prices.json data (no yfinance dependency).

Entry: next-day Open
Exit:  stop loss (4% below bottom) / target (neckline + distance) / 30-day max hold
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime
from dataclasses import dataclass, field
from typing import List
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# Config
# ============================================================
BACKTEST_START = "2018-04-01"
BACKTEST_END   = "2026-03-31"
TOP_N = 2
MAX_HOLD_DAYS = 30
DATA_FILE = "hk_blue_chip_8y_prices.json"

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

# ============================================================
# 破底翻 Detector (simplified, no smart filters)
# ============================================================
def detect_po_di_fan(ticker, name, df, scan_end_date):
    """
    Detect 破底翻 signals for a given stock up to scan_end_date.
    
    破底翻 pattern:
    1. Stock forms a bottom (min close in lookback window)
    2. Recovers above neckline (70th percentile of recovery)
    3. Breaks below the bottom (破底)
    4. Recovers back above neckline (翻回) → BUY signal
    
    Uses CLOSE prices for bottom/neckline (consistent with proven smart backtest).
    Uses LOW prices for breakdown detection.
    """
    signals = []
    if df is None or len(df) < 120:
        return signals

    mask = df.index <= scan_end_date
    data = df[mask].copy()
    if len(data) < 120:
        return signals

    open_prices = data['Open'].values
    close = data['Close'].values
    low_prices = data['Low'].values
    high_prices = data['High'].values
    volume = data['Volume'].values
    dates = data.index

    target_month = pd.Timestamp(scan_end_date).month
    target_year = pd.Timestamp(scan_end_date).year

    # Pre-compute 20-day moving average
    ma_series = pd.Series(close).rolling(20).mean().values

    for lookback in [60, 90, 120]:
        if len(close) < lookback + 30:
            continue

        for end_idx in range(lookback + 30, len(close)):
            signal_date = pd.Timestamp(dates[end_idx - 1])
            if signal_date.month != target_month or signal_date.year != target_year:
                continue

            # Use CLOSE prices for bottom/neckline (proven approach)
            segment = close[end_idx - lookback:end_idx]
            seg_vol = volume[end_idx - lookback:end_idx]

            # 1. Find bottom (min CLOSE in lookback window)
            min_price = np.min(segment)
            min_idx = np.argmin(segment)

            # Bottom must be in middle of window, not at edges
            if min_idx < 5 or min_idx > len(segment) - 10:
                continue

            # 2. Neckline: 70th percentile of recovery close prices after bottom
            recovery = segment[min_idx:]
            if len(recovery) < 3:
                continue
            neckline = np.percentile(recovery, 70)

            # Neckline must be meaningfully above bottom (>3%)
            if neckline < min_price * 1.03:
                continue

            # Previous high for target calculation
            pre_high = np.max(segment[:min_idx]) if min_idx > 10 else neckline

            # 3. Check for breakdown (破底) in recent 30 bars using LOW prices
            check_low = low_prices[end_idx - 30:end_idx]
            if len(check_low) < 20:
                continue

            broke_below = False
            broke_below_idx = -1
            for i, price in enumerate(check_low):
                if price < min_price * 0.98:  # 2% below bottom
                    broke_below = True
                    broke_below_idx = i
                    break

            if not broke_below or broke_below_idx >= len(check_low) - 5:
                continue

            # 4. Recovery check (翻回颈线) - use CLOSE prices
            check_close = close[end_idx - 30:end_idx]
            after_break = check_close[broke_below_idx:]
            if len(after_break) < 2:
                continue
            recovered = any(p > neckline for p in after_break[-5:])

            if not recovered:
                continue

            # 5. Volume confirmation
            recent_vol = np.mean(volume[end_idx - 5:end_idx]) if end_idx >= 5 else 0
            avg_vol = np.mean(seg_vol) if np.mean(seg_vol) > 0 else 1
            vol_confirm = recent_vol > avg_vol * 1.2

            # 6. Entry / Stop / Target
            if end_idx >= len(open_prices):
                continue
            entry = open_prices[end_idx]  # next-day Open (realistic execution)
            stop_loss = min_price * 0.96
            distance = neckline - min_price
            target_1 = max(neckline + distance, pre_high)

            risk = entry - stop_loss
            reward = target_1 - entry
            rr = reward / risk if risk > 0 else 0

            # 7. Confidence scoring
            confidence = 0.55
            if vol_confirm:
                confidence += 0.12
            if broke_below_idx > 5:
                confidence += 0.10
            if rr >= 3:
                confidence += 0.10
            if rr >= 2:
                confidence += 0.05
            # RSI oversold bonus
            if end_idx >= 14:
                rsi_delta = np.diff(close[end_idx - 15:end_idx])
                gains = np.mean(np.where(rsi_delta > 0, rsi_delta, 0))
                losses = np.mean(np.where(rsi_delta < 0, -rsi_delta, 0))
                rs = gains / max(losses, 1e-10)
                rsi = 100 - (100 / (1 + rs))
                if rsi < 40:
                    confidence += 0.08

            if rr < 1.0:
                continue

            desc = f"破底翻: {min_price:.2f}→{neckline:.2f} ({distance/min_price*100:.1f}%)"
            if vol_confirm:
                desc += " 放量"

            signals.append(Signal(
                ticker=ticker, name=name,
                signal_date=signal_date.strftime('%Y-%m-%d'),
                entry_price=round(entry, 2),
                stop_loss=round(stop_loss, 2),
                target_price=round(target_1, 2),
                neckline=round(neckline, 2),
                bottom_price=round(min_price, 2),
                confidence=round(min(confidence, 0.95), 2),
                risk_reward=round(rr, 2),
                volume_confirmed=vol_confirm,
                description=desc
            ))

    # Deduplicate by date, keep best
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
    )


# ============================================================
# Main Backtest
# ============================================================
def run_backtest():
    print("=" * 70)
    print("破底翻-ONLY Backtest — HSI Blue Chips")
    print(f"Period: {BACKTEST_START} to {BACKTEST_END}")
    print(f"Strategy: Top {TOP_N} 破底翻 per month (pure, no smart filters)")
    print("=" * 70)

    # Load data
    print(f"\nLoading {DATA_FILE}...")
    with open(DATA_FILE, 'r') as f:
        raw = json.load(f)

    stock_data = {}
    for ticker, info in raw['stocks'].items():
        df = pd.DataFrame(info['data'])
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        stock_data[ticker] = {'name': info['name'], 'df': df}

    print(f"Loaded {len(stock_data)} stocks")

    months = pd.date_range(start=BACKTEST_START, end=BACKTEST_END, freq='MS')
    print(f"Months to scan: {len(months)}\n")

    all_trades = []
    monthly_results = []
    recent_tickers = set()

    for month_start in months:
        month_end = (month_start + pd.offsets.MonthEnd(0)).strftime('%Y-%m-%d')
        month_label = month_start.strftime('%Y-%m')

        # Collect raw signals from all stocks
        raw_signals = []
        for ticker, info in stock_data.items():
            sigs = detect_po_di_fan(ticker, info['name'], info['df'], month_end)
            raw_signals.extend(sigs)

        # Deduplicate per stock (keep best)
        seen = set()
        unique = []
        for s in raw_signals:
            if s.ticker not in seen:
                unique.append(s)
                seen.add(s.ticker)
        raw_signals = unique

        # Sort by confidence * R:R
        raw_signals.sort(key=lambda s: -(s.confidence * s.risk_reward))

        # Skip recently traded stocks
        available = [s for s in raw_signals if s.ticker not in recent_tickers]

        # Pick top N
        picks = available[:TOP_N]

        if not picks:
            monthly_results.append({
                'month': month_label, 'raw': len(raw_signals),
                'trades': [], 'picks': []
            })
            print(f"  {month_label}: {len(raw_signals)} signals, 0 trades")
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

        monthly_results.append({
            'month': month_label, 'raw': len(raw_signals),
            'trades': month_trades, 'picks': picks
        })

        pnl_str = f"{sum(t.pnl_pct for t in month_trades):+.2f}%" if month_trades else "n/a"
        print(f"  {month_label}: {len(raw_signals)} signals → {len(month_trades)} trades, PnL={pnl_str}")
        for t in month_trades:
            print(f"    ✅ {t.ticker} {t.name}: {t.entry_date}@{t.entry_price} → {t.exit_date}@{t.exit_price} ({t.exit_reason}) {t.pnl_pct:+.2f}%")

        # Decay recent tickers
        if len(monthly_results) > 2:
            old = monthly_results[-3]
            for t in old.get('trades', []):
                recent_tickers.discard(t.ticker)

    # ============================================================
    # Stats
    # ============================================================
    stats = compute_stats(all_trades, monthly_results)
    print_stats(stats)
    return all_trades, monthly_results, stats


def compute_stats(all_trades, monthly_results):
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
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        if dd > max_dd:
            max_dd = dd

    exit_reasons = {}
    for t in all_trades:
        exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

    avg_hold = np.mean([t.holding_days for t in all_trades]) if all_trades else 0

    # Yearly breakdown
    yearly = {}
    for t in all_trades:
        y = t.entry_date[:4]
        if y not in yearly:
            yearly[y] = {'trades': 0, 'wins': 0, 'pnl_sum': 0}
        yearly[y]['trades'] += 1
        yearly[y]['pnl_sum'] += t.pnl_pct
        if t.pnl_pct > 0:
            yearly[y]['wins'] += 1

    return {
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
        'yearly': yearly,
    }


def print_stats(stats):
    print("\n" + "=" * 70)
    print("BACKTEST SUMMARY — 破底翻-ONLY Top 2")
    print("=" * 70)
    print(f"Total trades:    {stats['total_trades']}")
    print(f"Winners:         {stats['winning_trades']} ({stats['win_rate']:.1f}%)")
    print(f"Losers:          {stats['losing_trades']} ({100-stats['win_rate']:.1f}%)")
    print(f"Avg PnL/trade:   {stats['avg_pnl']:+.2f}%")
    print(f"Avg Win:         {stats['avg_win']:+.2f}%")
    print(f"Avg Loss:        {stats['avg_loss']:+.2f}%")
    print(f"Total Return:    {stats['total_return']:+.2f}%")
    print(f"Max Drawdown:    {stats['max_drawdown']:.2f}%")
    print(f"Avg Hold:        {stats['avg_hold']:.0f} days")
    print(f"Exit reasons:    {stats['exit_reasons']}")
    print()
    print("Yearly breakdown:")
    for y in sorted(stats['yearly'].keys()):
        d = stats['yearly'][y]
        wr = d['wins']/d['trades']*100 if d['trades'] > 0 else 0
        print(f"  {y}: {d['trades']} trades, {d['wins']} wins ({wr:.0f}%), PnL={d['pnl_sum']:+.2f}%")


# ============================================================
# HTML Generator
# ============================================================
def generate_html(all_trades, monthly_results, stats):
    html = []
    html.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>破底翻-ONLY Backtest — HSI Blue Chips (Apr 2018 – Mar 2026)</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#080c14;color:#c9d1d9;min-height:100vh}}
.container{{max-width:1400px;margin:0 auto;padding:20px}}
h1{{text-align:center;color:#00d4ff;font-size:28px;margin:20px 0 8px}}
.subtitle{{text-align:center;color:#8b949e;font-size:14px;margin-bottom:30px}}
.subtitle span{{margin:0 8px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px}}
.card{{background:#0f1923;border:1px solid #1a2a3a;border-radius:10px;padding:16px;text-align:center}}
.card .label{{color:#8b949e;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}}
.card .value{{font-size:24px;font-weight:700}}
.g{{color:#00e676}}.r{{color:#ff5252}}.b{{color:#00d4ff}}.o{{color:#ff9100}}.p{{color:#bb86fc}}
.section{{background:#0f1923;border:1px solid #1a2a3a;border-radius:10px;padding:20px;margin-bottom:20px}}
.section h2{{color:#00d4ff;margin-bottom:14px;font-size:18px}}
.chart-wrap{{background:#0f1923;border:1px solid #1a2a3a;border-radius:10px;padding:20px;margin-bottom:20px}}
.eq-bar{{display:flex;align-items:flex-end;height:200px;gap:1px;border-bottom:1px solid #1a2a3a;padding-bottom:2px}}
.eq-bar div{{flex:1;border-radius:2px 2px 0 0;min-width:2px}}
.eq-labels{{display:flex;justify-content:space-between;color:#8b949e;font-size:11px;padding-top:6px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#080c14;color:#8b949e;padding:8px 10px;text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.5px;position:sticky;top:0}}
td{{padding:7px 10px;border-bottom:1px solid #141e2a}}
tr:hover{{background:#0f1923}}
.pp{{color:#00e676;font-weight:600}}.pn{{color:#ff5252;font-weight:600}}
.ms{{background:#0f1923;border:1px solid #1a2a3a;border-radius:8px;margin-bottom:10px;overflow:hidden}}
.mh{{padding:12px 16px;background:#0a1018;cursor:pointer;display:flex;justify-content:space-between;align-items:center}}
.mh:hover{{background:#141e2a}}
.mh h3{{color:#00d4ff;font-size:15px}}
.sum{{display:flex;gap:10px;font-size:12px}}
.tag{{padding:2px 8px;border-radius:4px;font-size:11px}}
.tw2{{color:#00e676;background:#002200}}.tl{{color:#ff5252;background:#220000}}.tn{{color:#8b949e;background:#141e2a}}
.mb{{padding:0}}.mb.hidden{{display:none}}
.heatmap{{display:grid;grid-template-columns:repeat(12,1fr);gap:3px;margin-top:12px}}
.hm-cell{{padding:7px 4px;border-radius:4px;text-align:center;font-size:11px;font-weight:600}}
.hm-year{{text-align:center;color:#8b949e;font-weight:bold;padding:7px 0;font-size:13px}}
.filter-info{{background:#0f1923;border:1px solid #1a2a3a;border-radius:10px;padding:18px;margin-bottom:20px}}
.filter-info .rule{{display:flex;align-items:center;gap:8px;margin-bottom:4px;color:#8b949e;font-size:13px}}
.filter-info .rule strong{{color:#c9d1d9}}
@media(max-width:768px){{.grid{{grid-template-columns:repeat(2,1fr)}}.card .value{{font-size:18px}}}}
</style>
</head>
<body>
<div class="container">
<h1>🧠 破底翻-ONLY Backtest — HSI Blue Chips</h1>
<p class="subtitle"><span>📅 Apr 2018 → Mar 2026</span><span>|</span><span>🔬 破底翻 Top 2 (Pure)</span><span>|</span><span>🎯 {stats['total_trades']} trades</span></p>
""")

    # Strategy description
    html.append("""
<div class="filter-info">
<h2>📋 Strategy: 破底翻-ONLY (Pure)</h2>
<div class="rule">📌 <strong>Signal:</strong> 破底翻 — stock breaks below bottom then recovers above neckline</div>
<div class="rule">📌 <strong>Selection:</strong> Top 2 per month by confidence × R:R score</div>
<div class="rule">📌 <strong>Entry:</strong> Next-day Open price (realistic execution)</div>
<div class="rule">📌 <strong>Stop Loss:</strong> 4% below pattern bottom</div>
<div class="rule">📌 <strong>Target:</strong> Neckline + pattern distance (or prior high)</div>
<div class="rule">📌 <strong>Max Hold:</strong> 30 trading days</div>
<div class="rule">📌 <strong>Cooldown:</strong> Skip stock if traded in prior 2 months</div>
</div>
""")

    # Stats cards
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
    html.append('<div class="section"><h2>📊 Exit Reasons</h2>')
    for reason, count in sorted(stats['exit_reasons'].items(), key=lambda x: -x[1]):
        pct = count / stats['total_trades'] * 100
        icon = "🎯" if reason == "target" else "🛑" if reason == "stop_loss" else "⏰"
        html.append(f'<div class="rule">{icon} <strong>{reason}</strong>: {count} ({pct:.0f}%)</div>')
    html.append("</div>")

    # Yearly breakdown table
    html.append("""<div class="section"><h2>📅 Yearly Breakdown</h2>
<table><thead><tr><th>Year</th><th>Trades</th><th>Wins</th><th>Win Rate</th><th>Total PnL</th><th>Avg PnL</th></tr></thead><tbody>""")
    for y in sorted(stats['yearly'].keys()):
        d = stats['yearly'][y]
        wr = d['wins']/d['trades']*100 if d['trades'] > 0 else 0
        avg = d['pnl_sum']/d['trades'] if d['trades'] > 0 else 0
        pc = "g" if d['pnl_sum'] > 0 else "r"
        html.append(f'<tr><td><strong>{y}</strong></td><td>{d["trades"]}</td><td>{d["wins"]}</td><td>{wr:.0f}%</td><td class="{pc}">{d["pnl_sum"]:+.1f}%</td><td class="{pc}">{avg:+.2f}%</td></tr>')
    html.append("</tbody></table></div>")

    # Equity curve
    html.append('<div class="chart-wrap"><h2>📈 Equity Curve (Starting = 100)</h2><div class="eq-bar">')
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

    # All trades table
    html.append("""<div class="section"><h2>📋 All Transactions</h2>
<div style="max-height:700px;overflow-y:auto">
<table><thead><tr><th>#</th><th>Ticker</th><th>Name</th><th>Signal Date</th><th>Entry Date</th><th>Entry $</th><th>Exit Date</th><th>Exit $</th><th>Stop Loss</th><th>Target</th><th>Exit Reason</th><th>Days</th><th>PnL %</th><th>Conf</th><th>R:R</th></tr></thead><tbody>""")
    for i, t in enumerate(all_trades, 1):
        pc = "pp" if t.pnl_pct > 0 else "pn"
        html.append(f'<tr><td>{i}</td><td><strong>{t.ticker}</strong></td><td>{t.name}</td><td>{t.signal_date}</td><td>{t.entry_date}</td><td>{t.entry_price:.2f}</td><td>{t.exit_date}</td><td>{t.exit_price:.2f}</td><td>{t.stop_loss:.2f}</td><td>{t.target_price:.2f}</td><td>{t.exit_reason}</td><td>{t.holding_days}</td><td class="{pc}">{t.pnl_pct:+.2f}%</td><td>{t.confidence:.2f}</td><td>{t.risk_reward:.1f}</td></tr>')
    html.append("</tbody></table></div></div>")

    # Monthly breakdown (collapsible)
    html.append('<h2 style="color:#00d4ff;margin-bottom:14px">📅 Monthly Breakdown</h2>')
    for mr in monthly_results:
        month = mr['month']
        trades = mr['trades']
        raw = mr.get('raw', 0)

        if trades:
            mp = sum(t.pnl_pct for t in trades)
            w = len([t for t in trades if t.pnl_pct > 0])
            tc = "tw2" if mp > 0 else "tl" if mp < 0 else "tn"
        else:
            mp = 0; w = 0; tc = "tn"

        html.append(f"""<div class="ms"><div class="mh" onclick="this.nextElementSibling.classList.toggle('hidden')"><h3>{month}</h3><div class="sum"><span class="tag tn">Signals: {raw}</span><span class="tag {tc}">PnL: {mp:+.2f}%</span><span class="tag {'tw2' if w==len(trades) and trades else 'tl' if w==0 and trades else 'tn'}">W/L: {w}/{len(trades)}</span></div></div><div class="mb hidden">""")
        if trades:
            html.append('<table><thead><tr><th>Ticker</th><th>Name</th><th>Signal</th><th>Entry</th><th>$</th><th>Exit</th><th>$</th><th>Reason</th><th>Days</th><th>PnL</th><th>Conf</th><th>R:R</th></tr></thead><tbody>')
            for t in trades:
                pc = "pp" if t.pnl_pct > 0 else "pn"
                html.append(f'<tr><td><strong>{t.ticker}</strong></td><td>{t.name}</td><td>{t.signal_date}</td><td>{t.entry_date}</td><td>{t.entry_price:.2f}</td><td>{t.exit_date}</td><td>{t.exit_price:.2f}</td><td>{t.exit_reason}</td><td>{t.holding_days}d</td><td class="{pc}">{t.pnl_pct:+.2f}%</td><td>{t.confidence:.2f}</td><td>{t.risk_reward:.1f}</td></tr>')
            html.append('</tbody></table>')
        else:
            html.append(f'<p style="padding:14px;color:#8b949e">No 破底翻 signals this month.</p>')
        html.append('</div></div>')

    # Heatmap
    html.append('<div class="chart-wrap" style="margin-top:20px"><h2>🗓️ Monthly PnL Heatmap</h2><div class="heatmap">')
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
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Strategy: 破底翻-ONLY (Top 2, Pure) | Universe: HSI Blue Chips (75 stocks) | Period: Apr 2018 – Mar 2026
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

    print("\nGenerating HTML report...")
    html = generate_html(all_trades, monthly_results, stats)

    out_file = 'backtest_podifan_only_2018_2026.html'
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(html)

    import os
    size = os.path.getsize(out_file) / 1024
    print(f"✅ HTML saved: {out_file} ({size:.0f} KB)")

    # Also save JSON
    json_out = 'backtest_podifan_only_2018_2026.json'
    with open(json_out, 'w', encoding='utf-8') as f:
        json.dump({
            'generated': datetime.now().isoformat(),
            'strategy': '破底翻-ONLY (Top 2, Pure)',
            'period': f'{BACKTEST_START} to {BACKTEST_END}',
            'stats': {k: v for k, v in stats.items() if k != 'cumulative_curve'},
            'trades': [t.__dict__ for t in all_trades],
        }, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON saved: {json_out} ({os.path.getsize(json_out)/1024:.0f} KB)")
