#!/usr/bin/env python3
"""
蔡森技术分析 - 03690.HK 回测
假设当前日期: 2026-01-29
回测目标: 验证历史信号的准确率
"""

import sys
import json
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, '/root/.openclaw/workspace/Caisen-analyzer')
from cai_sen_analyzer import CaiSenAnalyzer, SignalType

SYMBOL = "3690.HK"
CUTOFF_DATE = "2026-01-29"
VERIFY_DAYS = 45  # Check 45 trading days after signal for outcome


def download_data():
    """Download enough data: 2y before cutoff + 3 months after for verification"""
    print(f"📥 Downloading {SYMBOL} data (2024-01 to 2026-04)...")
    ticker = yf.Ticker(SYMBOL)
    df = ticker.history(period="2y", auto_adjust=False)
    if df.empty:
        raise ValueError(f"Cannot fetch {SYMBOL}")
    print(f"   Got {len(df)} rows: {df.index[0].date()} → {df.index[-1].date()}")
    return df


def run_signals_at_cutoff(df, cutoff_str):
    """Run analyzer on data truncated to cutoff date"""
    cutoff = pd.Timestamp(cutoff_str).tz_localize(df.index.tz)
    df_truncated = df[df.index <= cutoff].copy()

    print(f"\n🔍 Running analysis on data up to {cutoff_str} ({len(df_truncated)} rows)...")

    analyzer = CaiSenAnalyzer()
    analyzer.load_data(SYMBOL, df_truncated)
    result = analyzer.analyze()

    return result, df_truncated


def verify_signal_outcome(df_full, signal, cutoff_str, verify_days=VERIFY_DAYS):
    """
    Check what happened after a signal was generated.
    Returns: 'target_hit', 'target2_hit', 'stop_loss_hit', 'expired'
    """
    cutoff = pd.Timestamp(cutoff_str).tz_localize(df_full.index.tz)
    future = df_full[df_full.index > cutoff].head(verify_days)

    if len(future) == 0:
        return "no_data", None, None

    entry = signal.entry_price
    stop = signal.stop_loss
    target1 = signal.target_price
    target2 = signal.target_price_2

    is_long = signal.pattern_type in {
        SignalType.PO_DI_FAN, SignalType.ZHEN_XIAN_TU_PO,
        SignalType.HEAD_SHOULDER_BOTTOM, SignalType.W_BOTTOM,
        SignalType.ISLAND_REVERSAL_BOTTOM, SignalType.VOLUME_LEADS_PRICE
    }

    hit_date = None
    outcome = "expired"

    for date, row in future.iterrows():
        high = row['High']
        low = row['Low']

        if is_long:
            # Check stop loss first (worst case)
            if low <= stop:
                outcome = "stop_loss_hit"
                hit_date = date
                break
            # Check target 2
            if high >= target2:
                outcome = "target2_hit"
                hit_date = date
                break
            # Check target 1
            if high >= target1:
                outcome = "target1_hit"
                hit_date = date
                break
        else:
            # Short signal
            if high >= stop:
                outcome = "stop_loss_hit"
                hit_date = date
                break
            if low <= target2:
                outcome = "target2_hit"
                hit_date = date
                break
            if low <= target1:
                outcome = "target1_hit"
                hit_date = date
                break

    # Calculate actual return
    if hit_date is not None:
        end_price = future.loc[hit_date, 'Close']
    elif len(future) > 0:
        end_price = future.iloc[-1]['Close']
        hit_date = future.index[-1]
    else:
        end_price = entry

    if is_long:
        actual_return = (end_price - entry) / entry * 100
    else:
        actual_return = (entry - end_price) / entry * 100

    return outcome, hit_date, actual_return


