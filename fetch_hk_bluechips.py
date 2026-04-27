#!/usr/bin/env python3
"""Fetch 8 years of unadjusted daily prices for all HK blue chip stocks."""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import json
import time
import os

# Hang Seng Index Blue Chip Constituents (current + recent)
# These are the major HSI constituent stocks
HSI_BLUE_CHIPS = {
    "0001.HK": "CK Hutchison",
    "0002.HK": "CLP Holdings",
    "0003.HK": "HK & China Gas",
    "0005.HK": "HSBC Holdings",
    "0006.HK": "Power Assets",
    "0011.HK": "Hang Seng Bank",
    "0012.HK": "Henderson Land",
    "0016.HK": "SHK Properties",
    "0017.HK": "New World Dev",
    "0019.HK": "Swire Pacific",
    "0027.HK": "Galaxy Entertainment",
    "0066.HK": "MTR Corporation",
    "0101.HK": "Hang Lung Properties",
    "0175.HK": "Geely Auto",
    "0241.HK": "Ali Health",
    "0267.HK": "CITIC",
    "0288.HK": "WH Group",
    "0291.HK": "China Resources Beer",
    "0316.HK": "Orient Overseas",
    "0322.HK": "TCL Electronics",
    "0386.HK": "China Petroleum",
    "0388.HK": "HKEX",
    "0669.HK": "Techtronic Ind",
    "0700.HK": "Tencent",
    "0762.HK": "China Unicom",
    "0823.HK": "Link REIT",
    "0857.HK": "PetroChina",
    "0868.HK": "Xinyi Glass",
    "0881.HK": "Zhongsheng Group",
    "0883.HK": "CNOOC",
    "0939.HK": "CCB",
    "0941.HK": "China Mobile",
    "0960.HK": "Longfor Group",
    "0968.HK": "Xinyi Solar",
    "0981.HK": "SMIC",
    "1024.HK": "Kuaishou Tech",
    "1038.HK": "CKI Holdings",
    "1044.HK": "Hengan International",
    "1093.HK": "CSPC Pharmaceutical",
    "1109.HK": "China Resources Land",
    "1113.HK": "CK Asset Holdings",
    "1177.HK": "Sino Biopharmaceutical",
    "1211.HK": "BYD Company",
    "1299.HK": "AIA Group",
    "1378.HK": "China Hongqiao",
    "1398.HK": "ICBC",
    "1810.HK": "Xiaomi",
    "1876.HK": "Budweiser APAC",
    "1928.HK": "Sands China",
    "1929.HK": "Chow Tai Fook",
    "1997.HK": "Wharf REIC",
    "2007.HK": "Country Garden",
    "2018.HK": "AAC Technologies",
    "2020.HK": "ANTA Sports",
    "2269.HK": "WuXi Biologics",
    "2313.HK": "Shenzhou International",
    "2318.HK": "Ping An Insurance",
    "2319.HK": "China Mengniu",
    "2331.HK": "Li Ning",
    "2382.HK": "Sunny Optical",
    "2388.HK": "BOC Hong Kong",
    "2628.HK": "China Life",
    "2688.HK": "ENN Energy",
    "3328.HK": "Bank of Communications",
    "3690.HK": "Meituan",
    "3968.HK": "China Merchants Bank",
    "3988.HK": "Bank of China",
    "6098.HK": "CG Services",
    "6618.HK": "JD Health",
    "6862.HK": "Haidilao",
    "9618.HK": "JD.com",
    "9633.HK": "Nongfu Spring",
    "9888.HK": "Baidu",
    "9961.HK": "Trip.com",
    "9988.HK": "Alibaba",
    "9999.HK": "NetEase",
}

END_DATE = datetime(2026, 4, 27)
START_DATE = END_DATE - timedelta(days=8*365)

print(f"Fetching HK Blue Chip prices from {START_DATE.date()} to {END_DATE.date()}")
print(f"Total stocks: {len(HSI_BLUE_CHIPS)}")
print("=" * 70)

