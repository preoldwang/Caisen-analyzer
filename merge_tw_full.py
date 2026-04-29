#!/usr/bin/env python3
"""
合併全台股四批次掃描結果，產出最終 HTML 報告
用法: python merge_tw_full.py
"""
import json, os, glob
from datetime import datetime

def load_chunks():
    chunks = []
    for i in range(1, 5):
        path = f"signals_chunk_{i}.json"
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                chunks.append(json.load(f))
            print(f"  ✅ 載入 {path}: {chunks[-1]['signal_count']} 個訊號")
        else:
            print(f"  ⚠️  找不到 {path}")
    return chunks

def build_html(all_signals, today, total_scanned):
    # 分類統計
    high_conf = [s for s in all_signals if s["confidence"] >= 0.75]
    high_rr   = [s for s in all_signals if s["rr"] >= 3.0]
    best      = [s for s in all_signals if s["confidence"] >= 0.75 and s["rr"] >= 3.0]

    # 依型態分組
    pattern_counts = {}
    for s in all_signals:
        pattern_counts[s["pattern"]] = pattern_counts.get(s["pattern"], 0) + 1
    pattern_tags = " ".join(
        f'<span class="badge badge-blue">{p} × {c}</span>'
        for p, c in sorted(pattern_counts.items(), key=lambda x: -x[1])
    )

    # 表格列
    def make_rows(signals, limit=None):
        rows = ""
        for s in (signals[:limit] if limit else signals):
            conf_pct = s["confidence"] * 100
            cc = "#3fb950" if conf_pct >= 75 else "#d29922"
            market_badge = '<span style="color:#58a6ff;font-size:11px">上市</span>' if s["market"]=="上市" else '<span style="color:#d29922;font-size:11px">上櫃</span>'
            rows += f"""<tr>
              <td><b>{s["ticker"]}</b> {market_badge}</td>
              <td>{s["name"]}</td>
              <td style="color:{cc}">{s["pattern"]}</td>
              <td style="color:{cc};font-weight:700">{conf_pct:.0f}%</td>
              <td>{s["entry"]:.2f}</td>
              <td style="color:#f85149">{s["stop_loss"]:.2f}</td>
              <td style="color:#3fb950">{s["target1"]:.2f}</td>
              <td style="color:#58a6ff">{s["target2"]:.2f}</td>
              <td>{s["rr"]}</td>
              <td style="font-size:12px;color:#8b949e">{s["signal_date"]}</td>
            </tr>"""
        if not signals:
            rows = '<tr><td colspan="10" style="text-align:center;padding:30px;color:#8b949e">📭 無符合條件訊號</td></tr>'
        return rows

    TABLE_HEADER = """<tr>
      <th>代號</th><th>名稱</th><th>型態</th><th>信心</th>
      <th>入場價</th><th>停損</th><th>目標一</th><th>目標二</th>
      <th>R:R</th><th>訊號日</th>
    </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>全台股蔡森掃描 {today}</title>
<style>
  *{{box-sizing:border-box}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
        background:#0f1117;color:#e1e4e8;padding:20px;margin:0}}
  h1{{color:#58a6ff;margin:0 0 4px}} h2{{color:#8b949e;font-size:14px;margin:0 0 20px}}
  h3{{color:#e1e4e8;font-size:16px;margin:24px 0 12px;border-left:3px solid #58a6ff;padding-left:10px}}
  .stats{{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}}
  .stat{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 18px;text-align:center;min-width:100px}}
  .stat .v{{font-size:22px;font-weight:700}} .stat .l{{font-size:11px;color:#8b949e;text-transform:uppercase;margin-top:2px}}
  .section{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px;margin-bottom:20px}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th{{padding:9px 8px;text-align:left;color:#8b949e;border-bottom:2px solid #30363d;font-size:11px;text-transform:uppercase}}
  td{{padding:9px 8px;border-bottom:1px solid #21262d;vertical-align:middle}}
  tr:hover td{{background:#1c2128}}
  .badge{{display:inline-block;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:600;margin:2px}}
  .badge-blue{{background:rgba(88,166,255,.15);color:#58a6ff}}
  .warn{{background:#1c1208;border:1px solid #d29922;border-radius:8px;padding:14px;
         margin-top:20px;color:#d29922;font-size:13px}}
  @media(max-width:600px){{.stats{{gap:8px}}.stat{{padding:10px}}table{{font-size:12px}}}}
</style></head><body>
<h1>🔍 全台股蔡森技術分析掃描</h1>
<h2>生成日期：{today}｜掃描：{total_scanned:,} 檔（上市＋上櫃）｜有效訊號：{len(all_signals)} 個</h2>

<div class="stats">
  <div class="stat"><div class="v" style="color:#58a6ff">{total_scanned:,}</div><div class="l">掃描檔數</div></div>
  <div class="stat"><div class="v" style="color:#3fb950">{len(all_signals)}</div><div class="l">有效訊號</div></div>
  <div class="stat"><div class="v" style="color:#3fb950">{len(high_conf)}</div><div class="l">信心≥75%</div></div>
  <div class="stat"><div class="v" style="color:#58a6ff">{len(high_rr)}</div><div class="l">R:R≥3</div></div>
  <div class="stat"><div class="v" style="color:#f0a830">{len(best)}</div><div class="l">精選(兩者)</div></div>
</div>

<div class="section">
  <div style="margin-bottom:8px;font-size:13px;color:#8b949e">型態分布：</div>
  {pattern_tags}
</div>

<h3>🥇 精選訊號（信心≥75% 且 R:R≥3）</h3>
<div class="section">
<table>{TABLE_HEADER}{make_rows(best)}</table>
</div>

<h3>📋 全部訊號（信心≥65% 且 R:R≥2）</h3>
<div class="section">
<table>{TABLE_HEADER}{make_rows(all_signals, limit=200)}</table>
{'<p style="text-align:center;color:#8b949e;font-size:13px">⚠️ 僅顯示前200筆</p>' if len(all_signals)>200 else ''}
</div>

<div class="warn">
  ⚠️ <b>免責聲明</b>：本工具基於蔡森技術分析方法論，僅供學習參考，不構成任何投資建議。<br>
  股市有風險，請嚴格執行停損，理性投資。過往表現不代表未來收益。
</div>
<p style="text-align:center;color:#484f58;font-size:12px;margin-top:20px">
  蔡森技術分析工具 v3.0 | Caisen-analyzer | Generated: {today}
</p>
</body></html>"""
    return html

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"{'='*60}")
    print(f"🔀 合併全台股掃描結果 — {today}")
    print(f"{'='*60}")

    chunks = load_chunks()
    if not chunks:
        print("❌ 找不到任何批次結果！")
        return

    all_signals = []
    total_scanned = 0
    for c in chunks:
        all_signals.extend(c.get("signals", []))
        total_scanned += c.get("scanned", 0)

    all_signals.sort(key=lambda x: x["confidence"], reverse=True)
    print(f"\n✅ 合併完成：掃描 {total_scanned:,} 檔，共 {len(all_signals)} 個訊號")

    html = build_html(all_signals, today, total_scanned)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    merged = {
        "date": today,
        "total_scanned": total_scanned,
        "signal_count": len(all_signals),
        "signals": all_signals
    }
    with open("signals.json", "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"📄 輸出：index.html + signals.json")

    # 清理批次暫存檔
    for i in range(1, 5):
        path = f"signals_chunk_{i}.json"
        if os.path.exists(path):
            os.remove(path)
            print(f"  🗑  清除 {path}")

if __name__ == "__main__":
    main()
