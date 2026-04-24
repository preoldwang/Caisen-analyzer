#!/usr/bin/env python3
"""
Improved Backtest: Top 2 + Premium Signal Filter
=================================================
Rules:
- Pick Top 2 (not Top 3)
- If at least one has 颈线突破 or 量价背离(上行) → trade both
- If no premium signal but both score ≥ 12 → trade both
- Otherwise → skip the month
- Also test: Score ≥ 13 filter variant
"""

import json
import os
import numpy as np
from datetime import datetime

BASE = '/root/.openclaw/workspace/Caisen-analyzer'

with open(os.path.join(BASE, 'backtest_20months_combined.json')) as f:
    data = json.load(f)

def has_premium_signal(trade):
    """Check if trade has 颈线突破 or 量价背离(上行) signal."""
    return any(s.get('type') in ['颈线突破', '量价背离(上行)'] for s in trade.get('signals', []))

def calc_stats(pnls, label):
    """Calculate portfolio stats."""
    if not pnls:
        return {}
    wins = len([p for p in pnls if p > 0])
    losses = len([p for p in pnls if p <= 0])
    avg = np.mean(pnls)
    med = np.median(pnls)
    std = np.std(pnls)
    cum = 1.0
    for p in pnls:
        cum *= (1 + p/100)
    cum_pct = (cum - 1) * 100
    sharpe = avg / std if std > 0 else 0
    max_dd = min(pnls)
    max_win = max(pnls)
    return {
        'label': label,
        'trades': len(pnls),
        'wins': wins,
        'losses': losses,
        'win_rate': wins/len(pnls)*100,
        'avg': avg,
        'med': med,
        'std': std,
        'cum': cum_pct,
        'sharpe': sharpe,
        'max_dd': max_dd,
        'max_win': max_win,
    }

# ============================================================
# Define strategies
# ============================================================

strategies = {}

# Baseline: Top 3
baseline = []
for r in data:
    for t in r.get('trades', []):
        baseline.append({'month': r['month'], **t})
strategies['Baseline (Top 3)'] = baseline

# Strategy A: Top 2 only
top2 = []
for r in data:
    for t in r.get('trades', [])[:2]:
        top2.append({'month': r['month'], **t})
strategies['A: Top 2 only'] = top2

# Strategy B: Top 2 + Premium signal filter
top2_premium = []
skipped_b = []
for r in data:
    trades = r.get('trades', [])[:2]
    has_prem = any(has_premium_signal(t) for t in trades)
    if has_prem:
        for t in trades:
            top2_premium.append({'month': r['month'], **t})
    else:
        skipped_b.append(r['month'])
strategies['B: Top 2 + Premium signal'] = top2_premium

# Strategy C: Top 2 + Score ≥ 13
top2_score13 = []
skipped_c = []
for r in data:
    trades = r.get('trades', [])[:2]
    has_high = any(t.get('score', 0) >= 13 for t in trades)
    if has_high:
        for t in trades:
            top2_score13.append({'month': r['month'], **t})
    else:
        skipped_c.append(r['month'])
strategies['C: Top 2 + Score≥13'] = top2_score13

# Strategy D: Top 2 + (Premium OR both score ≥ 12)
top2_smart = []
skipped_d = []
for r in data:
    trades = r.get('trades', [])[:2]
    has_prem = any(has_premium_signal(t) for t in trades)
    both_12 = all(t.get('score', 0) >= 12 for t in trades)
    if has_prem or both_12:
        for t in trades:
            top2_smart.append({'month': r['month'], **t})
    else:
        skipped_d.append(r['month'])
strategies['D: Top 2 + Premium or both≥12'] = top2_smart

# Strategy E: Top 2 + Score ≥ 13 for BOTH picks
top2_both13 = []
skipped_e = []
for r in data:
    trades = r.get('trades', [])[:2]
    if all(t.get('score', 0) >= 13 for t in trades):
        for t in trades:
            top2_both13.append({'month': r['month'], **t})
    else:
        skipped_e.append(r['month'])
strategies['E: Top 2 + both Score≥13'] = top2_both13

# Strategy F: Top 1 + Premium signal only
top1_premium = []
for r in data:
    trades = r.get('trades', [])
    if trades and has_premium_signal(trades[0]):
        top1_premium.append({'month': r['month'], **trades[0]})