def backtest_historical_signals(df_full, num_checks=8):
    """
    Backtest by running signals at multiple historical cutoff dates
    and checking outcomes
    """
    cutoff = pd.Timestamp(CUTOFF_DATE).tz_localize(df_full.index.tz)
    # Go back ~6 months, check every 3 weeks
    start_date = cutoff - timedelta(days=180)
    check_dates = pd.date_range(start=start_date, end=cutoff, periods=num_checks)
    # Make them business-day aligned
    check_dates = [df_full.index[df_full.index.searchsorted(d)] for d in check_dates]

    all_results = []

    for check_date in check_dates:
        check_str = str(check_date.date())
        df_trunc = df_full[df_full.index <= check_date].copy()

        if len(df_trunc) < 90:
            continue

        analyzer = CaiSenAnalyzer()
        analyzer.load_data(SYMBOL, df_trunc)
        result = analyzer.analyze()

        for signal in result.patterns:
            outcome, hit_date, actual_return = verify_signal_outcome(
                df_full, signal, check_str
            )
            all_results.append({
                'check_date': check_str,
                'signal_type': signal.pattern_type.value,
                'timeframe': signal.timeframe,
                'confidence': signal.confidence,
                'entry': signal.entry_price,
                'stop_loss': signal.stop_loss,
                'target1': signal.target_price,
                'target2': signal.target_price_2,
                'risk_reward': signal.risk_reward_ratio,
                'outcome': outcome,
                'hit_date': str(hit_date.date()) if hit_date else None,
                'actual_return_pct': round(actual_return, 2),
            })

    return all_results


def print_current_advice(result):
    """Print current analysis as of Jan 29, 2026"""
    print("\n" + "=" * 70)
    print(f"📊 03690.HK (美团) 蔡森技术分析 — 假设今天是 2026-01-29")
    print("=" * 70)

    current = result.current_price
    print(f"\n💰 当前价格: {current:.2f}")
    print(f"📈 日线趋势: {result.daily_trend}")
    print(f"📈 周线趋势: {result.weekly_trend}")

    if result.key_support:
        print(f"🟢 短期支撑: {result.key_support:.2f}")
    if result.key_resistance:
        print(f"🔴 近期压力: {result.key_resistance:.2f}")
    if result.long_term_support:
        print(f"🟢 长线大支撑: {result.long_term_support:.2f}")

    if result.patterns:
        print(f"\n🔍 发现 {len(result.patterns)} 个交易信号:")
        for p in result.patterns:
            BULLISH_SIGNALS = {"破底翻", "W底", "头肩底", "岛型反转(底)", "量先价行", "颈线突破"}
            is_bullish = p.pattern_type.value in BULLISH_SIGNALS
            emoji = "🟢" if is_bullish else "🔴"
            tf_tag = "【周线】" if p.timeframe == "weekly" else ""

            print(f"\n  {emoji} {tf_tag}{p.pattern_type.value}")
            print(f"     置信度: {p.confidence:.0%}")
            print(f"     颈线: {p.neckline:.2f}")
            print(f"     入场价: {p.entry_price:.2f}")
            print(f"     止损: {p.stop_loss:.2f} ({abs(p.stop_loss - p.entry_price)/p.entry_price*100:.1f}%)")
            print(f"     目标1: {p.target_price:.2f} ({abs(p.target_price - p.entry_price)/p.entry_price*100:.1f}%)")
            print(f"     目标2: {p.target_price_2:.2f} (黄金比例)")
            print(f"     风险回报比: 1:{p.risk_reward_ratio:.1f}")
            print(f"     {p.description}")
    else:
        print("\n🔍 当前无明确型态信号，建议观望等待")


