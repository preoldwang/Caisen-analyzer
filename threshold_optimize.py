#!/usr/bin/env python3
"""
蔡森技术分析 — 破底翻 & 月线缩量见底 阈值优化回测
=================================================
策略: 用原始检测器找信号，然后用不同置信度阈值筛选，找到最佳平衡点
"""

import sys, json, warnings
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime

sys.path.insert(0, '/root/.openclaw/workspace/Caisen-analyzer')
from cai_sen_analyzer import CaiSenAnalyzer, SignalType

warnings.filterwarnings('ignore')

# Signals we care about
TARGET_SIGNALS = {"破底翻", "月线缩量见底"}
BULLISH_SIGNALS = {"破底翻", "月线缩量见底"}

INSTRUMENTS = {
    '0916.HK': 'China Longyuan Power',
    '1880.HK': 'LVMH/Luxury',
    '0728.HK': 'China Telecom',
    '0788.HK': 'China Tower',
    '2318.HK': 'Ping An Insurance',
    '0836.HK': 'China Resources Power',
    '9961.HK': 'Trip.com',
    '2050.HK': '361 Degrees',
    'GC=F': 'Gold Futures',
}

CUTOFF_DATES = [
    "2025-05-01", "2025-06-01", "2025-07-01", "2025-08-01",
    "2025-09-01", "2025-10-01", "2025-11-01", "2025-12-01",
    "2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01",
]
VERIFY_DAYS = 22


def download_all():
    data = {}
    for symbol in INSTRUMENTS:
        print(f"  📥 {symbol}...", end=" ", flush=True)
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="2y", auto_adjust=False)
            if len(df) > 60:
                data[symbol] = df
                print(f"✅ {len(df)} rows")
            else:
                print(f"⚠️ skip")
        except Exception as e:
            print(f"❌ {e}")
    return data


def collect_all_signals(all_data):
    """
    Run original analyzer at each cutoff, collect 破底翻 + 月线缩量见底 signals.
    Return list of (signal, symbol, cutoff_str, bnh_return).
    Dedup monthly signals globally.
    """
    all_raw = []
    seen_monthly = set()

    for symbol, name in INSTRUMENTS.items():
        if symbol not in all_data:
            continue
        df_full = all_data[symbol]

        for cutoff_str in CUTOFF_DATES:
            cutoff = pd.Timestamp(cutoff_str)
            if df_full.index.tz is not None:
                cutoff = cutoff.tz_localize(df_full.index.tz)

            df_trunc = df_full[df_full.index <= cutoff].copy()
            if len(df_trunc) < 90:
                continue

            try:
                analyzer = CaiSenAnalyzer()
                analyzer.load_data(symbol, df_trunc)
                result = analyzer.analyze()

                # Filter to target signals only
                target = [p for p in result.patterns if p.pattern_type.value in TARGET_SIGNALS]

                # Buy-and-hold return
                future = df_full[df_full.index > cutoff].head(VERIFY_DAYS)
                bnh = 0
                if len(future) > 0:
                    bnh = (future.iloc[-1]['Close'] - df_trunc.iloc[-1]['Close']) / df_trunc.iloc[-1]['Close'] * 100

                for sig in target:
                    # Dedup monthly signals globally
                    if sig.timeframe == "monthly":
                        key = (symbol, sig.signal_date, sig.entry_price)
                        if key in seen_monthly:
                            continue
                        seen_monthly.add(key)
                    else:
                        # Daily signals: only count if signal_date is in cutoff month
                        if sig.signal_date[:7] != cutoff_str[:7]:
                            continue

                    all_raw.append({
                        'signal': sig,
                        'symbol': symbol,
                        'name': name,
                        'cutoff': cutoff_str,
                        'bnh_return': round(bnh, 2),
                    })

            except Exception as e:
                pass

    return all_raw


def verify_outcome(df_full, signal, cutoff_str):
    cutoff = pd.Timestamp(cutoff_str)
    if df_full.index.tz is not None:
        cutoff = cutoff.tz_localize(df_full.index.tz)
    future = df_full[df_full.index > cutoff].head(VERIFY_DAYS)
    if len(future) == 0:
        return "no_data", 0

    entry = signal.entry_price
    stop = signal.stop_loss
    target1 = signal.target_price
    target2 = signal.target_price_2
    is_long = signal.pattern_type.value in BULLISH_SIGNALS

    outcome = "expired"
    for date, row in future.iterrows():
        if is_long:
            if row['Low'] <= stop:
                outcome = "stop_loss_hit"
                break
            if row['High'] >= target2:
                outcome = "target2_hit"
                break
            if row['High'] >= target1:
                outcome = "target1_hit"
                break
        else:
            if row['High'] >= stop:
                outcome = "stop_loss_hit"
                break
            if row['Low'] <= target2:
                outcome = "target2_hit"
                break
            if row['Low'] <= target1:
                outcome = "target1_hit"
                break

    end_price = future.iloc[-1]['Close']
    if is_long:
        ret = (end_price - entry) / entry * 100
    else:
        ret = (entry - end_price) / entry * 100

    return outcome, round(ret, 2)