all_data = {}
errors = []

for i, (ticker, name) in enumerate(HSI_BLUE_CHIPS.items(), 1):
    print(f"[{i:2d}/{len(HSI_BLUE_CHIPS)}] {ticker} {name:<25s}", end=" ... ", flush=True)
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(start=START_DATE.strftime('%Y-%m-%d'),
                            end=END_DATE.strftime('%Y-%m-%d'),
                            auto_adjust=False)
        if hist.empty:
            print("NO DATA")
            errors.append({"ticker": ticker, "name": name, "error": "No data returned"})
        else:
            # Clean up - keep key columns
            hist = hist[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
            hist.index = hist.index.strftime('%Y-%m-%d')
            all_data[ticker] = {
                "name": name,
                "rows": len(hist),
                "start": hist.index[0],
                "end": hist.index[-1],
                "data": hist.reset_index().to_dict(orient='records')
            }
            print(f"OK ({len(hist)} days)")
    except Exception as e:
        print(f"ERROR: {e}")
        errors.append({"ticker": ticker, "name": name, "error": str(e)})
    
    # Rate limiting
    if i % 5 == 0:
        time.sleep(1)

print("\n" + "=" * 70)
print(f"Success: {len(all_data)} | Failed: {len(errors)}")

# Generate HTML report
print("\nGenerating HTML report...")

html_parts = []
html_parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HK Blue Chip Stocks - 8 Year Price History (Unadjusted)</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }
h1 { text-align: center; color: #58a6ff; margin-bottom: 8px; font-size: 28px; }
.subtitle { text-align: center; color: #8b949e; margin-bottom: 30px; font-size: 14px; }
.summary { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 30px; max-width: 800px; margin-left: auto; margin-right: auto; }
.summary h2 { color: #58a6ff; margin-bottom: 10px; }
.summary table { width: 100%; border-collapse: collapse; }
.summary td { padding: 4px 8px; color: #c9d1d9; }
.summary td:first-child { color: #8b949e; width: 180px; }
.stock-section { margin-bottom: 40px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }
.stock-header { background: #21262d; padding: 16px 20px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }
.stock-header:hover { background: #30363d; }
.stock-header h2 { color: #58a6ff; font-size: 20px; }
.stock-header .meta { color: #8b949e; font-size: 13px; }
.stock-header .meta span { margin-left: 16px; }
.stock-header .arrow { color: #8b949e; transition: transform 0.3s; font-size: 20px; }
.stock-header.collapsed .arrow { transform: rotate(-90deg); }
.stock-body { max-height: 600px; overflow-y: auto; }
.stock-body.hidden { display: none; }
table.price-table { width: 100%; border-collapse: collapse; font-size: 13px; }
table.price-table th { background: #21262d; color: #8b949e; padding: 8px 12px; text-align: right; position: sticky; top: 0; }
table.price-table th:first-child { text-align: left; }
table.price-table td { padding: 6px 12px; text-align: right; border-bottom: 1px solid #21262d; }
table.price-table td:first-child { text-align: left; color: #8b949e; }
table.price-table tr:hover { background: #1c2128; }
.up { color: #3fb950; }
.down { color: #f85149; }
.filter-bar { padding: 12px 20px; background: #0d1117; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.filter-bar input { background: #161b22; border: 1px solid #30363d; color: #c9d1d9; padding: 8px 12px; border-radius: 6px; font-size: 14px; width: 300px; }
.filter-bar input:focus { outline: none; border-color: #58a6ff; }
.filter-bar label { color: #8b949e; font-size: 13px; }
.filter-bar select { background: #161b22; border: 1px solid #30363d; color: #c9d1d9; padding: 6px 10px; border-radius: 6px; }
.error-list { background: #1c1210; border: 1px solid #6e3630; border-radius: 8px; padding: 16px; margin-bottom: 20px; }
.error-list h3 { color: #f85149; margin-bottom: 8px; }
.error-list li { color: #f0883e; margin-left: 20px; margin-bottom: 4px; }
.nav-top { position: fixed; bottom: 20px; right: 20px; background: #21262d; border: 1px solid #30363d; color: #58a6ff; padding: 10px 14px; border-radius: 8px; cursor: pointer; font-size: 14px; text-decoration: none; }
.nav-top:hover { background: #30363d; }
</style>
</head>
<body>
<h1>🇭🇰 HK Blue Chip Stocks — 8-Year Price History</h1>
<p class="subtitle">Unadjusted Daily Prices (OHLCV) | """ + START_DATE.strftime('%Y-%m-%d') + " to " + END_DATE.strftime('%Y-%m-%d') + """ | Generated """ + datetime.now().strftime('%Y-%m-%d %H:%M') + """</p>
""")

# Summary
html_parts.append(f"""
<div class="summary">
<h2>📊 Summary</h2>
<table>
<tr><td>Total Stocks</td><td><b>{len(HSI_BLUE_CHIPS)}</b></td></tr>
<tr><td>Successfully Fetched</td><td><b style="color:#3fb950">{len(all_data)}</b></td></tr>
<tr><td>Failed</td><td><b style="color:#f85149">{len(errors)}</b></td></tr>
<tr><td>Date Range</td><td>{START_DATE.strftime('%Y-%m-%d')} → {END_DATE.strftime('%Y-%m-%d')} (8 years)</td></tr>
<tr><td>Data Type</td><td>Unadjusted (raw) OHLCV</td></tr>
<tr><td>Source</td><td>Yahoo Finance via yfinance</td></tr>
</table>
</div>
""")

# Filter bar
html_parts.append("""
<div class="filter-bar">
<input type="text" id="searchBox" placeholder="🔍 Search by ticker or name..." oninput="filterStocks()">
<label>Show:
<select id="dateFilter" onchange="filterStocks()">
<option value="all">All Data</option>
<option value="1y">Last 1 Year</option>
<option value="2y">Last 2 Years</option>
<option value="5y">Last 5 Years</option>
</select>
</label>
<label>Per page:
<select id="rowLimit" onchange="filterStocks()">
<option value="50">50 rows</option>
<option value="100">100 rows</option>
<option value="250">250 rows</option>
<option value="99999">All rows</option>
</select>
</label>
</div>
""")

# Errors
if errors:
    html_parts.append('<div class="error-list"><h3>⚠️ Failed to fetch:</h3><ul>')
    for e in errors:
        html_parts.append(f'<li><b>{e["ticker"]}</b> {e["name"]}: {e["error"]}</li>')
    html_parts.append('</ul></div>')

# Stock data
sorted_tickers = sorted(all_data.keys(), key=lambda x: x)
for ticker in sorted_tickers:
    info = all_data[ticker]
    name = info["name"]
    rows = info["rows"]
    start = info["start"]
    end = info["end"]
    
    # Store data as JSON for JS filtering
    data_json = json.dumps(info["data"])
    
    html_parts.append(f"""
<div class="stock-section" data-ticker="{ticker.lower()}" data-name="{name.lower()}" data-json='{data_json}'>
<div class="stock-header" onclick="toggleStock(this)">
<div>
<h2>{ticker} — {name}</h2>
<div class="meta">
<span>📅 {start} → {end}</span>
<span>📊 {rows} trading days</span>
</div>
</div>
<div class="arrow">▼</div>
</div>
<div class="stock-body">
<table class="price-table">
<thead><tr><th>Date</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th></tr></thead>
<tbody>""")
    
    for row in info["data"]:
        date = row["Date"]
        o = f"{row['Open']:.2f}" if pd.notna(row['Open']) else "-"
        h = f"{row['High']:.2f}" if pd.notna(row['High']) else "-"
        l = f"{row['Low']:.2f}" if pd.notna(row['Low']) else "-"
        c = f"{row['Close']:.2f}" if pd.notna(row['Close']) else "-"
        v = f"{int(row['Volume']):,}" if pd.notna(row['Volume']) and row['Volume'] > 0 else "-"
        
        # Color close based on open
        try:
            close_val = float(c)
            open_val = float(o)
            cls = 'up' if close_val >= open_val else 'down'
        except:
            cls = ''
        
        html_parts.append(f'<tr><td>{date}</td><td>{o}</td><td>{h}</td><td>{l}</td><td class="{cls}">{c}</td><td>{v}</td></tr>')
    
    html_parts.append("""</tbody></table></div></div>""")

# JavaScript
html_parts.append("""
<a href="#" class="nav-top">↑ Top</a>
<script>
function toggleStock(header) {
    header.classList.toggle('collapsed');
    header.nextElementSibling.classList.toggle('hidden');
}

function filterStocks() {
    const query = document.getElementById('searchBox').value.toLowerCase();
    const dateFilter = document.getElementById('dateFilter').value;
    const rowLimit = parseInt(document.getElementById('rowLimit').value);
    const sections = document.querySelectorAll('.stock-section');
    
    const now = new Date('2026-04-27');
    let cutoffDate = null;
    if (dateFilter === '1y') cutoffDate = new Date('2025-04-27');
    else if (dateFilter === '2y') cutoffDate = new Date('2024-04-27');
    else if (dateFilter === '5y') cutoffDate = new Date('2021-04-27');
    
    sections.forEach(section => {
        const ticker = section.dataset.ticker;
        const name = section.dataset.name;
        const match = !query || ticker.includes(query) || name.includes(query);
        section.style.display = match ? '' : 'none';
        
        if (match) {
            const data = JSON.parse(section.dataset.json);
            let filtered = data;
            if (cutoffDate) {
                filtered = data.filter(r => new Date(r.Date) >= cutoffDate);
            }
            // Limit rows
            const limited = filtered.slice(-rowLimit);
            
            const tbody = section.querySelector('tbody');
            tbody.innerHTML = '';
            limited.forEach(row => {
                const o = row.Open != null ? row.Open.toFixed(2) : '-';
                const h = row.High != null ? row.High.toFixed(2) : '-';
                const l = row.Low != null ? row.Low.toFixed(2) : '-';
                const c = row.Close != null ? row.Close.toFixed(2) : '-';
                const v = row.Volume != null && row.Volume > 0 ? row.Volume.toLocaleString() : '-';
                let cls = '';
                try { cls = parseFloat(c) >= parseFloat(o) ? 'up' : 'down'; } catch(e) {}
                tbody.innerHTML += `<tr><td>${row.Date}</td><td>${o}</td><td>${h}</td><td>${l}</td><td class="${cls}">${c}</td><td>${v}</td></tr>`;
            });
            
            // Update meta
            const meta = section.querySelector('.meta');
            const spans = meta.querySelectorAll('span');
            if (limited.length > 0) {
                spans[0].textContent = `📅 ${limited[0].Date} → ${limited[limited.length-1].Date}`;
                spans[1].textContent = `📊 ${limited.length} trading days`;
            }
        }
    });
}
</script>
</body></html>""")

# Write HTML
output_path = "/root/.openclaw/workspace/Caisen-analyzer/hk_blue_chip_8y_prices.html"
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(html_parts))

print(f"\n✅ HTML saved to: {output_path}")
print(f"   File size: {os.path.getsize(output_path) / 1024 / 1024:.1f} MB")

# Save JSON too for reference
json_path = "/root/.openclaw/workspace/Caisen-analyzer/hk_blue_chip_8y_prices.json"
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump({"generated": datetime.now().isoformat(), "start": START_DATE.isoformat(), "end": END_DATE.isoformat(), "stocks": all_data}, f, ensure_ascii=False)

print(f"   JSON saved to: {json_path}")
print(f"   JSON size: {os.path.getsize(json_path) / 1024 / 1024:.1f} MB")