def print_backtest_results(results):
    """Print backtest accuracy report"""
    print("\n" + "=" * 70)
    print("📋 历史信号回测报告")
    print("=" * 70)

    if not results:
        print("  无历史信号可回测")
        return

    total = len(results)
    target1_hits = sum(1 for r in results if r['outcome'] == 'target1_hit')
    target2_hits = sum(1 for r in results if r['outcome'] == 'target2_hit')
    stop_hits = sum(1 for r in results if r['outcome'] == 'stop_loss_hit')
    expired = sum(1 for r in results if r['outcome'] == 'expired')

    print(f"\n  总信号数: {total}")
    print(f"  ✅ 目标1达成: {target1_hits} ({target1_hits/total*100:.0f}%)")
    print(f"  🎯 目标2达成(黄金比例): {target2_hits} ({target2_hits/total*100:.0f}%)")
    print(f"  ❌ 止损触发: {stop_hits} ({stop_hits/total*100:.0f}%)")
    print(f"  ⏰ 到期未触发: {expired} ({expired/total*100:.0f}%)")

    any_target = target1_hits + target2_hits
    print(f"\n  📊 总命中率(任意目标): {any_target}/{total} = {any_target/total*100:.0f}%")
    print(f"  📊 止损率: {stop_hits}/{total} = {stop_hits/total*100:.0f}%")

    # Average returns
    returns = [r['actual_return_pct'] for r in results if r['actual_return_pct'] is not None]
    if returns:
        avg_return = np.mean(returns)
        print(f"  📊 平均实际回报: {avg_return:+.2f}%")
        winning = [r for r in returns if r > 0]
        losing = [r for r in returns if r <= 0]
        if winning:
            print(f"  📊 盈利平均: +{np.mean(winning):.2f}% ({len(winning)}笔)")
        if losing:
            print(f"  📊 亏损平均: {np.mean(losing):.2f}% ({len(losing)}笔)")

    # Breakdown by signal type
    print("\n  按信号类型:")
    types = set(r['signal_type'] for r in results)
    for st in sorted(types):
        subset = [r for r in results if r['signal_type'] == st]
        hits = sum(1 for r in subset if r['outcome'] in ['target1_hit', 'target2_hit'])
        print(f"    {st}: {hits}/{len(subset)} 命中 ({hits/len(subset)*100:.0f}%)")

    # Detail table
    print("\n  详细信号记录:")
    print(f"  {'检查日期':<12} {'信号类型':<12} {'时间框':<6} {'入场':>8} {'止损':>8} {'目标1':>8} {'实际结果':<14} {'回报%':>8}")
    print("  " + "-" * 90)
    for r in results:
        outcome_map = {
            'target1_hit': '✅目标1',
            'target2_hit': '🎯目标2',
            'stop_loss_hit': '❌止损',
            'expired': '⏰到期',
        }
        print(f"  {r['check_date']:<12} {r['signal_type']:<12} {r['timeframe']:<6} "
              f"{r['entry']:>8.2f} {r['stop_loss']:>8.2f} {r['target1']:>8.2f} "
              f"{outcome_map.get(r['outcome'], r['outcome']):<14} {r['actual_return_pct']:>+7.2f}%")


def main():
    df_full = download_data()

    # 1. Current analysis as of Jan 29, 2026
    result, df_truncated = run_signals_at_cutoff(df_full, CUTOFF_DATE)
    print_current_advice(result)

    # 2. Historical backtest
    print("\n⏳ Running historical backtest (checking signals at multiple dates)...")
    backtest_results = backtest_historical_signals(df_full, num_checks=10)
    print_backtest_results(backtest_results)

    # 3. Show what actually happened after Jan 29
    cutoff = pd.Timestamp(CUTOFF_DATE).tz_localize(df_full.index.tz)
    after = df_full[df_full.index > cutoff]
    if len(after) > 0:
        print(f"\n" + "=" * 70)
        print(f"📈 01/29 之后实际走势 (截至 {after.index[-1].date()})")
        print("=" * 70)
        last_close = df_truncated.iloc[-1]['Close']
        actual_close = after.iloc[-1]['Close']
        actual_change = (actual_close - last_close) / last_close * 100
        actual_high = after['High'].max()
        actual_low = after['Low'].min()
        print(f"  01/29 收盘: {last_close:.2f}")
        print(f"  最新收盘: {actual_close:.2f}")
        print(f"  实际涨跌: {actual_change:+.2f}%")
        print(f"  期间最高: {actual_high:.2f}")
        print(f"  期间最低: {actual_low:.2f}")

        # Check if current signals' targets/stops would have been hit
        if result.patterns:
            print(f"\n  信号验证 (Jan 29 → {after.index[-1].date()}):")
            BULLISH_SIGNALS = {"破底翻", "W底", "头肩底", "岛型反转(底)", "量先价行", "颈线突破"}
            for p in result.patterns:
                is_long = p.pattern_type.value in BULLISH_SIGNALS
                if is_long:
                    if actual_high >= p.target_price_2:
                        verdict = "🎯 目标2已达成!"
                    elif actual_high >= p.target_price:
                        verdict = "✅ 目标1已达成!"
                    elif actual_low <= p.stop_loss:
                        verdict = "❌ 已触发止损"
                    else:
                        verdict = "⏳ 仍在运行中"
                else:
                    if actual_low <= p.target_price_2:
                        verdict = "🎯 目标2已达成!"
                    elif actual_low <= p.target_price:
                        verdict = "✅ 目标1已达成!"
                    elif actual_high >= p.stop_loss:
                        verdict = "❌ 已触发止损"
                    else:
                        verdict = "⏳ 仍在运行中"
                print(f"    {p.pattern_type.value}: {verdict}")


if __name__ == "__main__":
    main()