def threshold_sweep(all_raw, all_data):
    """
    For confidence thresholds from 0.50 to 0.95, calculate hit rate and returns.
    """
    thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]

    print("\n" + "=" * 90)
    print("📊 置信度阈值优化 — 破底翻 & 月线缩量见底")
    print("=" * 90)

    print(f"\n  {'阈值':>6} {'信号数':>6} {'命中':>6} {'命中率':>8} {'止损':>6} {'到期':>6} "
          f"{'平均回报':>10} {'盈利笔':>8} {'胜率':>8} {'vs买持':>10}")
    print("  " + "-" * 85)

    results_by_threshold = {}

    for thresh in thresholds:
        filtered = [r for r in all_raw if r['signal'].confidence >= thresh]

        if not filtered:
            print(f"  {thresh:>6.0%} {'0':>6} {'-':>6} {'N/A':>8} {'-':>6} {'-':>6} "
                  f"{'N/A':>10} {'-':>8} {'N/A':>8} {'N/A':>10}")
            continue

        # Verify each signal
        outcomes = []
        for r in filtered:
            df = all_data[r['symbol']]
            outcome, ret = verify_outcome(df, r['signal'], r['cutoff'])
            outcomes.append({
                **r,
                'outcome': outcome,
                'actual_return': ret,
            })

        total = len(outcomes)
        hits = sum(1 for o in outcomes if o['outcome'] in ('target1_hit', 'target2_hit'))
        sls = sum(1 for o in outcomes if o['outcome'] == 'stop_loss_hit')
        exps = sum(1 for o in outcomes if o['outcome'] == 'expired')
        avg_ret = np.mean([o['actual_return'] for o in outcomes])
        wins = [o for o in outcomes if o['actual_return'] > 0]
        win_rate = len(wins) / total * 100 if total > 0 else 0
        bnh = np.mean([o['bnh_return'] for o in outcomes])
        excess = avg_ret - bnh

        print(f"  {thresh:>6.0%} {total:>6} {hits:>6} {hits/total*100:>7.1f}% {sls:>6} {exps:>6} "
              f"{avg_ret:>+9.2f}% {len(wins):>8} {win_rate:>7.1f}% {excess:>+9.2f}%")

        results_by_threshold[thresh] = outcomes

    return results_by_threshold


