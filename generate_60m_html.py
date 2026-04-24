#!/usr/bin/env python3
"""
Combine 5 backtest JSON chunks into a single HTML report.
Usage: python generate_60m_html.py <output_html>
Reads: chunk_*.json files from workspace
"""

import json
import glob
import os
import sys
from datetime import datetime

def load_all_chunks():
    """Load and merge all chunk JSON files sorted by month."""
    workspace = '/root/.openclaw/workspace'
    all_data = []
    for f in sorted(glob.glob(os.path.join(workspace, 'backtest_60m_chunk_*.json'))):
        with open(f, 'r') as fh:
            data = json.load(fh)
            all_data.extend(data)
            print(f"Loaded {f}: {len(data)} months")
    all_data.sort(key=lambda x: x['month'])
    return all_data


def generate_html(data):
    """Generate HTML report from combined backtest data."""
    total_months = len(data)
    all_trades = []
    for m in data:
        all_trades.extend(m['trades'])

    total_trades = len(all_trades)
    winners = [t for t in all_trades if t['pnl_pct'] > 0]
    losers = [t for t in all_trades if t['pnl_pct'] <= 0]
    win_rate = len(winners) / total_trades * 100 if total_trades else 0
    avg_pnl = sum(t['pnl_pct'] for t in all_trades) / total_trades if total_trades else 0
    total_return = 1.0
    for t in all_trades:
        total_return *= (1 + t['pnl_pct'] / 100)
    total_return_pct = (total_return - 1) * 100

    # Best and worst trades
    best_trade = max(all_trades, key=lambda t: t['pnl_pct']) if all_trades else None
    worst_trade = min(all_trades, key=lambda t: t['pnl_pct']) if all_trades else None

    # Monthly returns
    monthly_returns = [(m['month'], m['avg_pnl']) for m in data]

    # Cumulative equity curve
    equity = [100]
    for m in data:
        for t in m['trades']:
            equity.append(equity[-1] * (1 + t['pnl_pct'] / 100))

    # Stock frequency
    stock_count = {}
    stock_pnl = {}
    for t in all_trades:
        sym = t['symbol']
        stock_count[sym] = stock_count.get(sym, 0) + 1
        stock_pnl[sym] = stock_pnl.get(sym, 0) + t['pnl_pct']
    top_stocks = sorted(stock_count.items(), key=lambda x: -x[1])[:15]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HK Blue Chip 60-Month Backtest — Cai Sen Analyzer</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f1117; color: #e4e4e7; line-height: 1.6; }}