strategies['F: Top 1 + Premium only'] = top1_premium

# ============================================================
# Print comparison table
# ============================================================

print('='*130)
print('IMPROVED BACKTEST COMPARISON — 20 Months (Aug 2024 - Mar 2026)')
print('='*130)
hdr = f"{'Strategy':<38} {'Trades':>6} {'W/L':>7} {'Win%':>6} {'Avg%':>7} {'Med%':>7} {'Cum%':>8} {'MaxDD':>7} {'Sharpe':>7} {'Skipped':>8}"
print(hdr)
print('-'*130)

for name, trades in strategies.items():
    pnls = [t.get('pnl_pct', 0) or 0 for t in trades]
    s = calc_stats(pnls, name)
    skip_count = 20 - len(set(t['month'] for t in trades))
    t_count = s['trades']; w = s['wins']; l = s['losses']; wr = s['win_rate']
    avg = s['avg']; med = s['med']; cum = s['cum']; mdd = s['max_dd']; sh = s['sharpe']
    print(f'{name:<38} {t_count:>6} {w}/{l:<4} {wr:>5.1f}% {avg:>+6.2f}% {med:>+6.2f}% {cum:>+7.2f}% {mdd:>+6.1f}% {sh:>6.2f} {skip_count:>6} mo')

# ============================================================
# Detailed monthly breakdown for best strategies
# ============================================================

print()
print('='*130)
print('MONTHLY BREAKDOWN — Strategy D (Top 2 + Premium or both≥12)')
print('='*130)

for r in data:
    month = r['month']
    trades = r.get('trades', [])[:2]
    has_prem = any(has_premium_signal(t) for t in trades)
    both_12 = all(t.get('score', 0) >= 12 for t in trades)
    traded = has_prem or both_12
    
    if traded:
        pnls = [t.get('pnl_pct', 0) or 0 for t in trades]
        avg = np.mean(pnls)
        emoji = '✅' if avg > 0 else '❌'
        reason = 'Premium' if has_prem else 'Both≥12'
        details = ' | '.join([f"{t['symbol']}({t.get('name','')}) {t.get('pnl_pct',0):+.1f}%" for t in trades])
        print(f'  {emoji} {month}: {avg:+.1f}%  [{reason}]  {details}')
    else:
        print(f'  ⏸️ {month}: SKIPPED (no premium signal, scores too low)')

# ============================================================
# Risk analysis
# ============================================================

print()
print('='*130)
print('RISK ANALYSIS')
print('='*130)

for name in ['A: Top 2 only', 'B: Top 2 + Premium signal', 'D: Top 2 + Premium or both≥12']:
    trades = strategies[name]
    pnls = [t.get('pnl_pct', 0) or 0 for t in trades]
    
    # Losing streaks
    max_streak = 0
    current = 0
    for p in pnls:
        if p <= 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    
    # Consecutive winning months
    month_pnls = {}
    for t in trades:
        m = t['month']
        if m not in month_pnls:
            month_pnls[m] = []
        month_pnls[m].append(t.get('pnl_pct', 0) or 0)
    
    month_avgs = [np.mean(month_pnls[m]) for m in sorted(month_pnls.keys())]
    max_win_streak = 0
    max_lose_streak = 0
    curr_w = 0
    curr_l = 0
    for a in month_avgs:
        if a > 0:
            curr_w += 1
            curr_l = 0
            max_win_streak = max(max_win_streak, curr_w)
        else:
            curr_l += 1
            curr_w = 0
            max_lose_streak = max(max_lose_streak, curr_l)
    
    # Profit factor
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    print(f'{name}:')
    print(f'  Max consecutive losing trades: {max_streak}')
    print(f'  Max consecutive winning months: {max_win_streak}')
    print(f'  Max consecutive losing months: {max_lose_streak}')
    print(f'  Profit factor: {pf:.2f}')
    print(f'  Gross profit: +{gross_profit:.1f}% | Gross loss: -{gross_loss:.1f}%')
    print()

# ============================================================
# Generate HTML report
# ============================================================

# Use Strategy D as the featured improved strategy
best_trades = strategies['D: Top 2 + Premium or both≥12']
best_pnls = [t.get('pnl_pct', 0) or 0 for t in best_trades]
best_stats = calc_stats(best_pnls, 'Improved')

