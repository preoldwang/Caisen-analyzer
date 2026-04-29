#!/usr/bin/env python3
"""
合併 2Y 掃描批次結果 → 產出 index_2y.html（週線/月線強化版報告）
"""
import json, os, subprocess
from datetime import datetime

def load_chunks_2y():
    chunks = []
    for i in range(1, 5):
        path = f"signals_chunk_{i}_2y.json"
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
    return '<span style="background:#21262d;color:#8b949e;border-radius:4px;padding:1px 5px;font-size:11px;margin-left:4px">🆕</span>'

def build_html_2y(all_signals, consecutive_map, today, total_scanned):
    high_conf  = [s for s in all_signals if s["confidence"] >= 0.75]
    best       = [s for s in all_signals if s["confidence"] >= 0.75 and s["rr"] >= 2.0]
    weekly_pat = [s for s in all_signals if "周" in s.get("pattern","") or "週" in s.get("pattern","")]
    monthly_pat= [s for s in all_signals if "月" in s.get("pattern","")]

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
            days = consecutive_map.get(f"{s['ticker']}|{s['pattern']}", 1)
            streak = get_streak_badge(days)
            tf = s.get("timeframe", "daily")
            tf_color = "#a371f7" if tf in ("weekly","monthly") else "#8b949e"
            tf_label = f'<span style="color:{tf_color};font-size:11px">[{tf}]</span>'
            rows += f"""<tr>
              <td><b>{s["ticker"]}</b> {market_badge}</td>
              <td>{s["name"]}{streak}</td>
              <td style="color:{cc}">{s["pattern"]} {tf_label}</td>
              <td style="color:{cc};font-weight:700">{conf_pct:.0f}%</td>
              <td>{s["entry"]:.2f}</td>
              <td style="color:#f85149">{s["stop_loss"]:.2f}</td>
              <td style="color:#3fb950">{s["target1"]:.2f}</td>
              <td style="color:#58a6ff">{s["target2"]:.2f}</td>
              <td>{s["rr"]}</td>
            </tr>"""
        if not signals:
            rows = '<tr><td colspan="9" style="text-align:center;padding:30px;color:#8b949e">📭 無符合條件訊號</td></tr>'
        return rows

    TH = """<tr>
      <th>代號</th><th>名稱</th><th>型態 [框架]</th><th>信心</th>
      <th>入場價</th><th>停損</th><th>目標一</th><th>目標二</th><th>R:R</th>
    </tr>"""

    return f"""<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>全台股蔡森掃描（2年週月線強化版）{today}</title>
<style>
  *{{box-sizing:border-box}}
  body{{font-family:-apple-system,sans-serif;background:#0f1117;color:#e1e4e8;padding:20px;margin:0}}
  h1{{color:#a371f7;margin:0 0 4px}}
  h2{{color:#8b949e;font-size:14px;margin:0 0 20px}}
  h3{{color:#e1e4e8;font-size:16px;margin:24px 0 12px;border-left:3px solid #a371f7;padding-left:10px}}
  .nav{{margin-bottom:20px}}
  .nav a{{color:#58a6ff;text-decoration:none;font-size:13px;margin-right:12px;
          padding:6px 12px;background:#161b22;border:1px solid #30363d;border-radius:6px}}
  .nav a.active{{background:rgba(163,113,247,.15);border-color:#a371f7;color:#a371f7}}
  .stats{{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}}
  .stat{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 18px;text-align:center;min-width:90px}}
  .stat .v{{font-size:22px;font-weight:700}} .stat .l{{font-size:11px;color:#8b949e;text-transform:uppercase;margin-top:2px}}
  .section{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px;margin-bottom:20px;overflow-x:auto}}
  table{{width:100%;border-collapse:collapse;font-size:13px;min-width:780px}}
  th{{padding:9px 8px;text-align:left;color:#8b949e;border-bottom:2px solid #30363d;font-size:11px;text-transform:uppercase}}
  td{{padding:9px 8px;border-bottom:1px solid #21262d;vertical-align:middle}}
  tr:hover td{{background:#1c2128}}
  .badge{{display:inline-block;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:600;margin:2px}}
  .badge-blue{{background:rgba(88,166,255,.15);color:#58a6ff}}
  .note{{background:#130d1f;border:1px solid #a371f7;border-radius:8px;padding:14px;margin-bottom:20px;color:#c9a7ff;font-size:13px}}
  .warn{{background:#1c1208;border:1px solid #d29922;border-radius:8px;padding:14px;margin-top:20px;color:#d29922;font-size:13px}}
</style></head><body>
<h1>🔭 全台股蔡森掃描 — 2年週月線強化版</h1>
<h2>生成日期：{today}｜掃描：{total_scanned:,} 檔｜有效訊號：{len(all_signals)} 個（資料期間：2年）</h2>
<div class="nav">
  <a href="index.html">📊 標準版（1年日線）</a>
  <a href="index_2y.html" class="active">🔭 強化版（2年週月線）</a>
  <a href="history.html">📚 歷史報告</a>
</div>
<div class="note">
  🔭 <b>強化版說明</b>：使用 2 年日K線資料，自動合成週線與月線，可偵測週線破底翻、月線頭肩型態、康波周期等大型態。
  同一支股票在此版本出現訊號，代表更大時間框架也形成結構，可信度高於標準版。
  標記 <span style="color:#a371f7">[weekly]</span> / <span style="color:#a371f7">[monthly]</span> 為週線/月線訊號。
</div>
<div class="stats">
  <div class="stat"><div class="v" style="color:#58a6ff">{total_scanned:,}</div><div class="l">掃描檔數</div></div>
  <div class="stat"><div class="v" style="color:#3fb950">{len(all_signals)}</div><div class="l">有效訊號</div></div>
  <div class="stat"><div class="v" style="color:#3fb950">{len(high_conf)}</div><div class="l">信心≥75%</div></div>
  <div class="stat"><div class="v" style="color:#a371f7">{len(weekly_pat)}</div><div class="l">週線訊號</div></div>
  <div class="stat"><div class="v" style="color:#f0a830">{len(monthly_pat)}</div><div class="l">月線訊號</div></div>
</div>
<div class="section">{pattern_tags}</div>
<h3>🥇 精選訊號（信心≥75% 且 R:R≥2）</h3>
<div class="section"><table>{TH}{make_rows(best)}</table></div>
<h3>📋 全部訊號</h3>
<div class="section"><table>{TH}{make_rows(all_signals, limit=200)}</table></div>
<div class="warn">⚠️ <b>免責聲明</b>：本工具基於蔡森技術分析方法論，僅供學習參考，不構成任何投資建議。</div>
<p style="text-align:center;color:#484f58;font-size:12px;margin-top:20px">蔡森技術分析工具 v4.1（2年強化版）| {today}</p>
</body></html>"""

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"{'='*60}\n🔭 合併 2Y 掃描結果 — {today}\n{'='*60}")

    chunks = load_chunks_2y()
    if not chunks:
        print("❌ 找不到 2Y 批次結果！"); return

    all_signals, total_scanned = [], 0
    for c in chunks:
        all_signals.extend(c.get("signals", []))
        total_scanned += c.get("scanned", 0)
    all_signals.sort(key=lambda x: x["confidence"], reverse=True)
    print(f"\n✅ 合併：{total_scanned:,} 檔，{len(all_signals)} 個訊號")

    # 查詢持續天數（共用 Supabase）
    try:
        from supabase_writer import get_consecutive_days
        consecutive_map = get_consecutive_days(all_signals, today)
    except Exception as e:
        print(f"  [警告] 持續天數查詢失敗: {e}")
        consecutive_map = {}

    html = build_html_2y(all_signals, consecutive_map, today, total_scanned)
    with open("index_2y.html", "w", encoding="utf-8") as f:
        f.write(html)

    with open("signals_2y.json", "w", encoding="utf-8") as f:
        json.dump({"date": today, "period": "2y", "total_scanned": total_scanned,
                   "signal_count": len(all_signals), "signals": all_signals},
                  f, ensure_ascii=False, indent=2)

    print(f"📄 輸出：index_2y.html + signals_2y.json")
    for i in range(1, 5):
        p = f"signals_chunk_{i}_2y.json"
        if os.path.exists(p): os.remove(p)

if __name__ == "__main__":
    main()
