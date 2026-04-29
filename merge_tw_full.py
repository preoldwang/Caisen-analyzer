#!/usr/bin/env python3
"""
合併全台股四批次 + 富邦權證橋接 + Supabase 歷史寫入 → 產出 HTML 報告
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

def get_streak_badge(days):
    if days >= 3:
        return f'<span title="連續出現{days}天" style="background:rgba(63,185,80,.2);color:#3fb950;border:1px solid rgba(63,185,80,.4);border-radius:4px;padding:1px 5px;font-size:11px;margin-left:4px">🔥 {days}天</span>'
    elif days == 2:
        return f'<span title="連續出現{days}天" style="background:rgba(210,153,34,.15);color:#d29922;border:1px solid rgba(210,153,34,.4);border-radius:4px;padding:1px 5px;font-size:11px;margin-left:4px">🔁 2天</span>'
    else:
        return '<span style="background:#21262d;color:#8b949e;border-radius:4px;padding:1px 5px;font-size:11px;margin-left:4px">🆕</span>'

def build_warrant_html(warrants):
    if not warrants:
        return '<span style="color:#484f58;font-size:11px">—</span>'
    parts = []
    for w in warrants:
        parts.append(
            f'<span title="{w["name"]} | {w["moneyness"]} | 剩{w["days_left"]}天 | 均量{w["vol5"]}張" style="background:rgba(88,166,255,.1);color:#58a6ff;border:1px solid rgba(88,166,255,.3);border-radius:4px;padding:2px 6px;font-size:11px;margin:1px;display:inline-block;cursor:help">{w["code"]}<br><span style="color:#8b949e">{w["price"]}</span></span>'
        )
    return " ".join(parts)

def build_html(all_signals, warrant_map, consecutive_map, today, total_scanned):
    high_conf = [s for s in all_signals if s["confidence"] >= 0.75]
    high_rr   = [s for s in all_signals if s["rr"] >= 3.0]
    best      = [s for s in all_signals if s["confidence"] >= 0.75 and s["rr"] >= 3.0]
    multi_day = [s for s in all_signals if consecutive_map.get(f"{s['ticker']}|{s['pattern']}", 1) >= 2]

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
            conf_pct  = s["confidence"] * 100
            cc = "#3fb950" if conf_pct >= 75 else "#d29922"
            market_badge = '<span style="color:#58a6ff;font-size:11px">上市</span>'                 if s["market"] == "上市" else '<span style="color:#d29922;font-size:11px">上櫃</span>'
            days = consecutive_map.get(f"{s['ticker']}|{s['pattern']}", 1)
            streak_html   = get_streak_badge(days)
            warrants_html = build_warrant_html(warrant_map.get(s["ticker"], []))
            rows += f"""<tr>
              <td><b>{s["ticker"]}</b> {market_badge}</td>
              <td>{s["name"]}{streak_html}</td>
              <td style="color:{cc}">{s["pattern"]}</td>
              <td style="color:{cc};font-weight:700">{conf_pct:.0f}%</td>
              <td>{s["entry"]:.2f}</td>
              <td style="color:#f85149">{s["stop_loss"]:.2f}</td>
              <td style="color:#3fb950">{s["target1"]:.2f}</td>
              <td style="color:#58a6ff">{s["target2"]:.2f}</td>
              <td>{s["rr"]}</td>
              <td>{warrants_html}</td>
            </tr>"""
        if not signals:
            rows = '<tr><td colspan="10" style="text-align:center;padding:30px;color:#8b949e">📭 無符合條件訊號</td></tr>'
        return rows

    TH = """<tr>
      <th>代號</th><th>名稱</th><th>型態</th><th>信心</th>
      <th>入場價</th><th>停損</th><th>目標一</th><th>目標二</th>
      <th>R:R</th><th>對應權證</th>
    </tr>"""

    return f"""<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>全台股蔡森掃描 {today}</title>
