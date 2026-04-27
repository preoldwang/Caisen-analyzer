#!/usr/bin/env python3
"""
破底翻 (Bottom Breakdown & Recovery) Backtest
=============================================
Strategy: Pick top 2 破底翻 signals each month from Jan 2022 to Mar 2026
Universe: All HSI Blue Chip stocks
Data: Unadjusted daily prices from hk_blue_chip_8y_prices.json
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Tuple
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# Config
# ============================================================
BACKTEST_START = "2022-01-01"
BACKTEST_END = "2026-03-31"
TOP_N = 2  # Top picks per month
MAX_HOLD_DAYS = 30  # Max holding period per trade
RISK_PER_TRADE_PCT = 5.0  # Risk 5% per trade (Cai Sen's rule)

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
    target_price_2: float
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
    exit_reason: str  # "target", "stop_loss", "max_hold", "end_of_data"
    holding_days: int
    pnl_pct: float
    pnl_amount: float
    confidence: float
    risk_reward: float

# ============================================================
# 破底翻 Detector (simplified from cai_sen_analyzer.py)
# ============================================================
def detect_po_di_fan(ticker: str, name: str, df: pd.DataFrame, scan_end_date: str) -> List[Signal]:
    """
    Detect 破底翻 signals up to scan_end_date.
    Returns signals where signal_date is in the month of scan_end_date.
    """
    signals = []
    if df is None or len(df) < 90:
        return signals

    # Filter to data before scan_end_date
    mask = df.index <= scan_end_date
    data = df[mask].copy()
    if len(data) < 90:
        return signals

    close = data['Close'].values
    high = data['High'].values
    low = data['Low'].values
    volume = data['Volume'].values
    dates = data.index

    # Target month for signal dates
    target_month = pd.Timestamp(scan_end_date).month
    target_year = pd.Timestamp(scan_end_date).year

    for lookback in [60, 90, 120]:
        if len(close) < lookback + 30:
            continue

        # Scan from lookback+30 to end
        for end_idx in range(lookback + 30, len(close)):
            signal_date = pd.Timestamp(dates[end_idx - 1])
            # Only want signals in our target month
            if signal_date.month != target_month or signal_date.year != target_year:
                continue

            segment = close[end_idx - lookback:end_idx]
            seg_low = low[end_idx - lookback:end_idx]
            seg_vol = volume[end_idx - lookback:end_idx]
            seg_dates = dates[end_idx - lookback:end_idx]

            # Find bottom region
            min_price = np.min(segment)
            min_idx = np.argmin(segment)

            # Neckline = 70th percentile of recovery region after bottom
            if min_idx > 5 and min_idx < len(segment) - 10:
                recovery_region = segment[min_idx:]
                if len(recovery_region) > 3:
                    neckline = np.percentile(recovery_region, 70)
                else:
                    continue
            else:
                continue

            # Previous high before bottom
            pre_high = np.max(segment[:min_idx]) if min_idx > 10 else neckline

            # Check if price broke below bottom then recovered above neckline
            check_window = close[end_idx - 30:end_idx]
            check_low = low[end_idx - 30:end_idx]
            if len(check_window) < 20:
                continue

            # Break below detection
            broke_below = False
            broke_below_idx = -1
            for i, price in enumerate(check_low):
                if price < min_price * 0.98:
                    broke_below = True
                    broke_below_idx = i
                    break

            if not broke_below or broke_below_idx >= len(check_window) - 5:
                continue

            # Recovery detection
            after_break = check_window[broke_below_idx:]
            recovered = any(p > neckline for p in after_break[-5:])
            if not recovered:
                continue

            # Volume confirmation
            recent_vol = volume[end_idx - 5:end_idx]
            avg_vol = np.mean(seg_vol) if np.mean(seg_vol) > 0 else 1
            vol_confirm = np.mean(recent_vol) > avg_vol * 1.2

            # Entry at neckline, stop at bottom - 3%
            entry = neckline
            stop_loss = min_price * 0.97
            distance = neckline - min_price
            target_1 = max(neckline + distance, pre_high)
            target_2 = neckline + distance * 1.618

            risk = entry - stop_loss
            reward = target_1 - entry
            rr = reward / risk if risk > 0 else 0

            # Confidence score
            confidence = 0.5
            if vol_confirm:
                confidence += 0.2
            if rr >= 3:
                confidence += 0.15
            if broke_below_idx > 5:
                confidence += 0.15

            if confidence >= 0.5 and rr >= 1.5:
                signals.append(Signal(
                    ticker=ticker,
                    name=name,
                    signal_date=signal_date.strftime('%Y-%m-%d'),
                    entry_price=round(entry, 2),
                    stop_loss=round(stop_loss, 2),
                    target_price=round(target_1, 2),
                    target_price_2=round(target_2, 2),
                    neckline=round(neckline, 2),
                    bottom_price=round(min_price, 2),
                    confidence=round(min(confidence, 1.0), 2),
                    risk_reward=round(rr, 2),
                    volume_confirmed=vol_confirm,
                    description=f"破底翻: 底部{min_price:.2f}→颈线{neckline:.2f} {'(放量)' if vol_confirm else ''}"
                ))

    # Deduplicate (same ticker, same month, keep best)
    if signals:
        signals.sort(key=lambda s: (-s.confidence, -s.risk_reward))
        deduped = []
        seen_dates = set()
        for s in signals:
            key = s.signal_date
            if key not in seen_dates:
                deduped.append(s)
                seen_dates.add(key)
        signals = deduped[:5]  # Keep top 5 per stock per month

    return signals

# ============================================================
# Trade Simulator
# ============================================================
def simulate_trade(signal: Signal, price_data: pd.DataFrame) -> Trade:
    """Simulate a trade from entry to exit."""
    if price_data is None or price_data.empty:
        return Trade(
            ticker=signal.ticker, name=signal.name,
            signal_date=signal.signal_date,
            entry_date=signal.signal_date, entry_price=signal.entry_price,
            exit_date=signal.signal_date, exit_price=signal.entry_price,
            stop_loss=signal.stop_loss, target_price=signal.target_price,
            exit_reason="no_data", holding_days=0,
            pnl_pct=0, pnl_amount=0,
            confidence=signal.confidence, risk_reward=signal.risk_reward
        )

    entry_date = pd.Timestamp(signal.signal_date)
    # Find next trading day after signal
    future_data = price_data[price_data.index > entry_date]
    if future_data.empty:
        return Trade(
            ticker=signal.ticker, name=signal.name,
            signal_date=signal.signal_date,
            entry_date=signal.signal_date, entry_price=signal.entry_price,
            exit_date=signal.signal_date, exit_price=signal.entry_price,
            stop_loss=signal.stop_loss, target_price=signal.target_price,
            exit_reason="no_future_data", holding_days=0,
            pnl_pct=0, pnl_amount=0,
            confidence=signal.confidence, risk_reward=signal.risk_reward
        )

    entry_price = signal.entry_price
    stop_loss = signal.stop_loss
    target = signal.target_price
    entry_dt = future_data.index[0]  # First trading day after signal

    # Simulate day by day
    exit_date = None
    exit_price = None
    exit_reason = "max_hold"

    for i, (dt, row) in enumerate(future_data.iterrows()):
        if i >= MAX_HOLD_DAYS:
            exit_date = dt
            exit_price = row['Close']
            exit_reason = "max_hold"
            break

        # Check stop loss (hit during the day)
        if row['Low'] <= stop_loss:
            exit_date = dt
            exit_price = stop_loss
            exit_reason = "stop_loss"
            break

        # Check target (hit during the day)
        if row['High'] >= target:
            exit_date = dt
            exit_price = target
            exit_reason = "target"
            break

    if exit_date is None:
        # Use last available data
        last_dt = future_data.index[-1]
        last_price = future_data.iloc[-1]['Close']
        exit_date = last_dt
        exit_price = last_price
        exit_reason = "end_of_data"

    holding_days = (exit_date - entry_dt).days
    pnl_pct = (exit_price - entry_price) / entry_price * 100
    pnl_amount = exit_price - entry_price

    return Trade(
        ticker=signal.ticker,
        name=signal.name,
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
        pnl_amount=round(pnl_amount, 2),
        confidence=signal.confidence,
        risk_reward=signal.risk_reward
    )

# ============================================================
# Main Backtest
# ============================================================
def run_backtest():
    print("=" * 70)
    print("破底翻 Backtest — HSI Blue Chips")
    print(f"Period: {BACKTEST_START} to {BACKTEST_END}")
    print(f"Strategy: Top {TOP_N} 破底翻 signals per month")
    print("=" * 70)

    # Load price data
    print("\nLoading price data...")
    with open('hk_blue_chip_8y_prices.json', 'r') as f:
        raw = json.load(f)

    # Convert to DataFrames
    stock_data = {}
    for ticker, info in raw['stocks'].items():
        records = info['data']
        df = pd.DataFrame(records)
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        stock_data[ticker] = {'name': info['name'], 'df': df}

    print(f"Loaded {len(stock_data)} stocks")

    # Generate month list
    months = pd.date_range(start=BACKTEST_START, end=BACKTEST_END, freq='MS')
    print(f"Backtest months: {len(months)} ({months[0].strftime('%Y-%m')} to {months[-1].strftime('%Y-%m')})")

    # Run month by month
    all_signals = []
    all_trades = []
    monthly_results = []

    for month_start in months:
        month_end = (month_start + pd.offsets.MonthEnd(0)).strftime('%Y-%m-%d')
        month_label = month_start.strftime('%Y-%m')
        print(f"\n--- {month_label} ---")

        # Scan all stocks for 破底翻 signals
        month_signals = []
        for ticker, info in stock_data.items():
            df = info['df']
            signals = detect_po_di_fan(ticker, info['name'], df, month_end)
            month_signals.extend(signals)

        if not month_signals:
            print(f"  No signals found")
            monthly_results.append({
                'month': month_label,
                'signals': 0,
                'trades': 0,
                'picks': [],
                'trades_executed': []
            })
            continue

        # Sort by confidence * risk_reward (best first)
        month_signals.sort(key=lambda s: -(s.confidence * s.risk_reward))

        # Deduplicate: max 1 signal per stock per month
        seen_tickers = set()
        unique_signals = []
        for s in month_signals:
            if s.ticker not in seen_tickers:
                unique_signals.append(s)
                seen_tickers.add(s.ticker)

        # Pick top N
        picks = unique_signals[:TOP_N]
        print(f"  Found {len(month_signals)} signals → Top {len(picks)} picks:")
        for p in picks:
            print(f"    {p.ticker} {p.name}: entry={p.entry_price}, SL={p.stop_loss}, target={p.target_price}, conf={p.confidence}, R:R={p.risk_reward}")

        # Simulate trades
        month_trades = []
        for signal in picks:
            df = stock_data[signal.ticker]['df']
            trade = simulate_trade(signal, df)
            month_trades.append(trade)
            all_trades.append(trade)
            print(f"    → {trade.ticker}: entry {trade.entry_date}@{trade.entry_price} → exit {trade.exit_date}@{trade.exit_price} ({trade.exit_reason}) PnL={trade.pnl_pct:+.2f}%")

        all_signals.extend(picks)
        monthly_results.append({
            'month': month_label,
            'signals': len(month_signals),
            'trades': len(month_trades),
            'picks': picks,
            'trades_executed': month_trades
        })

    # ============================================================
    # Compute Summary Stats
    # ============================================================
    print("\n" + "=" * 70)
    print("BACKTEST SUMMARY")
    print("=" * 70)

    total_trades = len(all_trades)
    winning_trades = [t for t in all_trades if t.pnl_pct > 0]
    losing_trades = [t for t in all_trades if t.pnl_pct <= 0]
    win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0

    avg_pnl = np.mean([t.pnl_pct for t in all_trades]) if all_trades else 0
    total_pnl = sum([t.pnl_pct for t in all_trades])
    avg_win = np.mean([t.pnl_pct for t in winning_trades]) if winning_trades else 0
    avg_loss = np.mean([t.pnl_pct for t in losing_trades]) if losing_trades else 0
    avg_hold = np.mean([t.holding_days for t in all_trades]) if all_trades else 0

    # Cumulative return (assuming equal position sizing)
    cumulative = 100
    cumulative_curve = [100]
    for t in all_trades:
        cumulative *= (1 + t.pnl_pct / 100)
        cumulative_curve.append(cumulative)
    total_return = cumulative - 100

    # Max drawdown
    peak = cumulative_curve[0]
    max_dd = 0
    for v in cumulative_curve:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # Exit reason breakdown
    exit_reasons = {}
    for t in all_trades:
        exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

    # Monthly win/loss
    monthly_pnl = {}
    for t in all_trades:
        m = t.signal_date[:7]
        if m not in monthly_pnl:
            monthly_pnl[m] = []
        monthly_pnl[m].append(t.pnl_pct)

    print(f"Total trades: {total_trades}")
    print(f"Winners: {len(winning_trades)} ({win_rate:.1f}%)")
    print(f"Losers: {len(losing_trades)} ({100-win_rate:.1f}%)")
    print(f"Avg PnL: {avg_pnl:+.2f}%")
    print(f"Avg Win: {avg_win:+.2f}%")
    print(f"Avg Loss: {avg_loss:+.2f}%")
    print(f"Total Return: {total_return:+.2f}%")
    print(f"Max Drawdown: {max_dd:.2f}%")
    print(f"Avg Hold: {avg_hold:.0f} days")
    print(f"Exit reasons: {exit_reasons}")

    return all_trades, monthly_results, {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'avg_pnl': avg_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'total_return': total_return,
        'max_drawdown': max_dd,
        'avg_hold': avg_hold,
        'exit_reasons': exit_reasons,
        'cumulative_curve': cumulative_curve,
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
    }

# ============================================================
# HTML Generator
# ============================================================
def generate_html(all_trades, monthly_results, stats):
    html = []
    html.append("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>破底翻 Backtest — HSI Blue Chips (Jan 2022 - Mar 2026)</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0e17; color: #c9d1d9; }
.container { max-width: 1400px; margin: 0 auto; padding: 20px; }
h1 { text-align: center; color: #ff6b35; font-size: 32px; margin: 20px 0 8px; }
.subtitle { text-align: center; color: #8b949e; font-size: 14px; margin-bottom: 30px; }
.subtitle span { margin: 0 8px; }

/* Stats Cards */
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 30px; }
.stat-card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; text-align: center; }
.stat-card .label { color: #8b949e; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
.stat-card .value { font-size: 28px; font-weight: 700; }
.stat-card .value.green { color: #3fb950; }
.stat-card .value.red { color: #f85149; }
.stat-card .value.blue { color: #58a6ff; }
.stat-card .value.orange { color: #ff6b35; }

/* Equity Chart */
.chart-container { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 24px; margin-bottom: 30px; }
.chart-container h2 { color: #ff6b35; margin-bottom: 16px; }
canvas { width: 100%; height: 300px; }

/* Monthly Breakdown */
.month-section { background: #161b22; border: 1px solid #30363d; border-radius: 12px; margin-bottom: 16px; overflow: hidden; }
.month-header { padding: 16px 20px; background: #21262d; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }
.month-header:hover { background: #30363d; }
.month-header h3 { color: #58a6ff; font-size: 18px; }
.month-header .summary { display: flex; gap: 16px; font-size: 13px; }
.month-header .summary .tag { padding: 2px 8px; border-radius: 4px; }
.month-header .summary .win { background: #0d2818; color: #3fb950; }
.month-header .summary .loss { background: #2d1013; color: #f85149; }
.month-header .summary .neutral { background: #1c2128; color: #8b949e; }
.month-body { padding: 0; }
.month-body.hidden { display: none; }

/* Trade Table */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #0d1117; color: #8b949e; padding: 10px 14px; text-align: left; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; position: sticky; top: 0; }
td { padding: 10px 14px; border-bottom: 1px solid #21262d; }
tr:hover { background: #1c2128; }
.pnl-pos { color: #3fb950; font-weight: 600; }
.pnl-neg { color: #f85149; font-weight: 600; }
.pnl-zero { color: #8b949e; }
.exit-target { color: #3fb950; }
.exit-stop { color: #f85149; }
.exit-hold { color: #f0883e; }
.exit-other { color: #8b949e; }
.signal-info { color: #8b949e; font-size: 11px; }

/* All Trades Table */
.all-trades { background: #161b22; border: 1px solid #30363d; border-radius: 12px; overflow: hidden; margin-bottom: 30px; }
.all-trades h2 { padding: 20px; color: #ff6b35; }
.all-trades .table-wrap { max-height: 600px; overflow-y: auto; }

/* Strategy Info */
.strategy-info { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 24px; margin-bottom: 30px; }
.strategy-info h2 { color: #ff6b35; margin-bottom: 12px; }
.strategy-info p { color: #8b949e; line-height: 1.6; margin-bottom: 8px; }
.strategy-info strong { color: #c9d1d9; }
.strategy-info .rule { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.strategy-info .rule .icon { font-size: 18px; }

/* Filters */
.filter-bar { padding: 16px 20px; background: #0d1117; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 20px; border-radius: 8px; }
.filter-bar input, .filter-bar select { background: #161b22; border: 1px solid #30363d; color: #c9d1d9; padding: 8px 12px; border-radius: 6px; font-size: 14px; }
.filter-bar input:focus, .filter-bar select:focus { outline: none; border-color: #58a6ff; }

/* Responsive */
@media (max-width: 768px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .stat-card .value { font-size: 22px; }
  table { font-size: 11px; }
  th, td { padding: 6px 8px; }
}
</style>
</head>
<body>
<div class="container">
<h1>🇭🇰 破底翻 Backtest — HSI Blue Chips</h1>
<p class="subtitle">
<span>📅 Jan 2022 → Mar 2026</span>
<span>|</span>
<span>📊 Top 2 picks/month</span>
<span>|</span>
<span>🎯 """ + str(stats['total_trades']) + """ trades</span>
</p>
""")

    # Strategy Info
    html.append("""
<div class="strategy-info">
<h2>📖 破底翻 Strategy (Cai Sen Method)</h2>
<p><strong>Core Concept:</strong> Stock price breaks below a support bottom, then recovers above the neckline.
This signals that major players (主力) are absorbing selling pressure and about to push prices higher.</p>
<div class="rule"><span class="icon">📉</span> <strong>Step 1 — 破底:</strong> Price breaks below the recent bottom support level</div>
<div class="rule"><span class="icon">🔄</span> <strong>Step 2 — 翻回:</strong> Price recovers back above the neckline (70th percentile of post-bottom recovery)</div>
<div class="rule"><span class="icon">📊</span> <strong>Confirmation:</strong> Volume surge on recovery (>1.2x avg) strengthens the signal</div>
<div class="rule"><span class="icon">🎯</span> <strong>Target:</strong> Distance from bottom to neckline, projected upward (蔡森 formula)</div>
<div class="rule"><span class="icon">🛑</span> <strong>Stop Loss:</strong> Bottom price × 0.97 (3% below bottom)</div>
<div class="rule"><span class="icon">⏰</span> <strong>Max Hold:</strong> 30 trading days</div>
<p style="margin-top: 12px;"><strong>蔡森金句:</strong> "破底翻大都会越过前高"</p>
</div>
""")

    # Stats Cards
    total_return_class = "green" if stats['total_return'] > 0 else "red"
    html.append(f"""
<div class="stats-grid">
<div class="stat-card">
<div class="label">Total Trades</div>
<div class="value blue">{stats['total_trades']}</div>
</div>
<div class="stat-card">
<div class="label">Win Rate</div>
<div class="value {'green' if stats['win_rate'] >= 50 else 'red'}">{stats['win_rate']:.1f}%</div>
</div>
<div class="stat-card">
<div class="label">Total Return</div>
<div class="value {total_return_class}">{stats['total_return']:+.1f}%</div>
</div>
<div class="stat-card">
<div class="label">Avg PnL / Trade</div>
<div class="value {'green' if stats['avg_pnl'] > 0 else 'red'}">{stats['avg_pnl']:+.2f}%</div>
</div>
<div class="stat-card">
<div class="label">Avg Win</div>
<div class="value green">{stats['avg_win']:+.2f}%</div>
</div>
<div class="stat-card">
<div class="label">Avg Loss</div>
<div class="value red">{stats['avg_loss']:+.2f}%</div>
</div>
<div class="stat-card">
<div class="label">Max Drawdown</div>
<div class="value red">{stats['max_drawdown']:.1f}%</div>
</div>
<div class="stat-card">
<div class="label">Avg Hold Days</div>
<div class="value orange">{stats['avg_hold']:.0f}d</div>
</div>
</div>
""")

    # Exit Reasons
    html.append("""
<div class="strategy-info">
<h2>📊 Exit Reason Breakdown</h2>
""")
    for reason, count in sorted(stats['exit_reasons'].items(), key=lambda x: -x[1]):
        pct = count / stats['total_trades'] * 100
        label = {"target": "🎯 Target Hit", "stop_loss": "🛑 Stop Loss", "max_hold": "⏰ Max Hold", "end_of_data": "📅 End of Data", "no_data": "❌ No Data", "no_future_data": "❌ No Future Data"}.get(reason, reason)
        html.append(f'<div class="rule"><span class="icon">{"🟢" if reason == "target" else "🔴" if reason == "stop_loss" else "🟡"}</span> {label}: <strong>{count}</strong> ({pct:.0f}%)</div>')
    html.append("</div>")

    # Equity Curve (simple CSS-based bar chart)
    html.append("""
<div class="chart-container">
<h2>📈 Equity Curve (Starting Capital: 100)</h2>
<div style="display: flex; align-items: flex-end; height: 250px; gap: 2px; padding: 20px 0; border-bottom: 1px solid #30363d;">
""")
    curve = stats['cumulative_curve']
    max_val = max(curve)
    min_val = min(curve)
    val_range = max_val - min_val if max_val != min_val else 1

    # Sample every N points to fit
    step = max(1, len(curve) // 120)
    sampled = curve[::step]
    if sampled[-1] != curve[-1]:
        sampled.append(curve[-1])

    for v in sampled:
        height = (v - min_val) / val_range * 230 + 20
        color = "#3fb950" if v >= 100 else "#f85149"
        html.append(f'<div style="width: 100%; flex: 1; height: {height}px; background: {color}; border-radius: 2px 2px 0 0; position: relative;" title="{v:.1f}"></div>')

    html.append(f"""
</div>
<div style="display: flex; justify-content: space-between; color: #8b949e; font-size: 12px; padding-top: 8px;">
<span>Start: 100.00</span>
<span>End: {curve[-1]:.2f} ({stats['total_return']:+.1f}%)</span>
</div>
</div>
""")

    # All Trades Table
    html.append("""
<div class="all-trades">
<h2>📋 All Trades</h2>
<div class="table-wrap">
<table>
<thead>
<tr>
<th>#</th><th>Ticker</th><th>Name</th><th>Signal Date</th><th>Entry Date</th><th>Entry Price</th>
<th>Exit Date</th><th>Exit Price</th><th>Stop Loss</th><th>Target</th><th>Exit Reason</th>
<th>Hold (d)</th><th>PnL %</th><th>Confidence</th><th>R:R</th>
</tr>
</thead>
<tbody>
""")
    for i, t in enumerate(all_trades, 1):
        pnl_class = "pnl-pos" if t.pnl_pct > 0 else "pnl-neg" if t.pnl_pct < 0 else "pnl-zero"
        exit_class = f"exit-{t.exit_reason.split('_')[0]}"
        html.append(f"""<tr>
<td>{i}</td><td><strong>{t.ticker}</strong></td><td>{t.name}</td>
<td>{t.signal_date}</td><td>{t.entry_date}</td><td>{t.entry_price:.2f}</td>
<td>{t.exit_date}</td><td>{t.exit_price:.2f}</td><td>{t.stop_loss:.2f}</td><td>{t.target_price:.2f}</td>
<td class="{exit_class}">{t.exit_reason}</td><td>{t.holding_days}</td>
<td class="{pnl_class}">{t.pnl_pct:+.2f}%</td><td>{t.confidence:.2f}</td><td>{t.risk_reward:.1f}</td>
</tr>""")
    html.append("</tbody></table></div></div>")

    # Monthly Breakdown
    html.append('<h2 style="color: #ff6b35; margin-bottom: 16px;">📅 Monthly Breakdown</h2>')

    for mr in monthly_results:
        month = mr['month']
        trades = mr['trades_executed']
        num_signals = mr['signals']

        if trades:
            month_pnl = sum(t.pnl_pct for t in trades)
            wins = len([t for t in trades if t.pnl_pct > 0])
            pnl_class = "green" if month_pnl > 0 else "red"
        else:
            month_pnl = 0
            wins = 0
            pnl_class = "neutral"

        tag_class = "win" if month_pnl > 0 else "loss" if month_pnl < 0 else "neutral"

        html.append(f"""
<div class="month-section">
<div class="month-header" onclick="this.nextElementSibling.classList.toggle('hidden')">
<h3>{month}</h3>
<div class="summary">
<span class="tag neutral">Signals: {num_signals}</span>
<span class="tag {tag_class}">PnL: {month_pnl:+.2f}%</span>
<span class="tag {'win' if wins == len(trades) and trades else 'loss' if wins == 0 and trades else 'neutral'}">W/L: {wins}/{len(trades)}</span>
</div>
</div>
<div class="month-body">
""")

        if trades:
            html.append("""<table>
<thead><tr><th>Ticker</th><th>Name</th><th>Signal</th><th>Entry</th><th>Entry Price</th><th>Exit</th><th>Exit Price</th><th>Reason</th><th>Hold</th><th>PnL</th><th>Conf</th><th>R:R</th></tr></thead>
<tbody>""")
            for t in trades:
                pnl_class = "pnl-pos" if t.pnl_pct > 0 else "pnl-neg"
                html.append(f"""<tr>
<td><strong>{t.ticker}</strong></td><td>{t.name}</td><td>{t.signal_date}</td>
<td>{t.entry_date}</td><td>{t.entry_price:.2f}</td>
<td>{t.exit_date}</td><td>{t.exit_price:.2f}</td>
<td>{t.exit_reason}</td><td>{t.holding_days}d</td>
<td class="{pnl_class}">{t.pnl_pct:+.2f}%</td><td>{t.confidence:.2f}</td><td>{t.risk_reward:.1f}</td>
</tr>""")
            html.append("</tbody></table>")
        else:
            html.append('<p style="padding: 20px; color: #8b949e;">No 破底翻 signals this month.</p>')

        html.append("</div></div>")

    # Monthly Performance Heatmap
    html.append("""
<div class="chart-container" style="margin-top: 30px;">
<h2>🗓️ Monthly PnL Heatmap</h2>
<div style="display: grid; grid-template-columns: repeat(12, 1fr); gap: 4px; margin-top: 16px;">
""")

    # Group by year
    yearly_months = {}
    for mr in monthly_results:
        year = mr['month'][:4]
        month_num = int(mr['month'][5:7])
        if year not in yearly_months:
            yearly_months[year] = {}
        trades = mr['trades_executed']
        pnl = sum(t.pnl_pct for t in trades) if trades else 0
        yearly_months[year][month_num] = pnl

    for year in sorted(yearly_months.keys()):
        html.append(f'<div style="text-align: center; color: #8b949e; font-weight: bold; padding: 8px 0;">{year}</div>')
        for m in range(1, 13):
            pnl = yearly_months[year].get(m, None)
            if pnl is None:
                html.append('<div style="background: #161b22; padding: 8px; border-radius: 4px; text-align: center; color: #30363d;">—</div>')
            else:
                if pnl > 0:
                    intensity = min(1, pnl / 10)
                    bg = f"rgba(63, 185, 80, {0.2 + intensity * 0.6})"
                    color = "#3fb950"
                elif pnl < 0:
                    intensity = min(1, abs(pnl) / 10)
                    bg = f"rgba(248, 81, 73, {0.2 + intensity * 0.6})"
                    color = "#f85149"
                else:
                    bg = "#21262d"
                    color = "#8b949e"
                html.append(f'<div style="background: {bg}; padding: 8px; border-radius: 4px; text-align: center; color: {color}; font-weight: 600;">{pnl:+.1f}%</div>')

    html.append("</div></div>")

    # Footer
    html.append(f"""
<div style="text-align: center; color: #30363d; margin-top: 40px; padding: 20px; font-size: 12px;">
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Strategy: 破底翻 (Cai Sen) | Universe: HSI Blue Chips | Data: Unadjusted Prices
</div>
</div>

<script>
function toggleStock(header) {{
    header.classList.toggle('collapsed');
    header.nextElementSibling.classList.toggle('hidden');
}}
</script>
</body></html>""")

    return '\n'.join(html)


# ============================================================
# Run
# ============================================================
if __name__ == '__main__':
    all_trades, monthly_results, stats = run_backtest()

    print("\nGenerating HTML report...")
    html = generate_html(all_trades, monthly_results, stats)

    output_path = 'hk_bluechip_po_di_fan_backtest.html'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    import os
    size = os.path.getsize(output_path)
    print(f"\n✅ HTML saved: {output_path} ({size/1024:.0f} KB)")

    # Also save JSON
    json_data = {
        'generated': datetime.now().isoformat(),
        'strategy': '破底翻 (Bottom Breakdown & Recovery)',
        'period': f'{BACKTEST_START} to {BACKTEST_END}',
        'universe': 'HSI Blue Chips',
        'stats': {k: v for k, v in stats.items() if k != 'cumulative_curve'},
        'trades': [t.__dict__ for t in all_trades],
    }
    json_path = 'hk_bluechip_po_di_fan_backtest.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON saved: {json_path} ({os.path.getsize(json_path)/1024:.0f} KB)")
