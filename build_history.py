#!/usr/bin/env python3
"""產出 history.html — 歷史報告頁面"""
import os, json
from datetime import datetime
from collections import defaultdict


def dedupe_records(records):
    seen = set()
    out = []
    for r in records:
        k = (r.get("trade_date"), r.get("ticker"), r.get("framework") or r.get("pattern"))
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out

def build_history_html(records):
    today = datetime.now().strftime("%Y-%m-%d")

    records = dedupe_records(records)

    # 依日期分組
    by_date = defaultdict(list)
    for r in records:
        by_date[r["trade_date"]].append(r)

    dates = sorted(by_date.keys(), reverse=True)

    # 日期列表（左欄）
    date_links = ""
    for d in dates:
        sigs = by_date[d]
        high = len([s for s in sigs if s["confidence"] >= 0.75])
        date_links += f'''
        <a href="#{d}" class="date-link">
          <div class="date-label">{d}</div>
          <div class="date-meta">{len(sigs)} 訊號 / <span style="color:#3fb950">{high} 高信心</span></div>
        </a>'''

    # 每日報告區塊
    sections = ""
    for d in dates:
        sigs = by_date[d]
        rows = ""
        for s in sigs:
            cc = "#3fb950" if s["confidence"] >= 0.75 else "#d29922"
            rows += f"""<tr>
              <td><b>{s["ticker"]}</b></td>
              <td>{s["name"]}</td>
              <td style="color:{cc}" data-framework="{s.get("framework", s["pattern"])}">{s.get("framework", s["pattern"])} </td>
              <td style="color:{cc}">{s["confidence"]*100:.0f}%</td>
              <td>{s["entry"]:.2f}</td>
              <td style="color:#f85149">{s["stop_loss"]:.2f}</td>
              <td style="color:#3fb950">{s["target1"]:.2f}</td>
              <td>{s["rr"]}</td>
            </tr>"""
        sections += f'''
        <div class="day-section" id="{d}">
          <h3>{d} <span class="day-count">{len(sigs)} 個訊號</span></h3>
          <div class="section">
          <table>
            <tr><th>代號</th><th>名稱</th><th>型態</th><th>信心</th>
                <th>入場價</th><th>停損</th><th>目標一</th><th>R:R</th></tr>
            {rows if rows else '<tr><td colspan="8" style="text-align:center;color:#8b949e">無訊號</td></tr>'}
          </table>
          </div>
        </div>'''

    return f"""<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>蔡森掃描歷史報告</title>
<style>
  *{{box-sizing:border-box}}
  body{{font-family:-apple-system,sans-serif;background:#0f1117;color:#e1e4e8;margin:0;padding:0}}
  .layout{{display:flex;min-height:100vh}}
  .sidebar{{width:200px;background:#161b22;border-right:1px solid #30363d;
            padding:16px;position:sticky;top:0;height:100vh;overflow-y:auto;flex-shrink:0}}
  .sidebar h2{{color:#58a6ff;font-size:14px;margin:0 0 12px}}
  .date-link{{display:block;padding:10px 8px;border-radius:6px;
              text-decoration:none;margin-bottom:4px;border:1px solid transparent}}
  .date-link:hover{{background:#1c2128;border-color:#30363d}}
  .date-label{{color:#e1e4e8;font-size:13px;font-weight:600}}
  .date-meta{{color:#8b949e;font-size:11px;margin-top:2px}}
  .main{{flex:1;padding:24px;overflow-x:auto}}
  .main h1{{color:#58a6ff;margin:0 0 4px}}
  .main h2{{color:#8b949e;font-size:13px;margin:0 0 24px}}
  h3{{color:#e1e4e8;font-size:15px;margin:28px 0 10px;
      border-left:3px solid #58a6ff;padding-left:10px}}
  .day-count{{color:#8b949e;font-size:12px;font-weight:400;margin-left:8px}}
  .section{{background:#161b22;border:1px solid #30363d;border-radius:8px;
            padding:12px;margin-bottom:8px;overflow-x:auto}}
  table{{width:100%;border-collapse:collapse;font-size:13px;min-width:600px}}
  th{{padding:8px;text-align:left;color:#8b949e;border-bottom:1px solid #30363d;font-size:11px}}
  td{{padding:8px;border-bottom:1px solid #21262d}}
  tr:hover td{{background:#1c2128}}
  a.back{{color:#58a6ff;font-size:13px;text-decoration:none;display:inline-block;margin-bottom:16px}}
</style></head><body>
<div class="layout">
  <div class="sidebar">
    <h2>📅 歷史報告</h2>
    <a href="index.html" class="date-link">
      <div class="date-label">← 今日報告</div>
    </a>
    {date_links if date_links else '<div style="color:#8b949e;font-size:12px">尚無歷史資料</div>'}
  </div>
  <div class="main">
    <h1>📚 蔡森掃描歷史報告</h1>
    <h2>最近 30 個交易日｜更新：{today}</h2>
    <label style="color:#8b949e;font-size:12px">型態框架</label>
    <select id="frameworkFilter" style="margin:8px 0 18px;padding:8px;border-radius:6px;background:#0f1117;color:#e1e4e8;border:1px solid #30363d;width:100%">
      <option value="ALL">ALL</option>
      <option value="W底">W底</option>
      <option value="M頭">M頭</option>
      <option value="頭肩底">頭肩底</option>
      <option value="頭肩頂">頭肩頂</option>
      <option value="旗形">旗形</option>
      <option value="三角形">三角形</option>
      <option value="假突破">假突破</option>
      <option value="破底翻">破底翻</option>
    </select>

    {sections if sections else '<p style="color:#8b949e">尚無歷史資料，請等待第一次掃描完成</p>'}
  </div>
</div>
<script>
const sel = document.getElementById('frameworkFilter');
sel.addEventListener('change', () => {
  const val = sel.value;
  document.querySelectorAll('table tr').forEach((tr, i) => {
    if (i === 0) return;
    const td = tr.querySelector('[data-framework]');
    if (!td) return;
    tr.style.display = (val === 'ALL' || td.dataset.framework === val) ? '' : 'none';
  });
});
</script></body></html>"""

def main():
    print("產出歷史報告...")
    try:
        from supabase_writer import get_history_summary
        records = get_history_summary(days=45)
        print(f"  取得 {len(records)} 筆歷史訊號")
    except Exception as e:
        print(f"  [警告] 無法取得歷史資料: {e}")
        records = []

    html = build_history_html(records)
    with open("history.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ history.html 產出完成")

if __name__ == "__main__":
    main()
