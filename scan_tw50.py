#!/usr/bin/env python3
"""台股50破底翻每日掃描 — GitHub Actions 版"""

import sys, json, os
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))
from cai_sen_analyzer import CaiSenAnalyzer

TW50 = {
    "2330.TW": "台積電", "2317.TW": "鴻海", "2454.TW": "聯發科",
    "2308.TW": "台達電", "2382.TW": "廣達", "2303.TW": "聯電",
    "3711.TW": "日月光投控", "2002.TW": "中鋼", "1301.TW": "台塑",
    "1303.TW": "南亞", "1326.TW": "台化", "6505.TW": "台塑化",
    "2412.TW": "中華電", "2882.TW": "國泰金", "2881.TW": "富邦金",
    "2886.TW": "兆豐金", "2891.TW": "中信金", "2884.TW": "玉山金",
    "2885.TW": "元大金", "2892.TW": "第一金", "5880.TW": "合庫金",
    "2880.TW": "華南金", "2887.TW": "台新金", "2888.TW": "新光金",
    "2890.TW": "永豐金", "2883.TW": "開發金", "2609.TW": "陽明",
    "2615.TW": "萬海", "2603.TW": "長榮", "2408.TW": "南亞科",
    "3034.TW": "聯詠", "2379.TW": "瑞昱", "2395.TW": "研華",
    "4904.TW": "遠傳", "4938.TW": "和碩", "3008.TW": "大立光",
    "2357.TW": "華碩", "2353.TW": "宏碁", "2376.TW": "技嘉",
    "2344.TW": "華邦電", "2449.TW": "京元電子", "3231.TW": "緯創",
    "2301.TW": "光寶科", "2324.TW": "仁寶", "6669.TW": "緯穎",
    "2368.TW": "金像電", "1216.TW": "統一", "2912.TW": "統一超",
    "1101.TW": "台泥", "9910.TW": "豐泰",
}

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    signals = []

    for ticker, name in TW50.items():
        try:
            print(f"掃描 {name} ({ticker})...")
            analyzer = CaiSenAnalyzer(ticker)
            analyzer.fetch_data(period="1y")
            result = analyzer.analyze()
            for p in result.patterns:
                if p.confidence >= 0.65 and p.risk_reward_ratio >= 2.0:
                    signals.append({
                        "ticker": ticker, "name": name,
                        "pattern": p.pattern_type.value,
                        "confidence": round(p.confidence, 2),
                        "neckline": round(p.neckline, 2),
                        "entry": round(p.entry_price, 2),
                        "stop_loss": round(p.stop_loss, 2),
                        "target1": round(p.target_price, 2),
                        "target2": round(p.target_price_2, 2),
                        "rr": round(p.risk_reward_ratio, 1),
                        "date": p.signal_date,
                    })
        except Exception as e:
            print(f"  跳過 {ticker}: {e}")

    signals.sort(key=lambda x: x["confidence"], reverse=True)

    rows = ""
    for s in signals:
        conf_pct = s["confidence"] * 100
        conf_color = "#3fb950" if conf_pct >= 75 else "#d29922"
        rows += f"""
        <tr>
          <td><b>{s["ticker"]}</b></td>
          <td>{s["name"]}</td>
          <td style="color:{conf_color}">{s["pattern"]}</td>
          <td style="color:{conf_color}">{conf_pct:.0f}%</td>
          <td>{s["entry"]:.2f}</td>
          <td style="color:#f85149">{s["stop_loss"]:.2f}</td>
          <td style="color:#3fb950">{s["target1"]:.2f}</td>
          <td style="color:#58a6ff">{s["target2"]:.2f}</td>
          <td>{s["rr"]}</td>
          <td>{s["date"]}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>台股蔡森掃描 {today}</title>
<style>
  body{{font-family:-apple-system,sans-serif;background:#0f1117;color:#e1e4e8;padding:24px;margin:0}}
  h1{{color:#58a6ff;margin-bottom:4px}} .sub{{color:#8b949e;font-size:13px;margin-bottom:24px}}
  .stats{{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap}}
  .stat{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px 20px;text-align:center}}
  .stat .v{{font-size:24px;font-weight:700;color:#58a6ff}} .stat .l{{font-size:11px;color:#8b949e;text-transform:uppercase}}
  table{{width:100%;border-collapse:collapse;font-size:14px}}
  th{{background:#161b22;padding:10px 8px;text-align:left;color:#8b949e;border-bottom:2px solid #30363d;font-size:12px;text-transform:uppercase}}
  td{{padding:10px 8px;border-bottom:1px solid #21262d;vertical-align:middle}}
  tr:hover td{{background:#1c2128}}
  .warn{{background:#1c1208;border:1px solid #d29922;border-radius:8px;padding:14px;margin-top:24px;color:#d29922;font-size:13px}}
  .empty{{text-align:center;padding:40px;color:#8b949e}}
</style></head><body>
<h1>🔍 台股蔡森技術分析掃描</h1>
<div class="sub">生成日期：{today} ｜ 掃描標的：{len(TW50)} 檔台股50成分股 ｜ 訊號數：{len(signals)}</div>
<div class="stats">
  <div class="stat"><div class="v">{len(TW50)}</div><div class="l">掃描檔數</div></div>
  <div class="stat"><div class="v" style="color:#3fb950">{len(signals)}</div><div class="l">有效訊號</div></div>
  <div class="stat"><div class="v" style="color:#3fb950">{len([s for s in signals if s["confidence"]>=0.75])}</div><div class="l">高信心 ≥75%</div></div>
  <div class="stat"><div class="v" style="color:#58a6ff">{len([s for s in signals if s["rr"]>=3])}</div><div class="l">R:R ≥ 3</div></div>
</div>
<table>
<tr><th>代號</th><th>名稱</th><th>型態</th><th>信心</th><th>入場價</th><th>停損</th><th>目標一</th><th>目標二</th><th>R:R</th><th>訊號日</th></tr>
{rows if rows else '<tr><td colspan="10" class="empty">📭 今日無符合條件訊號（信心≥65% + R:R≥2）</td></tr>'}
</table>
<div class="warn">
  ⚠️ <b>免責聲明</b>：本工具基於蔡森技術分析方法論，僅供學習參考，不構成任何投資建議。<br>
  股市有風險，請嚴格執行停損，理性投資。過往表現不代表未來收益。
</div>
</body></html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open("signals.json", "w", encoding="utf-8") as f:
        json.dump({"date": today, "count": len(signals), "signals": signals}, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！找到 {len(signals)} 個訊號")
    print(f"   輸出：index.html + signals.json")

if __name__ == "__main__":
    main()
