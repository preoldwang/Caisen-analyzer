#!/usr/bin/env python3
"""
蔡森技术分析 - 12个月滚动回测 (Cai Sen 12-Month Rolling Backtest)
==================================================================
对9个标的在12个月度检查点进行系统性回测
输出完整报告到控制台 + backtest_12m_results.json
"""

import sys
import json
import traceback
from datetime import datetime, timedelta
from dataclasses import asdict
from typing import Optional, List, Dict, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, '/root/.openclaw/workspace/Caisen-analyzer')
from cai_sen_analyzer import CaiSenAnalyzer, SignalType, Trend

# ── Configuration ──────────────────────────────────────────────

INSTRUMENTS = {
    "0916.HK":  "China Longyuan Power",
    "1880.HK":  "LVMH (Luxury)",
    "0728.HK":  "China Telecom",
    "0788.HK":  "China Tower",
    "2318.HK":  "Ping An Insurance",
    "0836.HK":  "China Resources Power",
    "9961.HK":  "Trip.com",
    "2050.HK":  "361 Degrees",
    "GC=F":     "Gold Futures",
}

# 12 monthly checkpoints: 1st trading day of each month
# We'll compute exact dates after downloading data
CHECKPOINT_MONTHS = [
    ("2025-05", "May 2025"),
    ("2025-06", "Jun 2025"),
    ("2025-07", "Jul 2025"),
    ("2025-08", "Aug 2025"),
    ("2025-09", "Sep 2025"),
    ("2025-10", "Oct 2025"),
    ("2025-11", "Nov 2025"),
    ("2025-12", "Dec 2025"),
    ("2026-01", "Jan 2026"),
    ("2026-02", "Feb 2026"),
    ("2026-03", "Mar 2026"),
    ("2026-04", "Apr 2026"),
]

VERIFY_DAYS = 22  # ~1 month of trading days

# BULLISH vs BEARISH classification
BULLISH_SIGNAL_NAMES = {
    "破底翻", "W底", "头肩底", "岛型反转(底)", "量先价行",
    "颈线突破", "回踩支撑", "真突破", "底部放量突破", "V型反转",
    "量价背离(上行)", "康波上行期", "月线缩量见底", "棒康多点", "对数图量幅",
}

BEARISH_SIGNAL_NAMES = {
    "假突破", "颈线跌破", "头肩顶", "M顶", "岛型反转(顶)",
    "反弹无力", "跌破支撑", "量价背离(下行)", "康波下行期",
    "月线爆量翻黑", "棒康空点", "骗线确认",
}


def is_bullish(signal_type: SignalType) -> bool:
    return signal_type.value in BULLISH_SIGNAL_NAMES


def is_bearish(signal_type: SignalType) -> bool:
    return signal_type.value in BEARISH_SIGNAL_NAMES


# ── Data Download ──────────────────────────────────────────────

def download_all_data() -> Dict[str, pd.DataFrame]:
    """Download 2y of data for all instruments."""
    data = {}
    for ticker, name in INSTRUMENTS.items():
        print(f"  📥 {ticker} ({name})...", end=" ", flush=True)
        try:
            t = yf.Ticker(ticker)
            df = t.history(period="2y", auto_adjust=False)
            if df.empty:
                print("⚠️ EMPTY")
                continue
            # Normalize timezone
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            print(f"✅ {len(df)} rows ({df.index[0].date()} → {df.index[-1].date()})")
            data[ticker] = df
        except Exception as e:
            print(f"❌ {e}")
    return data


# ── Checkpoint Logic ───────────────────────────────────────────

def get_checkpoint_date(df: pd.DataFrame, month_str: str) -> Optional[pd.Timestamp]:
    """Find the 1st trading day of the given month in the dataframe."""
    year, month = int(month_str[:4]), int(month_str[5:7])
    mask = (df.index.year == year) & (df.index.month == month)
    matches = df.index[mask]
    if len(matches) == 0:
        return None
    return matches[0]


def get_future_price(df: pd.DataFrame, cutoff: pd.Timestamp, days: int) -> Optional[float]:
    """Get the close price ~days trading days after cutoff."""
    future = df[df.index > cutoff]
    if len(future) == 0:
        return None
    if len(future) <= days:
        return future.iloc[-1]["Close"]
    return future.iloc[days - 1]["Close"]


