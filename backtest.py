#!/usr/bin/env python3
"""
蔡森回測器 — 視覺回測用
用法: python backtest.py --tickers 2330 2454 2382 --days 60
輸出: backtest_report/YYYY-MM-DD/[ticker]/ 各含 K 線圖 PNG
"""
import sys, os, argparse
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cai_sen_analyzer import CaiSenAnalyzer

# ─── 台股預設回測清單（可透過 --tickers 覆蓋）───────────────────────────────
DEFAULT_TICKERS = [
    "2330","2317","2454","2382","2412","2308","2881","2882","2886","2891",
    "3711","2303","2357","2379","2395","6669","2002","1301","1303","2207",
    "2610","2615","2618","2633","5880","6505","1216","2912","2474","3034"
]

# ─── 工具函式 ────────────────────────────────────────────────────────────────
def get_trading_dates(full_df, n_days):
    """從完整資料取最近 n_days 個交易日索引"""
    all_dates = full_df.index.normalize().unique().sort_values()
    # 排除最後一天（留作「之後走勢」驗證用）
    all_dates = all_dates[:-1]
    return all_dates[-n_days:]

def candlestick_on_ax(ax, df):
    """在 ax 畫蠟燭圖（不依賴 mplfinance）"""
    df = df.reset_index()
    x = range(len(df))
    for i, row in df.iterrows():
        color = "#d62728" if row["Close"] >= row["Open"] else "#1f77b4"
        # 實體
        ax.bar(i, abs(row["Close"] - row["Open"]),
               bottom=min(row["Open"], row["Close"]),
               width=0.6, color=color, linewidth=0)
        # 影線
        ax.plot([i, i], [row["Low"], row["High"]], color=color, linewidth=0.8)
    ax.set_xticks(x[::max(1, len(x)//8)])
    ax.set_xticklabels(df["Date"].dt.strftime("%m/%d").iloc[::max(1, len(x)//8)],
                       fontsize=7, rotation=30)
    ax.yaxis.tick_right()
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(axis="y", linestyle="--", alpha=0.3)

def draw_signal_chart(ticker, name, signal_date, pattern, confidence, rr,
                      entry, stop_loss, target1, target2,
                      pre_df, post_df, out_path):
    """產生單一訊號的視覺回測圖（訊號前60天 + 後20天）"""
    fig = plt.figure(figsize=(14, 7), facecolor="#0d1117")
    gs = GridSpec(2, 1, height_ratios=[3, 1], hspace=0.05, figure=fig)

    ax_k  = fig.add_subplot(gs[0])
    ax_vol = fig.add_subplot(gs[1], sharex=ax_k)

    for ax in [ax_k, ax_vol]:
        ax.set_facecolor("#161b22")
        for sp in ax.spines.values():
            sp.set_color("#30363d")

    # 合併前後資料，加標記欄
    all_df = pd.concat([pre_df, post_df]).drop_duplicates()
    all_df = all_df.sort_index()
    all_df_reset = all_df.reset_index()

    # 找訊號日在 x 軸的位置
    sig_ts = pd.Timestamp(signal_date)
    pre_len = len(pre_df)

    # 蠟燭圖
    for i, row in all_df_reset.iterrows():
        color = "#f85149" if row["Close"] >= row["Open"] else "#58a6ff"
        alpha = 1.0 if i < pre_len else 0.45   # 訊號後淡顯示（讓用眼驗證）
        ax_k.bar(i, abs(row["Close"] - row["Open"]),
                 bottom=min(row["Open"], row["Close"]),
                 width=0.6, color=color, alpha=alpha, linewidth=0)
        ax_k.plot([i, i], [row["Low"], row["High"]],
                  color=color, alpha=alpha, linewidth=0.8)
        # 成交量
        ax_vol.bar(i, row["Volume"], width=0.6, color=color, alpha=alpha*0.7, linewidth=0)

    # 訊號日垂直線
    ax_k.axvline(pre_len - 1, color="#f0e68c", linewidth=1.2,
                 linestyle="--", alpha=0.85, label="訊號日")

    # 關鍵價位水平線
    for val, color, label in [
        (entry,    "#2ea043", f"進場 {entry:.2f}"),
        (stop_loss,"#f85149", f"停損 {stop_loss:.2f}"),
        (target1,  "#58a6ff", f"目標1 {target1:.2f}"),
        (target2,  "#a371f7", f"目標2 {target2:.2f}"),
    ]:
        ax_k.axhline(val, color=color, linewidth=0.9, linestyle=":",
                     alpha=0.9, label=label)

    # 分隔線（訊號後區域背景）
    ax_k.axvspan(pre_len - 1, len(all_df_reset) - 1,
                 alpha=0.06, color="#f0e68c")

    # 標題
    ax_k.set_title(
        f"{ticker} {name}  ▸  {pattern}  "
        f"| 信心 {confidence:.0%}  R:R {rr:.1f}  | 訊號日 {signal_date}",
        color="#e6edf3", fontsize=11, loc="left", pad=8
    )

    # 圖例
    handles = [mpatches.Patch(color=c, label=l) for _, c, l in [
        (None,"#2ea043", f"進場 {entry:.2f}"),
        (None,"#f85149", f"停損 {stop_loss:.2f}"),
        (None,"#58a6ff", f"目標1 {target1:.2f}"),
        (None,"#a371f7", f"目標2 {target2:.2f}"),
        (None,"#f0e68c", "訊號後走勢（淡色）"),
    ]]
    ax_k.legend(handles=handles, loc="upper left", fontsize=7,
                facecolor="#161b22", edgecolor="#30363d", labelcolor="#e6edf3")

    ax_k.tick_params(colors="#8b949e", labelsize=7)
    ax_vol.tick_params(colors="#8b949e", labelsize=7)
    ax_vol.set_ylabel("Volume", color="#8b949e", fontsize=7)

    # X 軸日期標籤（只在 vol 顯示）
    step = max(1, len(all_df_reset) // 10)
    ax_vol.set_xticks(range(0, len(all_df_reset), step))
    ax_vol.set_xticklabels(
        all_df_reset["Date"].dt.strftime("%m/%d").iloc[::step],
        fontsize=7, rotation=30, color="#8b949e"
    )
    plt.setp(ax_k.get_xticklabels(), visible=False)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)

# ─── 主邏輯 ──────────────────────────────────────────────────────────────────
def run_backtest(ticker_codes, n_days=60, forward_days=20, period="2y",
                 out_root="backtest_report"):
    total_signals = 0

    for code in ticker_codes:
        sym = f"{code}.TW" if not code.endswith((".TW",".TWO")) else code
        print(f"\n{'─'*55}")
        print(f"▶ {sym}  抓取 {period} 資料...")

        try:
            az = CaiSenAnalyzer()
            full_df = az.fetch_data(symbol=sym, period=period)
        except Exception as e:
            print(f"  ✗ 抓資料失敗: {e}")
            continue

        # 取名稱（若有 Supabase 或本地 cache 可改）
        name = sym

        trading_dates = get_trading_dates(full_df, n_days)
        print(f"  回測 {len(trading_dates)} 個交易日...")

        ticker_signals = 0
        for cut_date in trading_dates:
            pre_df = full_df[full_df.index.normalize() <= cut_date]
            if len(pre_df) < 60:
                continue

            try:
                az2 = CaiSenAnalyzer()
                az2.data        = pre_df.copy()
                az2.symbol      = sym
                # 重建週/月線
                az2.weekly_data  = pre_df.resample("W").agg({
                    "Open":"first","High":"max","Low":"min",
                    "Close":"last","Volume":"sum"}).dropna()
                az2.monthly_data = pre_df.resample("ME").agg({
                    "Open":"first","High":"max","Low":"min",
                    "Close":"last","Volume":"sum"}).dropna()
                result = az2.analyze()
            except Exception as e:
                continue

            for p in result.patterns:
                if p.confidence < 0.65 or p.risk_reward_ratio < 2.0:
                    continue

                # 後續走勢
                post_df = full_df[full_df.index.normalize() > cut_date].head(forward_days)

                # 輸出路徑: backtest_report/TICKER/SIGNAL_DATE_PATTERN.png
                safe_pattern = p.pattern_type.value.replace("/","_").replace(" ","_")
                out_dir  = os.path.join(out_root, sym.replace(".", "_"))
                out_file = os.path.join(out_dir,
                    f"{cut_date.strftime('%Y%m%d')}_{safe_pattern}.png")

                if os.path.exists(out_file):
                    continue  # 已存在跳過

                # 取前60根 K 棒做背景圖
                chart_pre  = pre_df.tail(60)
                chart_post = post_df

                draw_signal_chart(
                    ticker=sym, name=name,
                    signal_date=cut_date.strftime("%Y-%m-%d"),
                    pattern=p.pattern_type.value,
                    confidence=p.confidence,
                    rr=p.risk_reward_ratio,
                    entry=p.entry_price, stop_loss=p.stop_loss,
                    target1=p.target_price, target2=p.target_price_2,
                    pre_df=chart_pre, post_df=chart_post,
                    out_path=out_file
                )
                ticker_signals += 1
                total_signals  += 1
                print(f"  ✅ {cut_date.date()} {p.pattern_type.value} "
                      f"conf={p.confidence:.0%} RR={p.risk_reward_ratio:.1f} → {out_file}")

        print(f"  └ {sym} 共 {ticker_signals} 個訊號圖")

    print(f"\n{'='*55}")
    print(f"✅ 回測完成，共 {total_signals} 張圖，存於 ./{out_root}/")

# ─── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="蔡森視覺回測器")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS,
                        help="股票代碼，如 2330 2454（不含 .TW）")
    parser.add_argument("--days",    type=int, default=60,
                        help="回看幾個交易日（預設 60）")
    parser.add_argument("--forward", type=int, default=20,
                        help="訊號後顯示幾個交易日走勢（預設 20）")
    parser.add_argument("--period",  default="2y",
                        help="yfinance 抓取長度（預設 2y）")
    parser.add_argument("--out",     default="backtest_report",
                        help="輸出目錄（預設 backtest_report）")
    args = parser.parse_args()

    run_backtest(
        ticker_codes=args.tickers,
        n_days=args.days,
        forward_days=args.forward,
        period=args.period,
        out_root=args.out,
    )