<style>
  *{{box-sizing:border-box}}
  body{{font-family:-apple-system,sans-serif;background:#0f1117;color:#e1e4e8;padding:20px;margin:0}}
  h1{{color:#58a6ff;margin:0 0 4px}} h2{{color:#8b949e;font-size:14px;margin:0 0 20px}}
  h3{{color:#e1e4e8;font-size:16px;margin:24px 0 12px;border-left:3px solid #58a6ff;padding-left:10px}}
  .nav{{margin-bottom:20px}}
  .nav a{{color:#58a6ff;text-decoration:none;font-size:13px;margin-right:16px;
          padding:6px 12px;background:#161b22;border:1px solid #30363d;border-radius:6px}}
  .stats{{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}}
  .stat{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 18px;text-align:center;min-width:90px}}
  .stat .v{{font-size:22px;font-weight:700}} .stat .l{{font-size:11px;color:#8b949e;text-transform:uppercase;margin-top:2px}}
  .section{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px;margin-bottom:20px;overflow-x:auto}}
  table{{width:100%;border-collapse:collapse;font-size:13px;min-width:850px}}
  th{{padding:9px 8px;text-align:left;color:#8b949e;border-bottom:2px solid #30363d;font-size:11px;text-transform:uppercase}}
  td{{padding:9px 8px;border-bottom:1px solid #21262d;vertical-align:middle}}
  tr:hover td{{background:#1c2128}}
  .badge{{display:inline-block;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:600;margin:2px}}
  .badge-blue{{background:rgba(88,166,255,.15);color:#58a6ff}}
  .warn{{background:#1c1208;border:1px solid #d29922;border-radius:8px;padding:14px;margin-top:20px;color:#d29922;font-size:13px}}
</style></head><body>
<h1>🔍 全台股蔡森技術分析掃描</h1>
<h2>生成日期：{today}｜掃描：{total_scanned:,} 檔（上市＋上櫃）｜有效訊號：{len(all_signals)} 個</h2>
<div class="nav">
  <a href="index.html">📊 今日報告</a>
  <a href="history.html">📚 歷史報告</a>
</div>
<div class="stats">
  <div class="stat"><div class="v" style="color:#58a6ff">{total_scanned:,}</div><div class="l">掃描檔數</div></div>
  <div class="stat"><div class="v" style="color:#3fb950">{len(all_signals)}</div><div class="l">有效訊號</div></div>
  <div class="stat"><div class="v" style="color:#3fb950">{len(high_conf)}</div><div class="l">信心≥75%</div></div>
  <div class="stat"><div class="v" style="color:#f0a830">{len(best)}</div><div class="l">精選</div></div>
  <div class="stat"><div class="v" style="color:#a371f7">{len(multi_day)}</div><div class="l">持續≥2天</div></div>
</div>
<div class="section">{pattern_tags}</div>
<h3>🥇 精選訊號（信心≥75% 且 R:R≥3）</h3>
<div class="section"><table>{TH}{make_rows(best)}</table></div>
<h3>📋 全部訊號（信心≥65% 且 R:R≥2）</h3>
<div class="section"><table>{TH}{make_rows(all_signals, limit=200)}</table>
{"<p style='text-align:center;color:#8b949e;font-size:13px'>⚠️ 僅顯示前200筆</p>" if len(all_signals)>200 else ""}
</div>
<div class="warn">⚠️ <b>免責聲明</b>：本工具基於蔡森技術分析方法論，僅供學習參考，不構成任何投資建議。</div>
<p style="text-align:center;color:#484f58;font-size:12px;margin-top:20px">蔡森技術分析工具 v4.1 | {today}</p>
</body></html>"""

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"{'='*60}\n🔀 合併 + 權證橋接 + DB 寫入 — {today}\n{'='*60}")

    chunks = load_chunks()
    if not chunks:
        print("❌ 找不到批次結果！"); return

    all_signals = []
    total_scanned = 0
    for c in chunks:
        all_signals.extend(c.get("signals", []))
        total_scanned += c.get("scanned", 0)
    all_signals.sort(key=lambda x: x["confidence"], reverse=True)
    print(f"\n✅ 合併：{total_scanned:,} 檔，{len(all_signals)} 個訊號")

    # 1. Supabase 寫入今日訊號
    print("\n📥 寫入 Supabase...")
    try:
        from supabase_writer import upsert_signals, get_consecutive_days
        upsert_signals(all_signals, today)
        consecutive_map = get_consecutive_days(all_signals, today)
        multi = sum(1 for v in consecutive_map.values() if v >= 2)
        print(f"   連續訊號統計：{multi} 個持續 ≥2 天")
    except Exception as e:
        print(f"   [警告] Supabase 操作失敗 ({e})，繼續產出報告")
        consecutive_map = {}

    # 2. 權證橋接
    print("\n🔗 查詢對應權證...")
    try:
        from warrant_bridge import find_warrants_for_signals
        top = [s for s in all_signals if s["confidence"] >= 0.75]
        warrant_map = find_warrants_for_signals(top)
        print(f"   {len(warrant_map)} 個訊號找到對應權證")
    except Exception as e:
        print(f"   [警告] 權證橋接失敗 ({e})")
        warrant_map = {}

    # 3. 產出 HTML
    html = build_html(all_signals, warrant_map, consecutive_map, today, total_scanned)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    # 4. 產出歷史頁面
    try:
        import subprocess
        subprocess.run(["python", "build_history.py"], check=True)
    except Exception as e:
        print(f"   [警告] history.html 產出失敗: {e}")

    # 5. 存 JSON
    with open("signals.json", "w", encoding="utf-8") as f:
        json.dump({"date": today, "total_scanned": total_scanned,
                   "signal_count": len(all_signals), "signals": all_signals,
                   "warrant_map": warrant_map, "consecutive": consecutive_map},
                  f, ensure_ascii=False, indent=2)

    print(f"\n📄 輸出：index.html + history.html + signals.json")
    for i in range(1, 5):
        p = f"signals_chunk_{i}.json"
        if os.path.exists(p): os.remove(p)

if __name__ == "__main__":
    main()
