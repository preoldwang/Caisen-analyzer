#!/usr/bin/env python3
"""Merge all agent backtest JSON files into one combined HTML report."""

import json
import os
import numpy as np
from datetime import datetime

BASE = '/root/.openclaw/workspace/Caisen-analyzer'

# Load all JSON files in order
files = [
    'backtest_agent1_2024Q3Q4.json',
    'backtest_agent2_2024Q4_2025Q1.json',
    'backtest_agent3_2025Q2Q3.json',
    'backtest_agent4_2025Q3Q4.json',
    'backtest_agent5_2025Q4_2026Q1.json',
]

all_results = []
for f in files:
    path = os.path.join(BASE, f)
    with open(path) as fp:
        data = json.load(fp)
        all_results.extend(data)

# Save merged JSON
merged_json = os.path.join(BASE, 'backtest_20months_combined.json')
with open(merged_json, 'w', encoding='utf-8') as fp:
    json.dump(all_results, fp, ensure_ascii=False, indent=2)
print(f"Merged JSON: {merged_json} ({len(all_results)} months)")

# Generate combined HTML
html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HK Blue Chip 20-Month Backtest — Cai Sen Analysis</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#e0e0e0;line-height:1.6}
.container{max-width:1500px;margin:0 auto;padding:20px}
h1{text-align:center;color:#00d4ff;font-size:2.2em;margin-bottom:5px}
.subtitle{text-align:center;color:#888;margin-bottom:30px;font-size:0.95em}
.summary-box{background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #0f3460;border-radius:12px;padding:25px;margin-bottom:30px}
.summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:15px;margin-top:15px}
.summary-item{text-align:center}
.summary-item .label{color:#888;font-size:0.8em;text-transform:uppercase;letter-spacing:1px}
.summary-item .value{font-size:1.8em;font-weight:bold;margin-top:5px}
.positive{color:#00ff88}.negative{color:#ff4444}.neutral{color:#ffaa00}
.methodology{background:#111;border:1px solid #222;border-radius:10px;padding:20px;margin-bottom:30px}
.methodology h3{color:#00d4ff;margin-bottom:10px}
.methodology p,.methodology li{color:#888;font-size:0.9em;margin-bottom:6px}
.methodology ul{padding-left:20px}
.month-card{background:#111;border:1px solid #222;border-radius:10px;margin-bottom:20px;overflow:hidden}
.month-header{background:linear-gradient(90deg,#1a1a2e,#0f3460);padding:15px 20px;display:flex;justify-content:space-between;align-items:center}
.month-header h2{color:#00d4ff;font-size:1.15em}
.month-header .dates{color:#888;font-size:0.85em}
.month-header .pnl{font-size:1.1em;font-weight:bold}
.month-body{padding:20px}
table{width:100%;border-collapse:collapse;margin-top:10px}
th{background:#1a1a2e;color:#00d4ff;padding:10px 12px;text-align:left;font-size:0.8em;text-transform:uppercase;letter-spacing:.5px;white-space:nowrap}
td{padding:10px 12px;border-bottom:1px solid #1a1a1a;font-size:0.88em}
tr:hover{background:#1a1a1a}
.stock-name{color:#aaa;font-size:0.82em}
.reason{color:#888;font-size:0.78em;max-width:420px;line-height:1.4}
.reason .signal{color:#ffaa00}
.buy-price{color:#00d4ff}.sell-price{color:#ffaa00}
.pnl-positive{color:#00ff88;font-weight:bold}.pnl-negative{color:#ff4444;font-weight:bold}
.bar-chart{background:#111;border:1px solid #222;border-radius:10px;padding:20px;margin-bottom:30px}
.bar-wrap{display:flex;align-items:flex-end;height:160px;gap:4px;padding:10px 0;overflow-x:auto}
.bar{display:flex;flex-direction:column;align-items:center;min-width:36px;border-radius:4px 4px 0 0;font-size:0.65em;padding-top:4px;cursor:default;transition:opacity .2s}
.bar:hover{opacity:.8}
.bar .lbl{color:#666;font-size:0.9em;margin-top:3px}
.quarter-table{margin-bottom:30px}
.quarter-table th{position:sticky;top:0;z-index:1}
.cumulative{background:linear-gradient(135deg,#0f3460,#1a1a2e);border:1px solid #00d4ff;border-radius:12px;padding:25px;margin-bottom:30px;text-align:center}
.cumulative .big{font-size:3em;font-weight:bold}
.footer{text-align:center;color:#555;margin-top:40px;padding:20px;border-top:1px solid #222}
</style>
</head>
<body>
<div class="container">
<h1>📊 HK Blue Chip 20-Month Backtest</h1>
<p class="subtitle">蔡森技術分析 (Cai Sen Technical Analysis) · Top 3 Picks per Month · Aug 2024 → Mar 2026</p>
"""

# Collect all trades
all_trades = []
monthly_data = []
for r in all_results:
    month = r.get('month', '?')
    first_day = r.get('first_trading_day', '?')
    last_day = r.get('last_trading_day', '?')
    trades = r.get('trades', [])
    avg_pnl = r.get('avg_pnl')
    month_trades = []
    for t in trades:
        pnl = t.get('pnl_pct')
        all_trades.append({'month': month, **t})
        month_trades.append(pnl)
    monthly_data.append({
        'month': month,
        'first_day': first_day,
        'last_day': last_day,
        'trades': trades,
        'avg_pnl': avg_pnl,
        'pnls': month_trades
    })

# Stats
total_trades = len(all_trades)
pnls = [t['pnl_pct'] for t in all_trades if t.get('pnl_pct') is not None]
winners = len([p for p in pnls if p > 0])
losers = len([p for p in pnls if p < 0])
avg_pnl = np.mean(pnls) if pnls else 0
total_return = 1.0
for p in pnls:
    total_return *= (1 + p / 100)
total_return_pct = (total_return - 1) * 100
win_rate = (winners / len(pnls) * 100) if pnls else 0
max_win = max(pnls) if pnls else 0
max_loss = min(pnls) if pnls else 0
median_pnl = np.median(pnls) if pnls else 0
std_pnl = np.std(pnls) if pnls else 0

# Best/worst trades
best_trade = max(all_trades, key=lambda x: x.get('pnl_pct', -999)) if all_trades else {}
worst_trade = min(all_trades, key=lambda x: x.get('pnl_pct', 999)) if all_trades else {}

# Monthly win/loss streaks
month_avgs = [m['avg_pnl'] for m in monthly_data if m['avg_pnl'] is not None]
winning_months = len([m for m in month_avgs if m > 0])
losing_months = len([m for m in month_avgs if m <= 0])

# Quarterly summary
quarters = {
    'Q3 2024': [m for m in monthly_data if m['month'].startswith('2024-0') and m['month'] in ['2024-08','2024-09']],
    'Q4 2024': [m for m in monthly_data if m['month'] in ['2024-10','2024-11','2024-12']],
    'Q1 2025': [m for m in monthly_data if m['month'] in ['2025-01','2025-02','2025-03']],
    'Q2 2025': [m for m in monthly_data if m['month'] in ['2025-04','2025-05','2025-06']],
    'Q3 2025': [m for m in monthly_data if m['month'] in ['2025-07','2025-08','2025-09']],
    'Q4 2025': [m for m in monthly_data if m['month'] in ['2025-10','2025-11','2025-12']],
    'Q1 2026': [m for m in monthly_data if m['month'] in ['2026-01','2026-02','2026-03']],
}

pnl_class = 'positive' if avg_pnl > 0 else 'negative'
ret_class = 'positive' if total_return_pct > 0 else 'negative'

html += f"""
<div class="summary-box">
<h2 style="color:#e0e0e0">📋 Overall Summary (20 Months · 60 Trades)</h2>
<div class="summary-grid">
<div class="summary-item"><div class="label">Total Trades</div><div class="value">{total_trades}</div></div>
<div class="summary-item"><div class="label">Winners / Losers</div><div class="value"><span class="positive">{winners}</span> / <span class="negative">{losers}</span></div></div>
<div class="summary-item"><div class="label">Win Rate</div><div class="value {'positive' if win_rate>=50 else 'negative'}">{win_rate:.1f}%</div></div>
<div class="summary-item"><div class="label">Avg P&L / Trade</div><div class="value {pnl_class}">{avg_pnl:+.2f}%</div></div>
<div class="summary-item"><div class="label">Median P&L</div><div class="value {'positive' if median_pnl>0 else 'negative'}">{median_pnl:+.2f}%</div></div>
<div class="summary-item"><div class="label">Cumulative Return</div><div class="value {ret_class}">{total_return_pct:+.2f}%</div></div>
<div class="summary-item"><div class="label">Best Trade</div><div class="value positive">{max_win:+.2f}%</div></div>
<div class="summary-item"><div class="label">Worst Trade</div><div class="value negative">{max_loss:+.2f}%</div></div>
<div class="summary-item"><div class="label">Winning Months</div><div class="value {'positive' if winning_months>losing_months else 'neutral'}">{winning_months}</div></div>
<div class="summary-item"><div class="label">Losing Months</div><div class="value {'negative' if losing_months>winning_months else 'neutral'}">{losing_months}</div></div>
</div>
</div>

<div class="cumulative">
<div style="color:#888;font-size:0.9em;margin-bottom:10px">📈 Cumulative Return (20 Months)</div>
<div class="big {ret_class}">{total_return_pct:+.2f}%</div>
<div style="color:#888;font-size:0.85em;margin-top:8px">
Best: {best_trade.get('symbol','')} ({best_trade.get('name','')}) in {best_trade.get('month','')} → {max_win:+.2f}% &nbsp;|&nbsp;
Worst: {worst_trade.get('symbol','')} ({worst_trade.get('name','')}) in {worst_trade.get('month','')} → {max_loss:+.2f}%
</div>
</div>
"""

# Methodology
html += """
<div class="methodology">
<h3>📐 Methodology</h3>
<ul>
<li><strong>Universe:</strong> 83 HK blue chip stocks (Hang Seng Index constituents + major HK-listed stocks)</li>
<li><strong>Analysis:</strong> Cai Sen (蔡森) volume-price methodology — pattern recognition (破底翻, W底, 颈线突破, 量先价行, 量价背离, 回踩支撑), trend alignment (MA20/60/120), volume confirmation</li>
<li><strong>Selection:</strong> Top 3 stocks by composite signal score on the first trading day of each month</li>
<li><strong>Execution:</strong> Buy at market open on first trading day → Sell at close on last trading day</li>
<li><strong>Data:</strong> Yahoo Finance RAW (unadjusted) prices — matching investing.com historical data</li>
<li><strong>Period:</strong> August 2024 → March 2026 (20 months, 60 trades)</li>
</ul>
<p style="margin-top:10px;color:#ffaa00">⚠️ Disclaimer: This backtest is for research purposes only. Past performance does not guarantee future results. Not investment advice.</p>
</div>
"""

# Monthly bar chart
html += '<div class="bar-chart"><h3 style="color:#00d4ff;margin-bottom:15px">📊 Monthly Average P&L</h3><div class="bar-wrap">'
for m in monthly_data:
    pnl = m['avg_pnl'] or 0
    h = max(5, abs(pnl) * 6)
    color = '#00ff88' if pnl > 0 else '#ff4444' if pnl < 0 else '#888'
    lbl = m['month'][-2:]  # just month number
    html += f'<div class="bar" style="height:{h}px;background:{color}" title="{m["month"]}: {pnl:+.2f}%"><span style="color:#ddd">{pnl:+.1f}%</span><span class="lbl">{lbl}</span></div>'
html += '</div></div>'

# Quarterly summary table
html += '<div class="quarter-table"><h3 style="color:#00d4ff;margin-bottom:15px">📅 Quarterly Summary</h3><table><tr><th>Quarter</th><th>Months</th><th>Trades</th><th>Winners</th><th>Avg P&L</th><th>Cumulative</th></tr>'
for qname, qmonths in quarters.items():
    if not qmonths:
        continue
    q_trades = []
    for m in qmonths:
        for t in m['trades']:
            if t.get('pnl_pct') is not None:
                q_trades.append(t['pnl_pct'])
    if not q_trades:
        continue
    q_avg = np.mean(q_trades)
    q_cum = 1.0
    for p in q_trades:
        q_cum *= (1 + p / 100)
    q_cum_pct = (q_cum - 1) * 100
    q_winners = len([p for p in q_trades if p > 0])
    cls = 'positive' if q_avg > 0 else 'negative'
    html += f'<tr><td><strong>{qname}</strong></td><td>{len(qmonths)}</td><td>{len(q_trades)}</td><td>{q_winners}/{len(q_trades)}</td><td class="{cls}">{q_avg:+.2f}%</td><td class="{cls}">{q_cum_pct:+.2f}%</td></tr>'
html += '</table></div>'

# Monthly details
for m in monthly_data:
    month = m['month']
    first_day = m['first_day']
    last_day = m['last_day']
    avg = m['avg_pnl']
    
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
<th>#</th><th>Stock</th><th>Buy Date</th><th>Buy (HKD)</th><th>Sell Date</th><th>Sell (HKD)</th><th>P&L</th><th>Score</th><th>Signals & Reasoning</th>
</tr>
"""
    
    for i, t in enumerate(m['trades']):
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
        reason_html = reason.replace('★', '<span class="signal">★</span>')
        score = t.get('score', '?')
        signals = t.get('signals', [])
        sig_types = ', '.join([s.get('type','') for s in signals])
        
        html += f"""<tr>
<td>{i+1}</td>
<td><strong>{t['symbol']}</strong><br><span class="stock-name">{t.get('name','')}</span></td>
<td>{t.get('buy_date','?')}</td>
<td class="buy-price">{buy_p}</td>
<td>{t.get('sell_date','?')}</td>
<td class="sell-price">{sell_p}</td>
<td class="{pnl_cls}">{pnl_display}</td>
<td>{score}</td>
<td class="reason"><strong>[{sig_types}]</strong><br>{reason_html}</td>
</tr>"""
    
    html += "</table></div></div>"

html += f"""
<div class="footer">
<p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')} · Cai Sen Technical Analysis Tool v3.0</p>
<p>蔡森技術分析 · 基于量价关系的股票型态识别 · RAW (unadjusted) price data from Yahoo Finance</p>
<p style="margin-top:8px;color:#ffaa00">⚠️ 仅供研究用途，不构成投资建议 · Past performance does not guarantee future results</p>
</div>
</div>
</body>
</html>"""

output_html = os.path.join(BASE, 'backtest_20months_combined.html')
with open(output_html, 'w', encoding='utf-8') as fp:
    fp.write(html)

print(f"Combined HTML: {output_html}")
print(f"\n{'='*60}")
print("📊 COMBINED 20-MONTH BACKTEST SUMMARY")
print(f"{'='*60}")
print(f"Total trades:      {total_trades}")
print(f"Winners:           {winners} ({win_rate:.1f}%)")
print(f"Losers:            {losers}")
print(f"Avg P&L/trade:     {avg_pnl:+.2f}%")
print(f"Median P&L:        {median_pnl:+.2f}%")
print(f"Std Dev:           {std_pnl:.2f}%")
print(f"Cumulative return: {total_return_pct:+.2f}%")
print(f"Winning months:    {winning_months}/20")
print(f"Losing months:     {losing_months}/20")
print(f"Best trade:        {best_trade.get('symbol','')} in {best_trade.get('month','')} → {max_win:+.2f}%")
print(f"Worst trade:       {worst_trade.get('symbol','')} in {worst_trade.get('month','')} → {max_loss:+.2f}%")