def get_future_high_low(df: pd.DataFrame, cutoff: pd.Timestamp, days: int) -> Tuple[Optional[float], Optional[float]]:
    """Get max high and min low in the next ~days trading days."""
    future = df[df.index > cutoff].head(days)
    if len(future) == 0:
        return None, None
    return future["High"].max(), future["Low"].min()


# ── Signal Evaluation ──────────────────────────────────────────

def evaluate_signal(df_full: pd.DataFrame, signal, cutoff: pd.Timestamp) -> dict:
    """
    Evaluate a single signal's outcome over the next VERIFY_DAYS.
    Returns dict with evaluation results.
    """
    entry = signal.entry_price
    stop = signal.stop_loss
    target1 = signal.target_price
    target2 = signal.target_price_2

    bullish = is_bullish(signal.pattern_type)
    bearish = is_bearish(signal.pattern_type)

    future = df_full[df_full.index > cutoff].head(VERIFY_DAYS)
    if len(future) == 0:
        return {
            "outcome": "no_data",
            "return_pct": 0.0,
            "target_hit": None,
            "days_to_hit": None,
        }

    outcome = "expired"
    hit_date = None
    target_hit = None

    for date, row in future.iterrows():
        high, low = row["High"], row["Low"]

        if bullish:
            if stop and low <= stop:
                outcome = "stop_loss"
                hit_date = date
                break
            if target2 and high >= target2:
                outcome = "target2_hit"
                hit_date = date
                target_hit = "target2"
                break
            if target1 and high >= target1:
                outcome = "target1_hit"
                hit_date = date
                target_hit = "target1"
                break
        elif bearish:
            if stop and high >= stop:
                outcome = "stop_loss"
                hit_date = date
                break
            if target2 and low <= target2:
                outcome = "target2_hit"
                hit_date = date
                target_hit = "target2"
                break
            if target1 and low <= target1:
                outcome = "target1_hit"
                hit_date = date
                target_hit = "target1"
                break

    # Final price for return calculation
    if hit_date is not None:
        end_price = future.loc[hit_date, "Close"]
    else:
        end_price = future.iloc[-1]["Close"]
        hit_date = future.index[-1]

    # Return calculation
    if entry and entry > 0:
        if bullish:
            return_pct = (end_price - entry) / entry * 100
        elif bearish:
            return_pct = (entry - end_price) / entry * 100
        else:
            return_pct = (end_price - entry) / entry * 100
    else:
        return_pct = 0.0

    days_to_hit = None
    if hit_date:
        days_to_hit = (hit_date - cutoff).days

    return {
        "outcome": outcome,
        "return_pct": round(return_pct, 2),
        "target_hit": target_hit,
        "days_to_hit": days_to_hit,
        "end_price": round(end_price, 4) if end_price else None,
    }


def get_recommendation(daily_trend: str, weekly_trend: str, signals: list) -> str:
    """
    Determine BUY / SELL / HOLD recommendation.
    BUY: bullish trend + bullish signal
    SELL: bearish trend + bearish signal
    HOLD: otherwise
    """
    has_bullish = any(is_bullish(s.pattern_type) for s in signals)
    has_bearish = any(is_bearish(s.pattern_type) for s in signals)

    trend_bullish = daily_trend in ("多头", "偏多")
    trend_bearish = daily_trend in ("空头", "偏空")

    if trend_bullish and has_bullish:
        return "BUY"
    elif trend_bearish and has_bearish:
        return "SELL"
    elif has_bullish and not has_bearish:
        return "BUY"  # Signal-only bullish
    elif has_bearish and not has_bullish:
        return "SELL"  # Signal-only bearish
    else:
        return "HOLD"


# ── Main Backtest ──────────────────────────────────────────────

