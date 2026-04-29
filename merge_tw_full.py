#!/usr/bin/env python3
"""
合併全台股四批次掃描結果 + 富邦權證橋接，產出最終 HTML 報告
"""
import json, os
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

def build_warrant_html(warrants):
    """產出權證清單的 HTML 片段"""
    if not warrants:
        return '<span style="color:#484f58;font-size:11px">—</span>'
    parts = []
    for w in warrants:
        parts.append(
            f'<span title="{w["name"]} | {w["moneyness"]} | 剩{w["days_left"]}天 | 均量{w["vol5"]}張" style="background:rgba(88,166,255,.1);color:#58a6ff;border:1px solid rgba(88,166,255,.3);border-radius:4px;padding:2px 6px;font-size:11px;margin:1px;display:inline-block;cursor:help">{w["code"]}<br><span style="color:#8b949e">{w["price"]}</span></span>'
        )
    return " ".join(parts)

def build_html(all_signals, warrant_map, today, total_scanned):
    high_conf = [s for s in all_signals if s["confidence"] >= 0.75]
    high_rr   = [s for s in all_signals if s["rr"] >= 3.0]
    best      = [s for s in all_signals if s["confidence"] >= 0.75 and s["rr"] >= 3.0]
    has_warrant = sum(1 for s in all_signals if s["ticker"] in warrant_map)

    pattern_counts = {}
    for s in all_signals:
        pattern_counts[s["pattern"]] = pattern_counts.get(s["pattern"], 0) + 1
    pattern_tags = " ".join(
        f'<span class="badge badge-blue">{p} × {c}</span>'
        for p, c in sorted(pattern_counts.items(), key=lambda x: -x[1])
    )

    def make_rows(signals, limit=None):
        rows = ""
        for s in (signals[:limit] if limit else signals):
            conf_pct = s["confidence"] * 100
            cc = "#3fb950" if conf_pct >= 75 else "#d29922"
            market_badge = '<span style="color:#58a6ff;font-size:11px">上市</span>'                 if s["market"] == "上市" else '<span style="color:#d29922;font-size:11px">上櫃</span>'
            warrants_html = build_warrant_html(warrant_map.get(s["ticker"], []))
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
              <td>{warrants_html}</td>
              <td style="font-size:12px;color:#8b949e">{s["signal_date"]}</td>
            </tr>"""
        if not signals:
            rows = '<tr><td colspan="11" style="text-align:center;padding:30px;color:#8b949e">📭 無符合條件訊號</td></tr>'
        return rows

    TABLE_HEADER = """<tr>
      <th>代號</th><th>名稱</th><th>型態</th><th>信心</th>
      <th>入場價</th><th>停損</th><th>目標一</th><th>目標二</th>
      <th>R:R</th><th>對應權證 ℹ️</th><th>訊號日</th>
    </tr>"""

    warrant_note = f'<p style="font-size:12px;color:#8b949e;margin:8px 0 0">ℹ️ 滑鼠移到權證代碼可查看：名稱、價內外、剩餘天數、5日均量。篩選條件：一般型認購、價外10–20%、剩餘≥60天、價格0.8–1.5元、均量≥200張</p>' if warrant_map else ""

    html = f"""<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>全台股蔡森掃描 {today}</title>