.container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
h1 {{ font-size: 2em; color: #fbbf24; margin-bottom: 8px; }}
h2 {{ font-size: 1.4em; color: #60a5fa; margin: 30px 0 15px; border-bottom: 1px solid #2d3748; padding-bottom: 8px; }}
h3 {{ font-size: 1.1em; color: #a78bfa; margin: 15px 0 10px; }}
.subtitle {{ color: #9ca3af; margin-bottom: 20px; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
.stat-card {{ background: #1a1b23; border-radius: 12px; padding: 20px; border: 1px solid #2d3748; }}
.stat-label {{ font-size: 0.85em; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.5px; }}
.stat-value {{ font-size: 1.8em; font-weight: 700; margin-top: 5px; }}
.stat-value.positive {{ color: #34d399; }}
.stat-value.negative {{ color: #f87171; }}
.stat-value.neutral {{ color: #fbbf24; }}
table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
th {{ background: #1e1f2b; color: #9ca3af; padding: 10px 12px; text-align: left; font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.5px; position: sticky; top: 0; }}
td {{ padding: 10px 12px; border-bottom: 1px solid #1e1f2b; font-size: 0.9em; }}
tr:hover {{ background: #1a1b23; }}
.pnl-positive {{ color: #34d399; font-weight: 600; }}
.pnl-negative {{ color: #f87171; font-weight: 600; }}
.reason {{ font-size: 0.8em; color: #9ca3af; max-width: 400px; }}
.reason .star {{ color: #fbbf24; }}
.signal-tag {{ display: inline-block; background: #2d3748; color: #a78bfa; padding: 2px 8px; border-radius: 4px; font-size: 0.75em; margin: 2px; }}
.month-header {{ background: #1a1b23; }}
.month-header td {{ font-weight: 700; color: #fbbf24; font-size: 1em; }}
.equity-chart {{ background: #1a1b23; border-radius: 12px; padding: 20px; border: 1px solid #2d3748; margin: 20px 0; }}
.bar {{ display: inline-block; margin: 1px; border-radius: 2px; min-width: 8px; }}
.bar.up {{ background: #34d399; }}
.bar.down {{ background: #f87171; }}
.stock-freq {{ display: flex; flex-wrap: wrap; gap: 10px; }}
.stock-badge {{ background: #1e1f2b; border: 1px solid #2d3748; border-radius: 8px; padding: 8px 14px; }}
.stock-badge .count {{ color: #fbbf24; font-weight: 700; }}
.stock-badge .pnl {{ font-size: 0.85em; }}
.note {{ background: #1a1b23; border-left: 3px solid #fbbf24; padding: 12px 16px; margin: 10px 0; border-radius: 0 8px 8px 0; font-size: 0.9em; }}
footer {{ text-align: center; color: #6b7280; margin-top: 40px; padding: 20px; font-size: 0.85em; }}
</style>
</head>
<body>
<div class="container">
<h1>🇭🇰 HK Blue Chip 60-Month Backtest</h1>
<p class="subtitle">Cai Sen Technical Analysis · Best 2 Monthly Picks · Buy First Trading Day, Sell Last · {data[0]['month']} to {data[-1]['month']}</p>

<div class="stats-grid">
  <div class="stat-card">
    <div class="stat-label">Total Months</div>
    <div class="stat-value neutral">{total_months}</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Total Trades</div>
    <div class="stat-value neutral">{total_trades}</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Win Rate</div>
    <div class="stat-value {'positive' if win_rate > 50 else 'negative'}">{win_rate:.1f}%</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Avg Monthly P&L</div>
    <div class="stat-value {'positive' if avg_pnl > 0 else 'negative'}">{avg_pnl:+.2f}%</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Cumulative Return</div>
    <div class="stat-value {'positive' if total_return_pct > 0 else 'negative'}">{total_return_pct:+.1f}%</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Winners / Losers</div>
    <div class="stat-value neutral">{len(winners)} / {len(losers)}</div>
  </div>
</div>

<div class="stats-grid">
  <div class="stat-card">
    <div class="stat-label">Best Trade</div>
    <div class="stat-value positive">{best_trade['symbol']} {best_trade['pnl_pct']:+.1f}%</div>
    <div style="font-size:0.8em;color:#9ca3af">{best_trade['name']} ({best_trade['buy_date']})</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Worst Trade</div>
    <div class="stat-value negative">{worst_trade['symbol']} {worst_trade['pnl_pct']:+.1f}%</div>
    <div style="font-size:0.8em;color:#9ca3af">{worst_trade['name']} ({worst_trade['buy_date']})</div>
  </div>
</div>

<h2>📈 Monthly Returns</h2>
<div class="equity-chart">
"""
    # Monthly bar chart
    max_abs = max(abs(r) for _, r in monthly_returns) if monthly_returns else 1
    for month, ret in monthly_returns:
        bar_height = int(abs(ret) / max_abs * 80) if max_abs > 0 else 0
        bar_class = 'up' if ret > 0 else 'down'
        html += f'<div class="bar {bar_class}" style="height:{max(bar_height,3)}px" title="{month}: {ret:+.2f}%"></div>\n'

    html += """</div>

<h2>📊 Stock Selection Frequency (Top 15)</h2>
<div class="stock-freq">
"""
    for sym, count in top_stocks:
        pnl = stock_pnl.get(sym, 0)
        pnl_class = 'pnl-positive' if pnl > 0 else 'pnl-negative'
        name = data[0]['trades'][0].get('name', sym) if data else sym
        # Find name from any trade
        for m in data:
            for t in m['trades']:
                if t['symbol'] == sym:
                    name = t['name']
                    break
        html += f'<div class="stock-badge"><strong>{sym}</strong> {name}<br><span class="count">×{count}</span> <span class="pnl {pnl_class}">Σ{pnl:+.1f}%</span></div>\n'

    html += """</div>

<h2>📋 Full Transaction Log</h2>
<div class="note">Buy at <strong>Open</strong> on the first trading day of each month. Sell at <strong>Close</strong> on the last trading day. Top 2 picks by Cai Sen technical score.</div>

<table>
<thead>
<tr><th>#</th><th>Month</th><th>Stock</th><th>Name</th><th>Buy Date</th><th>Buy Price</th><th>Sell Date</th><th>Sell Price</th><th>P&L %</th><th>Score</th><th>Reason / Signals</th></tr>
</thead>
<tbody>
"""

    trade_num = 0
    for m in data:
        for t in m['trades']:
            trade_num += 1
            pnl_class = 'pnl-positive' if t['pnl_pct'] > 0 else 'pnl-negative'

            # Build signal tags
            signal_html = ''
            for sig in t.get('signals', []):
                star = '★ ' if sig.get('confidence', 0) >= 0.65 else ''
                signal_html += f'<span class="signal-tag">{star}{sig["type"]}</span> '

            # Build reason with star highlighting
            reason = t.get('reason', '')
            reason = reason.replace('★ ', '<span class="star">★ </span>')

            html += f"""<tr>
  <td>{trade_num}</td>
  <td>{m['month']}</td>
  <td><strong>{t['symbol']}</strong></td>
  <td>{t['name']}</td>
  <td>{t['buy_date']}</td>
  <td>{t['buy_price']:.2f}</td>
  <td>{t['sell_date']}</td>
  <td>{t['sell_price']:.2f}</td>
  <td class="{pnl_class}">{t['pnl_pct']:+.2f}%</td>
  <td>{t['score']}</td>
  <td class="reason">{signal_html}<br>{reason}</td>
</tr>
"""

    html += """</tbody>
</table>

<h2>📅 Monthly Detail</h2>
"""

    for m in data:
        month_pnl_class = 'pnl-positive' if m['avg_pnl'] > 0 else 'pnl-negative'
        html += f"""
<h3>{m['month']} — Avg P&L: <span class="{month_pnl_class}">{m['avg_pnl']:+.2f}%</span> ({m['first_trading_day']} → {m['last_trading_day']})</h3>
<table>
<thead><tr><th>Stock</th><th>Buy@</th><th>Sell@</th><th>P&L</th><th>Score</th><th>Reason</th></tr></thead>
<tbody>
"""
        for t in m['trades']:
            pnl_c = 'pnl-positive' if t['pnl_pct'] > 0 else 'pnl-negative'
            reason = t.get('reason', '').replace('★ ', '<span class="star">★ </span>')
            html += f'<tr><td><strong>{t["symbol"]}</strong> {t["name"]}</td><td>{t["buy_date"]} @ {t["buy_price"]:.2f}</td><td>{t["sell_date"]} @ {t["sell_price"]:.2f}</td><td class="{pnl_c}">{t["pnl_pct"]:+.2f}%</td><td>{t["score"]}</td><td class="reason">{reason}</td></tr>\n'
        html += "</tbody></table>\n"

    html += f"""
<footer>
  Generated by Cai Sen Analyzer v3.0 · {datetime.now().strftime('%Y-%m-%d %H:%M')} ·
  Data source: Yahoo Finance (yfinance) · 84 HK Blue Chips analyzed monthly
</footer>
</div>
</body>
</html>"""
    return html


if __name__ == '__main__':
    output = sys.argv[1] if len(sys.argv) > 1 else '/root/.openclaw/workspace/backtest_60m_report.html'
    data = load_all_chunks()
    if not data:
        print("No chunk files found!")
        sys.exit(1)
    html = generate_html(data)
    with open(output, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"HTML report saved to {output}")
    print(f"Total months: {len(data)}, Total trades: {sum(len(m['trades']) for m in data)}")