def run_backtest():
    print("=" * 80)
    print("🔬 蔡森技术分析 - 12个月滚动回测 (Cai Sen 12-Month Rolling Backtest)")
    print("=" * 80)
    print(f"\n📅 检查点: 2025年5月 → 2026年4月 (共12个月)")
    print(f"📊 标的: {len(INSTRUMENTS)}个 ({', '.join(INSTRUMENTS.keys())})")
    print(f"⏱️ 信号验证窗口: {VERIFY_DAYS}个交易日 (~1个月)")
    print(f"{'=' * 80}\n")

    # Step 1: Download data
    print("📥 下载数据中...")
    all_data = download_all_data()
    print(f"\n✅ 成功下载 {len(all_data)}/{len(INSTRUMENTS)} 个标的\n")

    if not all_data:
        print("❌ 没有数据，退出")
        return

    # Storage
    all_signal_records = []       # Every signal from every checkpoint
    instrument_summaries = {}     # Per-instrument stats
    monthly_summaries = {}        # Per-month stats
    recommendation_records = []   # BUY/SELL/HOLD recommendations

    # Step 2: Run backtest for each instrument at each checkpoint
    for ticker, name in INSTRUMENTS.items():
        if ticker not in all_data:
            continue

        df = all_data[ticker]
        ticker_signals = []
        ticker_recs = []

        print(f"\n{'─' * 80}")
        print(f"📊 {ticker} ({name}) — {len(df)} rows ({df.index[0].date()} → {df.index[-1].date()})")
        print(f"{'─' * 80}")

        for month_code, month_label in CHECKPOINT_MONTHS:
            checkpoint = get_checkpoint_date(df, month_code)
            if checkpoint is None:
                print(f"  {month_label}: ⚠️ 无数据")
                continue

            # Truncate data to checkpoint
            df_trunc = df[df.index <= checkpoint].copy()
            if len(df_trunc) < 60:
                print(f"  {month_label}: ⚠️ 数据不足 ({len(df_trunc)} rows)")
                continue

            # Buy-and-hold benchmark
            bnh_entry = df_trunc.iloc[-1]["Close"]
            bnh_exit = get_future_price(df, checkpoint, VERIFY_DAYS)
            bnh_return = ((bnh_exit - bnh_entry) / bnh_entry * 100) if bnh_exit and bnh_entry else 0.0

            # Run analyzer
            try:
                analyzer = CaiSenAnalyzer()
                analyzer.load_data(ticker, df_trunc)
                result = analyzer.analyze()
            except Exception as e:
                print(f"  {month_label}: ❌ 分析器错误: {e}")
                all_signal_records.append({
                    "ticker": ticker,
                    "name": name,
                    "checkpoint": month_code,
                    "checkpoint_label": month_label,
                    "error": str(e),
                    "signals": [],
                    "recommendation": "ERROR",
                    "recommendation_return": 0.0,
                    "bnh_return": round(bnh_return, 2),
                    "daily_trend": "N/A",
                    "weekly_trend": "N/A",
                })
                continue

            daily_trend = result.daily_trend
            weekly_trend = result.weekly_trend
            signals = result.patterns

            # Evaluate each signal
            signal_results = []
            for sig in signals:
                ev = evaluate_signal(df, sig, checkpoint)
                sig_dict = {
                    "signal_type": sig.pattern_type.value,
                    "timeframe": sig.timeframe,
                    "confidence": sig.confidence,
                    "entry_price": sig.entry_price,
                    "stop_loss": sig.stop_loss,
                    "target_price": sig.target_price,
                    "target_price_2": sig.target_price_2,
                    "risk_reward_ratio": sig.risk_reward_ratio,
                    "direction": "BULLISH" if is_bullish(sig.pattern_type) else ("BEARISH" if is_bearish(sig.pattern_type) else "NEUTRAL"),
                    **ev,
                }
                signal_results.append(sig_dict)
                ticker_signals.append({
                    "ticker": ticker,
                    "checkpoint": month_code,
                    **sig_dict,
                })

            # Recommendation
            rec = get_recommendation(daily_trend, weekly_trend, signals)
            if rec == "BUY" and bnh_entry and bnh_exit:
                rec_return = (bnh_exit - bnh_entry) / bnh_entry * 100
            elif rec == "SELL" and bnh_entry and bnh_exit:
                rec_return = (bnh_entry - bnh_exit) / bnh_entry * 100
            else:
                rec_return = 0.0

            rec_dict = {
                "ticker": ticker,
                "name": name,
                "checkpoint": month_code,
                "daily_trend": daily_trend,
                "weekly_trend": weekly_trend,
                "recommendation": rec,
                "rec_return_pct": round(rec_return, 2),
                "bnh_return_pct": round(bnh_return, 2),
                "num_signals": len(signals),
                "num_bullish": sum(1 for s in signals if is_bullish(s.pattern_type)),
                "num_bearish": sum(1 for s in signals if is_bearish(s.pattern_type)),
            }
            ticker_recs.append(rec_dict)
            recommendation_records.append(rec_dict)

            # Store checkpoint record
            cp_record = {
                "ticker": ticker,
                "name": name,
                "checkpoint": month_code,
                "checkpoint_label": month_label,
                "checkpoint_date": str(checkpoint.date()),
                "daily_trend": daily_trend,
                "weekly_trend": weekly_trend,
                "current_price": round(result.current_price, 4),
                "signals": signal_results,
                "recommendation": rec,
                "recommendation_return": round(rec_return, 2),
                "bnh_return": round(bnh_return, 2),
                "num_signals": len(signals),
            }
            all_signal_records.append(cp_record)

            # Print summary for this checkpoint
            sig_count = len(signals)
            if sig_count > 0:
                bullish_n = sum(1 for s in signals if is_bullish(s.pattern_type))
                bearish_n = sum(1 for s in signals if is_bearish(s.pattern_type))
                types_str = ", ".join(s.pattern_type.value for s in signals)
                print(f"  {month_label}: 趋势({daily_trend}/{weekly_trend}) | "
                      f"信号×{sig_count} 🟢{bullish_n} 🔴{bearish_n} | "
                      f"建议:{rec}({rec_return:+.1f}%) | "
                      f"买持:{bnh_return:+.1f}% | "
                      f"{types_str}")
            else:
                print(f"  {month_label}: 趋势({daily_trend}/{weekly_trend}) | "
                      f"无信号 | 建议:{rec}({rec_return:+.1f}%) | "
                      f"买持:{bnh_return:+.1f}%")

        # Per-instrument summary
        instrument_summaries[ticker] = {
            "name": name,
            "total_signals": len(ticker_signals),
            "bullish_signals": sum(1 for s in ticker_signals if s.get("direction") == "BULLISH"),
            "bearish_signals": sum(1 for s in ticker_signals if s.get("direction") == "BEARISH"),
            "hit_rate": 0.0,
            "avg_return": 0.0,
            "rec_buy_count": sum(1 for r in ticker_recs if r["recommendation"] == "BUY"),
            "rec_sell_count": sum(1 for r in ticker_recs if r["recommendation"] == "SELL"),
            "rec_hold_count": sum(1 for r in ticker_recs if r["recommendation"] == "HOLD"),
            "avg_rec_return": 0.0,
            "avg_bnh_return": round(np.mean([r["bnh_return_pct"] for r in ticker_recs]) if ticker_recs else 0.0, 2),
        }

        hits = sum(1 for s in ticker_signals if s.get("outcome") in ("target1_hit", "target2_hit"))
        returns = [s["return_pct"] for s in ticker_signals if "return_pct" in s]
        if ticker_signals:
            instrument_summaries[ticker]["hit_rate"] = round(hits / len(ticker_signals) * 100, 1)
        if returns:
            instrument_summaries[ticker]["avg_return"] = round(np.mean(returns), 2)
        rec_returns = [r["rec_return_pct"] for r in ticker_recs]
        if rec_returns:
            instrument_summaries[ticker]["avg_rec_return"] = round(np.mean(rec_returns), 2)

    # Per-month summary
    for month_code, month_label in CHECKPOINT_MONTHS:
        month_records = [r for r in all_signal_records if r.get("checkpoint") == month_code]
        month_recs = [r for r in recommendation_records if r["checkpoint"] == month_code]
        total_signals = sum(r.get("num_signals", 0) for r in month_records)
        monthly_summaries[month_code] = {
            "label": month_label,
            "instruments_tested": len(month_records),
            "total_signals": total_signals,
            "buy_count": sum(1 for r in month_recs if r["recommendation"] == "BUY"),
            "sell_count": sum(1 for r in month_recs if r["recommendation"] == "SELL"),
            "hold_count": sum(1 for r in month_recs if r["recommendation"] == "HOLD"),
            "avg_rec_return": round(np.mean([r["rec_return_pct"] for r in month_recs]) if month_recs else 0.0, 2),
            "avg_bnh_return": round(np.mean([r["bnh_return_pct"] for r in month_recs]) if month_recs else 0.0, 2),
        }

    # ── Generate Report ──────────────────────────────────────────

    report_lines = []
    def p(line=""):
        report_lines.append(line)
        print(line)

    p("\n" + "=" * 80)
    p("📋 回测报告 — 蔡森技术分析 12个月滚动回测")
    p("=" * 80)
    p(f"回测期间: 2025年5月 → 2026年4月 (12个月)")
    p(f"标的数量: {len(INSTRUMENTS)}")
    p(f"验证窗口: {VERIFY_DAYS} 个交易日")

    # ── Section 1: Per-Instrument Summary ──
    p(f"\n{'━' * 80}")
    p("📊 1. 各标的汇总")
    p(f"{'━' * 80}")
    p(f"{'标的':<12} {'名称':<22} {'信号数':>6} {'🟢多':>4} {'🔴空':>4} {'命中率':>6} {'平均回报':>8} {'建议回报':>8} {'买持回报':>8}")
    p("─" * 80)

    total_all_signals = 0
    total_hits = 0
    total_returns = []
    total_rec_returns = []
    total_bnh_returns = []

    for ticker, name in INSTRUMENTS.items():
        if ticker not in instrument_summaries:
            continue
        s = instrument_summaries[ticker]
        total_all_signals += s["total_signals"]
        total_bnh_returns.append(s["avg_bnh_return"])
        p(f"{ticker:<12} {name:<22} {s['total_signals']:>6} {s['bullish_signals']:>4} {s['bearish_signals']:>4} "
          f"{s['hit_rate']:>5.1f}% {s['avg_return']:>+7.2f}% {s['avg_rec_return']:>+7.2f}% {s['avg_bnh_return']:>+7.2f}%")

    # ── Section 2: Per-Month Summary ──
    p(f"\n{'━' * 80}")
    p("📅 2. 月度汇总")
    p(f"{'━' * 80}")
    p(f"{'月份':<12} {'标的数':>6} {'信号数':>6} {'BUY':>5} {'SELL':>5} {'HOLD':>5} {'建议回报':>8} {'买持回报':>8}")
    p("─" * 80)

    for month_code, month_label in CHECKPOINT_MONTHS:
        ms = monthly_summaries.get(month_code, {})
        p(f"{month_label:<12} {ms.get('instruments_tested', 0):>6} {ms.get('total_signals', 0):>6} "
          f"{ms.get('buy_count', 0):>5} {ms.get('sell_count', 0):>5} {ms.get('hold_count', 0):>5} "
          f"{ms.get('avg_rec_return', 0):>+7.2f}% {ms.get('avg_bnh_return', 0):>+7.2f}%")

    # ── Section 3: Overall Accuracy ──
    p(f"\n{'━' * 80}")
    p("🎯 3. 总体准确率")
    p(f"{'━' * 80}")

    all_signals_flat = []
    for rec in all_signal_records:
        for sig in rec.get("signals", []):
            all_signals_flat.append(sig)

    if all_signals_flat:
        total = len(all_signals_flat)
        hits = sum(1 for s in all_signals_flat if s.get("outcome") in ("target1_hit", "target2_hit"))
        stops = sum(1 for s in all_signals_flat if s.get("outcome") == "stop_loss")
        expired = sum(1 for s in all_signals_flat if s.get("outcome") == "expired")

        bullish_sigs = [s for s in all_signals_flat if s.get("direction") == "BULLISH"]
        bearish_sigs = [s for s in all_signals_flat if s.get("direction") == "BEARISH"]

        bullish_hits = sum(1 for s in bullish_sigs if s.get("outcome") in ("target1_hit", "target2_hit"))
        bearish_hits = sum(1 for s in bearish_sigs if s.get("outcome") in ("target1_hit", "target2_hit"))

        all_returns = [s["return_pct"] for s in all_signals_flat if "return_pct" in s]
        winning = [r for r in all_returns if r > 0]
        losing = [r for r in all_returns if r <= 0]

        p(f"  总信号数: {total}")
        p(f"  ✅ 目标达成(任意): {hits}/{total} = {hits/total*100:.1f}%")
        p(f"  ❌ 止损触发: {stops}/{total} = {stops/total*100:.1f}%")
        p(f"  ⏰ 到期未触发: {expired}/{total} = {expired/total*100:.1f}%")
        p()
        p(f"  🟢 BUY信号: {len(bullish_sigs)} 个, 命中: {bullish_hits}/{len(bullish_sigs)} = {bullish_hits/len(bullish_sigs)*100:.1f}%" if bullish_sigs else "  🟢 BUY信号: 0")
        p(f"  🔴 SELL信号: {len(bearish_sigs)} 个, 命中: {bearish_hits}/{len(bearish_sigs)} = {bearish_hits/len(bearish_sigs)*100:.1f}%" if bearish_sigs else "  🔴 SELL信号: 0")
        p()
        p(f"  📊 平均回报: {np.mean(all_returns):+.2f}%")
        if winning:
            p(f"  📊 盈利平均: +{np.mean(winning):.2f}% ({len(winning)}笔)")
        if losing:
            p(f"  📊 亏损平均: {np.mean(losing):.2f}% ({len(losing)}笔)")
    else:
        p("  无信号记录")

    # ── Section 4: Portfolio Simulation ──
    p(f"\n{'━' * 80}")
    p("💰 4. 组合收益模拟 (跟随所有建议)")
    p(f"{'━' * 80}")

    # For each month, if rec=BUY, gain = bnh_return; if SELL, gain = -bnh_return; if HOLD, 0
    monthly_portfolio_returns = {}
    for month_code, month_label in CHECKPOINT_MONTHS:
        month_recs = [r for r in recommendation_records if r["checkpoint"] == month_code]
        if not month_recs:
            continue
        # Equal-weight: each instrument's recommendation return
        rec_returns = [r["rec_return_pct"] for r in month_recs]
        bnh_returns = [r["bnh_return_pct"] for r in month_recs]
        avg_rec = np.mean(rec_returns) if rec_returns else 0
        avg_bnh = np.mean(bnh_returns) if bnh_returns else 0
        monthly_portfolio_returns[month_code] = {
            "label": month_label,
            "strategy_return": round(avg_rec, 2),
            "benchmark_return": round(avg_bnh, 2),
            "num_positions": len(month_recs),
        }

    p(f"  {'月份':<12} {'策略收益':>10} {'买持收益':>10} {'超额收益':>10}")
    p("  " + "─" * 50)

    cumulative_strategy = 1.0
    cumulative_bnh = 1.0
    for month_code, month_label in CHECKPOINT_MONTHS:
        if month_code not in monthly_portfolio_returns:
            continue
        pr = monthly_portfolio_returns[month_code]
        s_ret = pr["strategy_return"]
        b_ret = pr["benchmark_return"]
        excess = s_ret - b_ret

        cumulative_strategy *= (1 + s_ret / 100)
        cumulative_bnh *= (1 + b_ret / 100)

        p(f"  {pr['label']:<12} {s_ret:>+9.2f}% {b_ret:>+9.2f}% {excess:>+9.2f}%")

    total_strat = (cumulative_strategy - 1) * 100
    total_bnh = (cumulative_bnh - 1) * 100
    p(f"  {'─' * 50}")
    p(f"  {'累计':<12} {total_strat:>+9.2f}% {total_bnh:>+9.2f}% {total_strat - total_bnh:>+9.2f}%")

    # ── Section 5: Signal Type Breakdown ──
    p(f"\n{'━' * 80}")
    p("📈 5. 信号类型分析")
    p(f"{'━' * 80}")

    if all_signals_flat:
        type_stats = {}
        for s in all_signals_flat:
            st = s.get("signal_type", "unknown")
            if st not in type_stats:
                type_stats[st] = {"total": 0, "hits": 0, "stops": 0, "returns": [], "direction": s.get("direction", "?")}
            type_stats[st]["total"] += 1
            if s.get("outcome") in ("target1_hit", "target2_hit"):
                type_stats[st]["hits"] += 1
            if s.get("outcome") == "stop_loss":
                type_stats[st]["stops"] += 1
            if "return_pct" in s:
                type_stats[st]["returns"].append(s["return_pct"])

        p(f"  {'信号类型':<20} {'方向':<8} {'次数':>4} {'命中':>4} {'止损':>4} {'命中率':>6} {'平均回报':>8}")
        p("  " + "─" * 65)
        for st, stats in sorted(type_stats.items(), key=lambda x: -x[1]["total"]):
            hit_rate = stats["hits"] / stats["total"] * 100 if stats["total"] else 0
            avg_ret = np.mean(stats["returns"]) if stats["returns"] else 0
            p(f"  {st:<20} {stats['direction']:<8} {stats['total']:>4} {stats['hits']:>4} {stats['stops']:>4} {hit_rate:>5.1f}% {avg_ret:>+7.2f}%")

    # ── Section 6: Detailed Signal Table ──
    p(f"\n{'━' * 80}")
    p("📋 6. 详细信号记录")
    p(f"{'━' * 80}")
    p(f"  {'标的':<10} {'月份':<8} {'信号类型':<16} {'方向':<6} {'入场':>8} {'止损':>8} {'目标1':>8} {'结果':<10} {'回报%':>7} {'天数':>4}")
    p("  " + "─" * 90)

    for rec in all_signal_records:
        for sig in rec.get("signals", []):
            outcome_emoji = {
                "target1_hit": "✅T1",
                "target2_hit": "🎯T2",
                "stop_loss": "❌SL",
                "expired": "⏰EXP",
                "no_data": "⚠️N/A",
            }.get(sig.get("outcome", ""), sig.get("outcome", "?"))

            p(f"  {rec['ticker']:<10} {rec['checkpoint']:<8} {sig.get('signal_type','?'):<16} "
              f"{sig.get('direction','?'):<6} {sig.get('entry_price',0):>8.2f} "
              f"{sig.get('stop_loss',0):>8.2f} {sig.get('target_price',0):>8.2f} "
              f"{outcome_emoji:<10} {sig.get('return_pct',0):>+6.2f}% "
              f"{sig.get('days_to_hit',''):>4}")

    # ── Save results ──
    output = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "checkpoint_months": [m[0] for m in CHECKPOINT_MONTHS],
            "instruments": INSTRUMENTS,
            "verify_days": VERIFY_DAYS,
        },
        "instrument_summaries": instrument_summaries,
        "monthly_summaries": monthly_summaries,
        "portfolio_simulation": {
            "monthly": monthly_portfolio_returns,
            "cumulative_strategy_return": round(total_strat, 2),
            "cumulative_benchmark_return": round(total_bnh, 2),
            "excess_return": round(total_strat - total_bnh, 2),
        },
        "overall_accuracy": {
            "total_signals": len(all_signals_flat),
            "hit_rate": round(hits / total * 100, 1) if all_signals_flat else 0,
            "stop_rate": round(stops / total * 100, 1) if all_signals_flat else 0,
            "avg_return": round(np.mean(all_returns), 2) if all_returns else 0,
            "win_rate": round(len(winning) / len(all_returns) * 100, 1) if all_returns else 0,
        },
        "all_signal_records": all_signal_records,
        "recommendation_records": recommendation_records,
    }

    with open("/root/.openclaw/workspace/Caisen-analyzer/backtest_12m_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n💾 结果已保存到 backtest_12m_results.json")

    # Save text report
    with open("/root/.openclaw/workspace/Caisen-analyzer/backtest_12m_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"💾 文字报告已保存到 backtest_12m_report.txt")

    p(f"\n{'=' * 80}")
    p("✅ 回测完成!")
    p(f"{'=' * 80}")


if __name__ == "__main__":
    run_backtest()