<style>
  *{{box-sizing:border-box}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0f1117;color:#e1e4e8;padding:20px;margin:0}}
  h1{{color:#58a6ff;margin:0 0 4px}} h2{{color:#8b949e;font-size:14px;margin:0 0 20px}}
  h3{{color:#e1e4e8;font-size:16px;margin:24px 0 12px;border-left:3px solid #58a6ff;padding-left:10px}}
  .stats{{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}}
  .stat{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 18px;text-align:center;min-width:100px}}
  .stat .v{{font-size:22px;font-weight:700}} .stat .l{{font-size:11px;color:#8b949e;text-transform:uppercase;margin-top:2px}}
  .section{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px;margin-bottom:20px;overflow-x:auto}}
  table{{width:100%;border-collapse:collapse;font-size:13px;min-width:900px}}
  th{{padding:9px 8px;text-align:left;color:#8b949e;border-bottom:2px solid #30363d;font-size:11px;text-transform:uppercase}}
  td{{padding:9px 8px;border-bottom:1px solid #21262d;vertical-align:middle}}
  tr:hover td{{background:#1c2128}}
  .badge{{display:inline-block;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:600;margin:2px}}
  .badge-blue{{background:rgba(88,166,255,.15);color:#58a6ff}}
  .warn{{background:#1c1208;border:1px solid #d29922;border-radius:8px;padding:14px;margin-top:20px;color:#d29922;font-size:13px}}
</style></head><body>
<h1>🔍 全台股蔡森技術分析掃描</h1>
<h2>生成日期：{today}｜掃描：{total_scanned:,} 檔（上市＋上櫃）｜有效訊號：{len(all_signals)} 個</h2>
<div class="stats">
  <div class="stat"><div class="v" style="color:#58a6ff">{total_scanned:,}</div><div class="l">掃描檔數</div></div>
  <div class="stat"><div class="v" style="color:#3fb950">{len(all_signals)}</div><div class="l">有效訊號</div></div>
  <div class="stat"><div class="v" style="color:#3fb950">{len(high_conf)}</div><div class="l">信心≥75%</div></div>
  <div class="stat"><div class="v" style="color:#58a6ff">{len(high_rr)}</div><div class="l">R:R≥3</div></div>
  <div class="stat"><div class="v" style="color:#f0a830">{len(best)}</div><div class="l">精選</div></div>
  <div class="stat"><div class="v" style="color:#a371f7">{has_warrant}</div><div class="l">附權證建議</div></div>
</div>
<div class="section">{pattern_tags}</div>
<h3>🥇 精選訊號（信心≥75% 且 R:R≥3）</h3>
<div class="section">
<table>{TABLE_HEADER}{make_rows(best)}</table>
{warrant_note}
</div>
<h3>📋 全部訊號（信心≥65% 且 R:R≥2）</h3>
<div class="section">
<table>{TABLE_HEADER}{make_rows(all_signals, limit=200)}</table>
{'<p style="text-align:center;color:#8b949e;font-size:13px">⚠️ 僅顯示前200筆</p>' if len(all_signals)>200 else ''}
</div>
<div class="warn">⚠️ <b>免責聲明</b>：本工具基於蔡森技術分析方法論，僅供學習參考，不構成任何投資建議。股市有風險，請嚴格執行停損，理性投資。</div>
<p style="text-align:center;color:#484f58;font-size:12px;margin-top:20px">蔡森技術分析工具 v4.0 | Caisen-analyzer | Generated: {today}</p>
</body></html>"""
    return html

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"{'='*60}")
    print(f"🔀 合併全台股掃描結果 + 權證橋接 — {today}")
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
    print(f"\n✅ 合併完成：{total_scanned:,} 檔，{len(all_signals)} 個訊號")

    # 權證橋接
    print("\n🔗 查詢對應權證...")
    try:
        from warrant_bridge import find_warrants_for_signals
        # 只對信心 ≥ 75% 的訊號查詢，減少 API 呼叫次數
        top_signals = [s for s in all_signals if s["confidence"] >= 0.75]
        warrant_map = find_warrants_for_signals(top_signals)
        print(f"   完成：{len(warrant_map)} 個訊號找到對應權證")
    except Exception as e:
        print(f"   [警告] 權證橋接失敗（{e}），報告仍正常產出")
        warrant_map = {}

    html = build_html(all_signals, warrant_map, today, total_scanned)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    merged = {
        "date": today,
        "total_scanned": total_scanned,
        "signal_count": len(all_signals),
        "signals": all_signals,
        "warrant_map": warrant_map
    }
    with open("signals.json", "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"📄 輸出：index.html + signals.json")

    for i in range(1, 5):
        path = f"signals_chunk_{i}.json"
        if os.path.exists(path):
            os.remove(path)

if __name__ == "__main__":
    main()