base_trades = strategies['Baseline (Top 3)']
base_pnls = [t.get('pnl_pct', 0) or 0 for t in base_trades]
base_stats = calc_stats(base_pnls, 'Baseline')

html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Improved HK Backtest — Top 2 + Smart Filter</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#e0e0e0;line-height:1.6}
.container{max-width:1400px;margin:0 auto;padding:20px}
h1{text-align:center;color:#00d4ff;font-size:2em;margin-bottom:5px}
.subtitle{text-align:center;color:#888;margin-bottom:30px}
.vs{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:30px}
.vs-card{border-radius:12px;padding:25px;text-align:center}
.vs-card.old{background:linear-gradient(135deg,#2a1a1a,#1a1a2e);border:1px solid #664444}
.vs-card.new{background:linear-gradient(135deg,#1a2a1a,#1a2e1a);border:1px solid #44aa44}
.vs-card h2{font-size:1.1em;margin-bottom:15px;color:#888}
.vs-card .big{font-size:2.5em;font-weight:bold}
.vs-card .grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:15px}
.vs-card .item .lbl{color:#888;font-size:0.75em;text-transform:uppercase}
.vs-card .item .val{font-size:1.3em;font-weight:bold}
.positive{color:#00ff88}.negative{color:#ff4444}.neutral{color:#ffaa00}
.improvement{background:linear-gradient(135deg,#0f3460,#1a2e1a);border:2px solid #00ff88;border-radius:12px;padding:25px;margin-bottom:30px;text-align:center}
.improvement h3{color:#00ff88;font-size:1.3em;margin-bottom:10px}
.improvement .big{font-size:2em;font-weight:bold}
.rules{background:#111;border:1px solid #222;border-radius:10px;padding:20px;margin-bottom:30px}
.rules h3{color:#00d4ff;margin-bottom:10px}
.rules li{color:#888;font-size:0.9em;margin-bottom:6px;margin-left:20px}
.rules .highlight{color:#00ff88;font-weight:bold}
.month-card{background:#111;border:1px solid #222;border-radius:10px;margin-bottom:15px;overflow:hidden}
.month-header{background:linear-gradient(90deg,#1a1a2e,#0f3460);padding:12px 20px;display:flex;justify-content:space-between;align-items:center}
.month-header h2{color:#00d4ff;font-size:1.05em}
.month-header .pnl{font-size:1.05em;font-weight:bold}
.month-body{padding:15px 20px}
table{width:100%;border-collapse:collapse}
th{background:#1a1a2e;color:#00d4ff;padding:8px 10px;text-align:left;font-size:0.8em;text-transform:uppercase}
td{padding:8px 10px;border-bottom:1px solid #1a1a1a;font-size:0.85em}
tr:hover{background:#1a1a1a}
.skip-badge{display:inline-block;background:#333;color:#888;padding:2px 8px;border-radius:4px;font-size:0.8em}
.premium-badge{display:inline-block;background:#0f3460;color:#00d4ff;padding:2px 8px;border-radius:4px;font-size:0.8em}
.pnl-positive{color:#00ff88;font-weight:bold}.pnl-negative{color:#ff4444;font-weight:bold}
.bar-wrap{display:flex;align-items:flex-end;height:140px;gap:4px;padding:10px 0}
.bar{display:flex;flex-direction:column;align-items:center;min-width:32px;border-radius:4px 4px 0 0;font-size:0.6em;padding-top:3px}
.bar .lbl{color:#666;font-size:0.9em;margin-top:2px}
.footer{text-align:center;color:#555;margin-top:40px;padding:20px;border-top:1px solid #222}
</style>
</head>
<body>
<div class="container">
<h1>🎯 Improved Backtest: Top 2 + Smart Filter</h1>
<p class="subtitle">蔡森技術分析 · Optimized Strategy vs Baseline · Aug 2024 → Mar 2026</p>

<div class="improvement">
<h3>✅ Key Improvement</h3>
<div class="big">""" + f'{best_stats["win_rate"]:.1f}% win rate' + """</div>
<div style="color:#888;margin-top:5px">""" + f'Up from {base_stats["win_rate"]:.1f}% baseline' + """ · """ + f'{best_stats["trades"]} trades (vs {base_stats["trades"]})' + """</div>
</div>

<div class="vs">
<div class="vs-card old">
<h2>❌ Baseline (Top 3)</h2>
<div class="big negative">""" + f'{base_stats["cum"]:+.1f}%' + """</div>
<div class="grid">
<div class="item"><div class="lbl">Trades</div><div class="val">""" + f'{base_stats["trades"]}' + """</div></div>
<div class="item"><div class="lbl">Win Rate</div><div class="val negative">""" + f'{base_stats["win_rate"]:.1f}%' + """</div></div>
<div class="item"><div class="lbl">Avg P&L</div><div class="val">""" + f'{base_stats["avg"]:+.2f}%' + """</div></div>
<div class="item"><div class="lbl">Max DD</div><div class="val negative">""" + f'{base_stats["max_dd"]:+.1f}%' + """</div></div>
<div class="item"><div class="lbl">Sharpe</div><div class="val">""" + f'{base_stats["sharpe"]:.2f}' + """</div></div>
<div class="item"><div class="lbl">Winning Mo</div><div class="val">""" + f'{len([m for m in set(t["month"] for t in base_trades) if np.mean([t.get("pnl_pct",0) or 0 for t in base_trades if t["month"]==m])>0])}' + """/20</div></div>
</div>
</div>
<div class="vs-card new">
<h2>✅ Improved (Top 2 + Filter)</h2>
<div class="big positive">""" + f'{best_stats["cum"]:+.1f}%' + """</div>
<div class="grid">
<div class="item"><div class="lbl">Trades</div><div class="val">""" + f'{best_stats["trades"]}' + """</div></div>
<div class="item"><div class="lbl">Win Rate</div><div class="val positive">""" + f'{best_stats["win_rate"]:.1f}%' + """</div></div>
<div class="item"><div class="lbl">Avg P&L</div><div class="val">""" + f'{best_stats["avg"]:+.2f}%' + """</div></div>
<div class="item"><div class="lbl">Max DD</div><div class="val">""" + f'{best_stats["max_dd"]:+.1f}%' + """</div></div>
<div class="item"><div class="lbl">Sharpe</div><div class="val positive">""" + f'{best_stats["sharpe"]:.2f}' + """</div></div>
<div class="item"><div class="lbl">Winning Mo</div><div class="val">""" + f'{len([m for m in set(t["month"] for t in best_trades) if np.mean([t.get("pnl_pct",0) or 0 for t in best_trades if t["month"]==m])>0])}' + """/""" + f'{len(set(t["month"] for t in best_trades))}' + """</div></div>
</div>
</div>
</div>

<div class="rules">
<h3>📐 Improved Strategy Rules</h3>
<ol>
<li>Pick <span class="highlight">Top 2</span> stocks (not Top 3) by Cai Sen composite score</li>
<li>If at least one pick has <span class="highlight">颈线突破</span> or <span class="highlight">量价背离(上行)</span> signal → <span class="highlight">TRADE both</span></li>
<li>If no premium signal but <span class="highlight">both picks score ≥ 12</span> → <span class="highlight">TRADE both</span></li>
<li>Otherwise → <span class="highlight">SKIP the month</span> (sit in cash)</li>
<li>Buy at open on first trading day → Sell at close on last trading day</li>
</ol>
</div>

<div style="background:#111;border:1px solid #222;border-radius:10px;padding:20px;margin-bottom:30px">
<h3 style="color:#00d4ff;margin-bottom:15px">📊 Strategy Comparison</h3>
<table>
<tr><th>Strategy</th><th>Trades</th><th>Win Rate</th><th>Avg P&L</th><th>Cumulative</th><th>Max DD</th><th>Sharpe</th><th>Months Skipped</th></tr>
"""

for name, trades in strategies.items():
    pnls = [t.get('pnl_pct', 0) or 0 for t in trades]
    s = calc_stats(pnls, name)
    skip_count = 20 - len(set(t['month'] for t in trades))
    cls = 'positive' if s['avg'] > 0 else 'negative'
    html += f'<tr><td><strong>{name}</strong></td><td>{s["trades"]}</td><td class="{cls}">{s["win_rate"]:.1f}%</td><td class="{cls}">{s["avg"]:+.2f}%</td><td class="{cls}">{s["cum"]:+.1f}%</td><td>{s["max_dd"]:+.1f}%</td><td>{s["sharpe"]:.2f}</td><td>{skip_count}</td></tr>'

html += """</table></div>

<div style="background:#111;border:1px solid #222;border-radius:10px;padding:20px;margin-bottom:30px">
<h3 style="color:#00d4ff;margin-bottom:15px">📅 Monthly Detail — Improved Strategy (Top 2 + Filter)</h3>
"""

# Build monthly detail for Strategy D
month_data_d = {}
for t in best_trades:
    m = t['month']
    if m not in month_data_d:
        month_data_d[m] = []
    month_data_d[m].append(t)

for r in data:
    month = r['month']
    first_day = r.get('first_trading_day', '?')
    last_day = r.get('last_trading_day', '?')
    
    if month in month_data_d:
        trades = month_data_d[month]
        pnls = [t.get('pnl_pct', 0) or 0 for t in trades]
        avg = np.mean(pnls)
        cls = 'pnl-positive' if avg > 0 else 'pnl-negative'
        
        # Determine filter reason
        has_prem = any(has_premium_signal(t) for t in trades)
        reason = 'Premium signal (颈线突破/量价背离)' if has_prem else 'Both scores ≥ 12'
        
        html += f"""<div class="month-card">
<div class="month-header">
<div><h2>📅 {month}</h2><span style="color:#888;font-size:0.85em">{first_day} → {last_day} · <span class="premium-badge">{reason}</span></span></div>
<div class="pnl {cls}">{avg:+.2f}%</div>
</div>
<div class="month-body"><table>
<tr><th>#</th><th>Stock</th><th>Buy Date</th><th>Buy</th><th>Sell Date</th><th>Sell</th><th>P&L</th><th>Score</th><th>Signals</th></tr>
"""
        for i, t in enumerate(trades):
            pnl = t.get('pnl_pct')
            pnl_cls = 'pnl-positive' if pnl and pnl > 0 else 'pnl-negative'
            sigs = ', '.join([s.get('type','') for s in t.get('signals',[])])
            html += f'<tr><td>{i+1}</td><td><strong>{t["symbol"]}</strong> {t.get("name","")}</td><td>{t.get("buy_date","")}</td><td>{t.get("buy_price","")}</td><td>{t.get("sell_date","")}</td><td>{t.get("sell_price","")}</td><td class="{pnl_cls}">{pnl:+.2f}%</td><td>{t.get("score","")}</td><td>{sigs}</td></tr>'
        html += "</table></div></div>"
    else:
        # Skipped month
        # Check why skipped
        trades_2 = r.get('trades', [])[:2]
        has_prem = any(has_premium_signal(t) for t in trades_2)
        both_12 = all(t.get('score', 0) >= 12 for t in trades_2) if trades_2 else False
        
        html += f"""<div class="month-card">
<div class="month-header" style="background:linear-gradient(90deg,#1a1a1a,#222)">
<div><h2>📅 {month}</h2><span class="skip-badge">SKIPPED — No premium signal, scores too low</span></div>
<div style="color:#888">Cash (0%)</div>
</div>
<div class="month-body" style="color:#666;font-size:0.85em">
"""
        for t in trades_2:
            sigs = ', '.join([s.get('type','') for s in t.get('signals',[])])
            html += f'<div>{t["symbol"]} ({t.get("name","")}) — Score: {t.get("score",0)}, Signals: [{sigs}]</div>'
        html += "</div></div>"

html += """</div>

<div class="footer">
<p>Generated on """ + datetime.now().strftime('%Y-%m-%d %H:%M') + """ · Cai Sen Technical Analysis Tool v3.0 · Improved Strategy</p>
<p>蔡森技術分析 · Top 2 + Premium Signal Filter · RAW (unadjusted) prices</p>
</div>
</div>
</body>
</html>"""

# Save
html_path = os.path.join(BASE, 'backtest_improved_strategy.html')
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'\n📄 HTML report: {html_path}')

json_path = os.path.join(BASE, 'backtest_improved_strategy.json')
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(best_trades, f, ensure_ascii=False, indent=2)
print(f'💾 JSON data: {json_path}')