def detailed_analysis(results_by_threshold, all_data):
    """Show detailed breakdown at best threshold"""
    # Find best threshold by win rate (minimum 5 signals)
    best_thresh = None
    best_wr = 0
    for thresh, outcomes in results_by_threshold.items():
        if len(outcomes) >= 3:
            wr = sum(1 for o in outcomes if o['actual_return'] > 0) / len(outcomes)
            if wr > best_wr:
                best_wr = wr
                best_thresh = thresh

    if best_thresh is None:
        print("\n⚠️ No threshold produced enough signals for analysis")
        return

    outcomes = results_by_threshold[best_thresh]

    print(f"\n" + "=" * 90)
    print(f"📋 最佳阈值详细分析: {best_thresh:.0%} (胜率 {best_wr:.0%})")
    print("=" * 90)

    # By signal type
    print(f"\n  按信号类型:")
    for stype in ['破底翻', '月线缩量见底']:
        sub = [o for o in outcomes if stype in o['signal'].pattern_type.value]
        if not sub:
            continue
        hits = sum(1 for o in sub if o['outcome'] in ('target1_hit', 'target2_hit'))
        sls = sum(1 for o in sub if o['outcome'] == 'stop_loss_hit')
        avg = np.mean([o['actual_return'] for o in sub])
        print(f"    {stype}: {len(sub)} signals | 命中 {hits} | 止损 {sls} | 回报 {avg:+.2f}%")

    # By instrument
    print(f"\n  按标的:")
    for sym in INSTRUMENTS:
        sub = [o for o in outcomes if o['symbol'] == sym]
        if not sub:
            continue
        hits = sum(1 for o in sub if o['outcome'] in ('target1_hit', 'target2_hit'))
        avg = np.mean([o['actual_return'] for o in sub])
        bnh = np.mean([o['bnh_return'] for o in sub])
        print(f"    {sym}: {len(sub)} signals | 命中 {hits} | 回报 {avg:+.2f}% | 买持 {bnh:+.2f}%")

    # Detail table
    print(f"\n  详细记录:")
    print(f"  {'标的':<10} {'月份':<12} {'信号':<16} {'置信':>5} {'入场':>8} {'止损':>8} "
          f"{'目标1':>8} {'结果':<10} {'回报':>8} {'买持':>8}")
    print("  " + "-" * 100)
    for o in sorted(outcomes, key=lambda x: x['cutoff']):
        om = {
            'target1_hit': '✅T1', 'target2_hit': '🎯T2',
            'stop_loss_hit': '❌SL', 'expired': '⏰EXP', 'no_data': '❓N/A'
        }
        s = o['signal']
        print(f"  {o['symbol']:<10} {o['cutoff']:<12} {s.pattern_type.value:<16} "
              f"{s.confidence:>5.0%} {s.entry_price:>8.2f} {s.stop_loss:>8.2f} "
              f"{s.target_price:>8.2f} {om.get(o['outcome'], '?'):<10} "
              f"{o['actual_return']:>+7.2f}% {o['bnh_return']:>+7.2f}%")

    # Portfolio simulation
    print(f"\n" + "=" * 90)
    print(f"💰 组合模拟 @ {best_thresh:.0%} 阈值 (假设等权分配)")
    print("=" * 90)

    total_ret = sum(o['actual_return'] for o in outcomes)
    total_bnh = sum(o['bnh_return'] for o in outcomes)
    n = len(outcomes)
    print(f"  信号总数: {n}")
    print(f"  策略累计回报: {total_ret:+.2f}% (平均 {total_ret/n:+.2f}% per signal)")
    print(f"  买持累计回报: {total_bnh:+.2f}% (平均 {total_bnh/n:+.2f}%)")
    print(f"  超额回报: {total_ret - total_bnh:+.2f}%")

    # Compound return simulation
    monthly_returns = {}
    for o in outcomes:
        m = o['cutoff']
        if m not in monthly_returns:
            monthly_returns[m] = []
        monthly_returns[m].append(o['actual_return'])

    print(f"\n  月度:")
    cum = 1.0
    cum_bnh = 1.0
    print(f"  {'月份':<14} {'信号':>4} {'月收益':>8} {'累计':>10} {'买持累计':>10}")
    print("  " + "-" * 50)
    for m in CUTOFF_DATES:
        if m in monthly_returns:
            m_ret = np.mean(monthly_returns[m])
            cum *= (1 + m_ret / 100)
            n_sig = len(monthly_returns[m])
        else:
            m_ret = 0
            n_sig = 0
        print(f"  {m:<14} {n_sig:>4} {m_ret:>+7.2f}% {(cum-1)*100:>+9.2f}% {(cum_bnh-1)*100:>+9.2f}%")

    print(f"\n  最终复合回报: {(cum-1)*100:+.2f}%")

    # Improvement recommendations
    print(f"\n" + "=" * 90)
    print(f"💡 改进建议")
    print("=" * 90)

    sl_signals = [o for o in outcomes if o['outcome'] == 'stop_loss_hit']
    if sl_signals:
        print(f"\n  止损信号分析 ({len(sl_signals)} 笔):")
        for o in sl_signals[:10]:
            s = o['signal']
            sl_pct = abs(s.stop_loss - s.entry_price) / s.entry_price * 100
            print(f"    {o['symbol']} {o['cutoff']}: 止损距离 {sl_pct:.1f}%, "
                  f"入场 {s.entry_price:.2f} → 止损 {s.stop_loss:.2f}")

    exp_signals = [o for o in outcomes if o['outcome'] == 'expired']
    if exp_signals:
        avg_exp_ret = np.mean([o['actual_return'] for o in exp_signals])
        print(f"\n  到期信号 ({len(exp_signals)} 笔, 平均回报 {avg_exp_ret:+.2f}%):")
        print(f"    这些信号方向正确但目标太远。建议:")
        print(f"    - 收窄目标价 (目标1更保守)")
        print(f"    - 延长持有期 (44天而非22天)")
        print(f"    - 或设移动止损跟踪利润")


def main():
    print("=" * 90)
    print("🚀 蔡森技术分析 — 破底翻 & 月线缩量见底 阈值优化")
    print("=" * 90)

    print("\n📥 下载数据...\n")
    all_data = download_all()

    print(f"\n🔍 收集原始信号...\n")
    all_raw = collect_all_signals(all_data)
    print(f"  原始信号总数: {len(all_raw)}")

    # Breakdown
    pdf = sum(1 for r in all_raw if '破底翻' in r['signal'].pattern_type.value)
    mysd = sum(1 for r in all_raw if '月线缩量见底' in r['signal'].pattern_type.value)
    print(f"  破底翻: {pdf}")
    print(f"  月线缩量见底: {mysd}")

    if not all_raw:
        print("\n⚠️ 无信号，退出")
        return

    # Confidence distribution
    confs = [r['signal'].confidence for r in all_raw]
    print(f"  置信度范围: {min(confs):.0%} ~ {max(confs):.0%}, 均值 {np.mean(confs):.0%}")

    results = threshold_sweep(all_raw, all_data)
    detailed_analysis(results, all_data)


if __name__ == "__main__":
    main()
