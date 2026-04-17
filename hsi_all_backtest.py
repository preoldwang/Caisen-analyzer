#!/usr/bin/env python3
"""
蔡森技术分析 — 全部恒生指数蓝筹股 回测
======================================
测试所有 HSI 成分股 + 黄金，看看破底翻 & 月线缩量见底在更广范围的表现
"""

import sys, json, warnings, traceback
import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, '/root/.openclaw/workspace/Caisen-analyzer')
from cai_sen_analyzer import CaiSenAnalyzer, SignalType

warnings.filterwarnings('ignore')

# All HSI Blue Chip constituents (as of 2025/2026)
# Format: yfinance ticker
HSI_BLUE_CHIPS = {
    '0005.HK': 'HSBC Holdings',
    '0006.HK': 'Power Assets',
    '0011.HK': 'Hang Seng Bank',
    '0012.HK': 'Henderson Land',
    '0016.HK': 'SHK Properties',
    '0027.HK': 'Galaxy Entertainment',
    '0066.HK': 'MTR Corporation',
    '0175.HK': 'Geely Auto',
    '0241.HK': 'Alibaba Health',
    '0267.HK': 'CITIC',
    '0288.HK': 'WH Group',
    '0386.HK': 'Sinopec',
    '0388.HK': 'HKEX',
    '0669.HK': 'Techtronic',
    '0688.HK': 'China Overseas',
    '0700.HK': 'Tencent',
    '0762.HK': 'China Unicom',
    '0823.HK': 'Link REIT',
    '0836.HK': 'CR Power',
    '0857.HK': 'PetroChina',
    '0883.HK': 'CNOOC',
    '0916.HK': 'Longyuan Power',
    '0939.HK': 'CCB',
    '0941.HK': 'China Mobile',
    '0960.HK': 'Longfor',
    '0968.HK': 'Xinyi Solar',
    '0981.HK': 'SMIC',
    '0992.HK': 'Lenovo',
    '1024.HK': 'Kuaishou',
    '1038.HK': 'CKI Holdings',
    '1044.HK': 'Hengan Intl',
    '1088.HK': 'China Shenhua',
    '1093.HK': 'CSPC Pharma',
    '1109.HK': 'CR Land',
    '1113.HK': 'CKA',
    '1177.HK': 'Sino Biopharma',
    '1209.HK': 'CR Mixc',
    '1211.HK': 'BYD',
    '1299.HK': 'AIA Group',
    '1378.HK': 'China Hongqiao',
    '1398.HK': 'ICBC',
    '1810.HK': 'Xiaomi',
    '1876.HK': 'Budweiser APAC',
    '1880.HK': 'LVMH',
    '1928.HK': 'Sands China',
    '1929.HK': 'Chow Tai Fook',
    '1997.HK': 'Wharf REIC',
    '2007.HK': 'Country Garden',
    '2013.HK': 'Weimob',
    '2015.HK': 'Li Auto',
    '2020.HK': 'Anta Sports',
    '2269.HK': 'WuXi Biologics',
    '2313.HK': 'Shenzhou Intl',
    '2318.HK': 'Ping An',
    '2319.HK': 'Mengniu Dairy',
    '2331.HK': 'Li Ning',
    '2359.HK': 'WuXi AppTec',
    '2382.HK': 'Sunny Optical',
    '2628.HK': 'China Life',
    '2688.HK': 'ENN Energy',
    '2899.HK': 'Zijin Mining',
    '3690.HK': 'Meituan',
    '3692.HK': 'Hansoh Pharma',
    '3968.HK': 'CMB',
    '6030.HK': 'CITIC Securities',
    '6618.HK': 'JD Health',
    '6690.HK': 'Haier SmartHome',
    '9618.HK': 'JD.com',
    '9626.HK': 'Bilibili',
    '9633.HK': 'Nongfu Spring',
    '9698.HK': 'GDS Holdings',
    '9888.HK': 'Baidu',
    '9866.HK': 'NIO',
    '9901.HK': 'New Oriental',
    '9961.HK': 'Trip.com',
    '9988.HK': 'Alibaba',
    '9999.HK': 'NetEase',
    '2050.HK': '361 Degrees',
    '0728.HK': 'China Telecom',
    '0788.HK': 'China Tower',
    '0883.HK': 'CNOOC',  # duplicate removed
    'GC=F': 'Gold Futures',
}

# Remove duplicates
seen = set()
BLUE_CHIPS = {}
for k, v in HSI_BLUE_CHIPS.items():
    if k not in seen:
        BLUE_CHIPS[k] = v
        seen.add(k)

CUTOFF_DATES = [
    "2025-05-01", "2025-06-01", "2025-07-01", "2025-08-01",
    "2025-09-01", "2025-10-01", "2025-11-01", "2025-12-01",
    "2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01",
]
VERIFY_DAYS_1M = 22
VERIFY_DAYS_3M = 66

TARGET_SIGNALS = {
    "破底翻", "月线缩量见底", "月线爆量翻黑", "周线破底翻",
    "假突破", "真突破", "回踩支撑", "量价背离(上行)", "量价背离(下行)",
    "底部放量突破", "反弹无力", "跌破支撑", "骗线确认", "V型反转",
    "W底", "头肩底", "头肩顶", "M顶",
    "岛型反转(底)", "岛型反转(顶)", "量先价行",
    "康波上行期", "康波下行期", "八年循环转折",
    "棒康多点", "棒康空点", "对数图量幅", "月线头肩型态",
}

BULLISH = {"破底翻", "W底", "头肩底", "岛型反转(底)", "量先价行",
           "颈线突破", "回踩支撑", "真突破", "底部放量突破", "V型反转",
           "量价背离(上行)", "康波上行期", "月线缩量见底", "棒康多点", "对数图量幅"}
BEARISH = {"假突破", "颈线跌破", "头肩顶", "M顶", "岛型反转(顶)",
           "反弹无力", "跌破支撑", "量价背离(下行)", "康波下行期",
           "月线爆量翻黑", "棒康空点", "騙線确认", "骗线确认"}


def download_all():
    data = {}
    n = len(BLUE_CHIPS)
    for i, (symbol, name) in enumerate(BLUE_CHIPS.items(), 1):
        print(f"  [{i:3d}/{n}] {symbol:<12} {name:<20}", end=" ", flush=True)
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="2y")
            if len(df) > 120:
                data[symbol] = df
                print(f"✅ {len(df)} rows")
            else:
                print(f"⚠️ only {len(df)} rows")
        except Exception as e:
            print(f"❌ {str(e)[:50]}")
    return data


def run_backtest(all_data):
    """Run analyzer at each cutoff, collect all signals, verify outcomes."""
    all_signals = []
    seen_monthly = set()

    total = len(all_data)
    for si, (symbol, name) in enumerate(BLUE_CHIPS.items(), 1):
        if symbol not in all_data:
            continue
        df_full = all_data[symbol]

        for ci, cutoff_str in enumerate(CUTOFF_DATES):
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

                # B&H returns
                future = df_full[df_full.index > cutoff]
                f1m = future.head(VERIFY_DAYS_1M)
                f3m = future.head(VERIFY_DAYS_3M)
                bnh_1m = 0
                bnh_3m = 0
                if len(f1m) > 0:
                    bnh_1m = (f1m.iloc[-1]['Close'] - df_trunc.iloc[-1]['Close']) / df_trunc.iloc[-1]['Close'] * 100
                if len(f3m) > 0:
                    bnh_3m = (f3m.iloc[-1]['Close'] - df_trunc.iloc[-1]['Close']) / df_trunc.iloc[-1]['Close'] * 100

                for sig in result.patterns:
                    # Dedup monthly signals
                    if sig.timeframe == "monthly":
                        key = (symbol, str(sig.signal_date), sig.entry_price)
                        if key in seen_monthly:
                            continue
                        seen_monthly.add(key)
                    elif sig.timeframe == "weekly":
                        if sig.signal_date in ("N/A (weekly)", "N/A"):
                            key = (symbol, "weekly", sig.entry_price, cutoff_str)
                        else:
                            if str(sig.signal_date)[:7] != cutoff_str[:7]:
                                continue
                            key = (symbol, str(sig.signal_date), sig.entry_price)
                    else:
                        if str(sig.signal_date)[:7] != cutoff_str[:7]:
                            continue
                        key = (symbol, str(sig.signal_date), sig.entry_price)

                    # Verify outcome
                    outcome, actual_ret, days_held = verify(df_full, sig, cutoff_str, VERIFY_DAYS_1M)
                    _, ret_3m, _ = verify(df_full, sig, cutoff_str, VERIFY_DAYS_3M)

                    is_bull = sig.pattern_type.value in BULLISH
                    is_bear = sig.pattern_type.value in BEARISH

                    all_signals.append({
                        'symbol': symbol,
                        'name': name,
                        'cutoff': cutoff_str,
                        'signal': sig.pattern_type.value,
                        'timeframe': sig.timeframe,
                        'direction': 'BUY' if is_bull else ('SELL' if is_bear else 'N/A'),
                        'confidence': sig.confidence,
                        'entry': sig.entry_price,
                        'stop_loss': sig.stop_loss,
                        'target1': sig.target_price,
                        'target2': sig.target_price_2,
                        'rr': sig.risk_reward_ratio,
                        'outcome': outcome,
                        'ret_1m': round(actual_ret, 2),
                        'ret_3m': round(ret_3m, 2),
                        'days_held': days_held,
                        'bnh_1m': round(bnh_1m, 2),
                        'bnh_3m': round(bnh_3m, 2),
                    })

                if si % 10 == 0 and ci == 0:
                    print(f"  [{si}/{total}] processed {symbol}...")

            except Exception as e:
                pass  # skip errors silently

    return all_signals


def verify(df_full, signal, cutoff_str, verify_days):
    cutoff = pd.Timestamp(cutoff_str)
    if df_full.index.tz is not None:
        cutoff = cutoff.tz_localize(df_full.index.tz)
    future = df_full[df_full.index > cutoff].head(verify_days)
    if len(future) == 0:
        return "no_data", 0, 0

    entry = signal.entry_price
    stop = signal.stop_loss
    t1 = signal.target_price
    t2 = signal.target_price_2
    is_bull = signal.pattern_type.value in BULLISH

    outcome = "expired"
    hit_date = None
    for date, row in future.iterrows():
        if is_bull:
            if row['Low'] <= stop:
                outcome = "stop_loss"
                hit_date = date
                break
            if row['High'] >= t2:
                outcome = "target2"
                hit_date = date
                break
            if row['High'] >= t1:
                outcome = "target1"
                hit_date = date
                break
        else:
            if row['High'] >= stop:
                outcome = "stop_loss"
                hit_date = date
                break
            if row['Low'] <= t2:
                outcome = "target2"
                hit_date = date
                break
            if row['Low'] <= t1:
                outcome = "target1"
                hit_date = date
                break

    end_price = future.iloc[-1]['Close']
    if is_bull:
        ret = (end_price - entry) / entry * 100
    else:
        ret = (entry - end_price) / entry * 100

    days = (hit_date - future.index[0]).days if hit_date else verify_days
    return outcome, ret, days


def print_report(signals):
    if not signals:
        print("\n⚠️ 无信号!")
        return

    # ── Overall ──
    print("\n" + "=" * 100)
    print("📊 全部恒生指数蓝筹 + 黄金 — 蔡森技术分析 12个月滚动回测")
    print("=" * 100)

    total = len(signals)
    t1 = sum(1 for s in signals if s['outcome'] == 'target1')
    t2 = sum(1 for s in signals if s['outcome'] == 'target2')
    sl = sum(1 for s in signals if s['outcome'] == 'stop_loss')
    exp = sum(1 for s in signals if s['outcome'] == 'expired')
    hit = t1 + t2
    rets = [s['ret_1m'] for s in signals]

    print(f"\n  总信号数: {total}")
    print(f"  ✅🎯 命中(任意目标): {hit}/{total} = {hit/total*100:.1f}%")
    print(f"  ❌ 止损: {sl}/{total} = {sl/total*100:.1f}%")
    print(f"  ⏰ 到期: {exp}/{total} = {exp/total*100:.1f}%")
    print(f"  📊 平均1M回报: {np.mean(rets):+.2f}%")
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    if wins: print(f"  📊 盈利: +{np.mean(wins):.2f}% ({len(wins)}笔)")
    if losses: print(f"  📊 亏损: {np.mean(losses):.2f}% ({len(losses)}笔)")

    # ── By signal type ──
    print("\n" + "━" * 100)
    print("📊 按信号类型 (按出现频率排序)")
    print("━" * 100)
    type_stats = {}
    for s in signals:
        st = s['signal']
        if st not in type_stats:
            type_stats[st] = {'n': 0, 'hit': 0, 'sl': 0, 'rets': [], 'dir': s['direction']}
        type_stats[st]['n'] += 1
        if s['outcome'] in ('target1', 'target2'):
            type_stats[st]['hit'] += 1
        if s['outcome'] == 'stop_loss':
            type_stats[st]['sl'] += 1
        type_stats[st]['rets'].append(s['ret_1m'])

    print(f"  {'信号类型':<20} {'方向':>5} {'数量':>5} {'命中':>5} {'命中率':>8} {'止损':>5} {'止损率':>8} {'平均回报':>10}")
    print("  " + "-" * 80)
    for st, d in sorted(type_stats.items(), key=lambda x: -x[1]['n']):
        wr = d['hit']/d['n']*100 if d['n'] > 0 else 0
        slr = d['sl']/d['n']*100 if d['n'] > 0 else 0
        avg = np.mean(d['rets'])
        emoji = "🟢" if d['dir'] == 'BUY' else ("🔴" if d['dir'] == 'SELL' else "⚪")
        print(f"  {emoji} {st:<18} {d['dir']:>5} {d['n']:>5} {d['hit']:>5} {wr:>7.1f}% {d['sl']:>5} {slr:>7.1f}% {avg:>+9.2f}%")

    # ── Top performers (破底翻 & 月线缩量见底) ──
    print("\n" + "━" * 100)
    print("⭐ 破底翻 & 月线缩量见底 详细")
    print("━" * 100)
    special = [s for s in signals if s['signal'] in ('破底翻', '月线缩量见底')]
    if special:
        print(f"  {'标的':<10} {'月份':<12} {'信号':<16} {'方向':>5} {'置信':>5} {'入场':>8} {'止损':>8} "
              f"{'目标1':>8} {'结果':<10} {'1M回报':>8} {'3M回报':>8} {'买持1M':>8}")
        print("  " + "-" * 105)
        for s in sorted(special, key=lambda x: x['cutoff']):
            om = {'target1': '✅T1', 'target2': '🎯T2', 'stop_loss': '❌SL', 'expired': '⏰EXP'}
            print(f"  {s['symbol']:<10} {s['cutoff']:<12} {s['signal']:<16} {s['direction']:>5} "
                  f"{s['confidence']:>5.0%} {s['entry']:>8.2f} {s['stop_loss']:>8.2f} "
                  f"{s['target1']:>8.2f} {om.get(s['outcome'], '?'):<10} "
                  f"{s['ret_1m']:>+7.2f}% {s['ret_3m']:>+7.2f}% {s['bnh_1m']:>+7.2f}%")
    else:
        print("  ⚠️ 无破底翻或月线缩量见底信号")

    # ── By instrument (top 20 by signal count) ──
    print("\n" + "━" * 100)
    print("📊 按标的汇总 (前20)")
    print("━" * 100)
    inst_stats = {}
    for s in signals:
        sym = s['symbol']
        if sym not in inst_stats:
            inst_stats[sym] = {'n': 0, 'hit': 0, 'buy': 0, 'sell': 0, 'rets': [], 'bnh': []}
        inst_stats[sym]['n'] += 1
        if s['outcome'] in ('target1', 'target2'):
            inst_stats[sym]['hit'] += 1
        if s['direction'] == 'BUY':
            inst_stats[sym]['buy'] += 1
        elif s['direction'] == 'SELL':
            inst_stats[sym]['sell'] += 1
        inst_stats[sym]['rets'].append(s['ret_1m'])
        inst_stats[sym]['bnh'].append(s['bnh_1m'])

    print(f"  {'标的':<10} {'名称':<20} {'信号':>5} {'🟢':>4} {'🔴':>4} {'命中率':>8} {'平均回报':>10} {'买持':>10}")
    print("  " + "-" * 75)
    for sym, d in sorted(inst_stats.items(), key=lambda x: -x[1]['n'])[:20]:
        name = BLUE_CHIPS.get(sym, '')
        wr = d['hit']/d['n']*100 if d['n'] > 0 else 0
        avg = np.mean(d['rets'])
        bnh = np.mean(d['bnh'])
        print(f"  {sym:<10} {name:<20} {d['n']:>5} {d['buy']:>4} {d['sell']:>4} {wr:>7.1f}% {avg:>+9.2f}% {bnh:>+9.2f}%")

    # ── Monthly portfolio ──
    print("\n" + "━" * 100)
    print("💰 月度组合收益 (所有BUY/SELL建议等权)")
    print("━" * 100)
    print(f"  {'月份':<14} {'信号':>5} {'BUY':>4} {'SELL':>4} {'策略1M':>8} {'买持1M':>8} {'超额':>8}")
    print("  " + "-" * 55)
    cum_strat = 1.0
    cum_bnh = 1.0
    for m in CUTOFF_DATES:
        ms = [s for s in signals if s['cutoff'] == m]
        n = len(ms)
        bu = sum(1 for s in ms if s['direction'] == 'BUY')
        se = sum(1 for s in ms if s['direction'] == 'SELL')
        if n > 0:
            sr = np.mean([s['ret_1m'] for s in ms])
            br = np.mean([s['bnh_1m'] for s in ms])
        else:
            sr = 0
            br = 0
        cum_strat *= (1 + sr/100)
        cum_bnh *= (1 + br/100)
        print(f"  {m:<14} {n:>5} {bu:>4} {se:>4} {sr:>+7.2f}% {br:>+7.2f}% {sr-br:>+7.2f}%")
    print(f"  {'累计':<14} {'':>5} {'':>4} {'':>4} {(cum_strat-1)*100:>+7.2f}% {(cum_bnh-1)*100:>+7.2f}% {(cum_strat-cum_bnh)*100:>+7.2f}%")

    # ── Best single trades ──
    print("\n" + "━" * 100)
    print("🏆 最佳单笔交易 (按1M回报排序, 前15)")
    print("━" * 100)
    top = sorted(signals, key=lambda x: -x['ret_1m'])[:15]
    for s in top:
        om = {'target1': '✅T1', 'target2': '🎯T2', 'stop_loss': '❌SL', 'expired': '⏰EXP'}
        print(f"  {s['symbol']:<10} {s['cutoff']:<12} {s['signal']:<16} {s['direction']:>5} "
              f"{s['entry']:>8.2f} → {om.get(s['outcome'], '?'):<5} {s['ret_1m']:>+7.2f}% (B&H: {s['bnh_1m']:>+7.2f}%)")

    # ── Worst single trades ──
    print("\n  💀 最差单笔交易 (前15):")
    worst = sorted(signals, key=lambda x: x['ret_1m'])[:15]
    for s in worst:
        om = {'target1': '✅T1', 'target2': '🎯T2', 'stop_loss': '❌SL', 'expired': '⏰EXP'}
        print(f"  {s['symbol']:<10} {s['cutoff']:<12} {s['signal']:<16} {s['direction']:>5} "
              f"{s['entry']:>8.2f} → {om.get(s['outcome'], '?'):<5} {s['ret_1m']:>+7.2f}% (B&H: {s['bnh_1m']:>+7.2f}%)")

    # ── Specific to user's requested stocks ──
    print("\n" + "━" * 100)
    print("🎯 用户指定标的 (00916 01880 00728 00788 02318 00836 09961 02050 + Gold)")
    print("━" * 100)
    user_stocks = {'0916.HK', '1880.HK', '0728.HK', '0788.HK', '2318.HK', '0836.HK', '9961.HK', '2050.HK', 'GC=F'}
    user_sigs = [s for s in signals if s['symbol'] in user_stocks]
    if user_sigs:
        total_u = len(user_sigs)
        hit_u = sum(1 for s in user_sigs if s['outcome'] in ('target1', 'target2'))
        sl_u = sum(1 for s in user_sigs if s['outcome'] == 'stop_loss')
        print(f"  信号数: {total_u} | 命中: {hit_u} ({hit_u/total_u*100:.1f}%) | 止损: {sl_u} ({sl_u/total_u*100:.1f}%)")
        print(f"  平均回报: {np.mean([s['ret_1m'] for s in user_sigs]):+.2f}%")

        # By type for user stocks
        for st in ['破底翻', '月线缩量见底']:
            sub = [s for s in user_sigs if s['signal'] == st]
            if sub:
                sh = sum(1 for s in sub if s['outcome'] in ('target1', 'target2'))
                print(f"  {st}: {len(sub)} signals, {sh} hit ({sh/len(sub)*100:.0f}%)")


def main():
    print("=" * 100)
    print("🚀 全部恒生指数蓝筹 + 黄金 — 蔡森技术分析 12个月回测")
    print(f"   共 {len(BLUE_CHIPS)} 个标的 × 12 个月")
    print("=" * 100)

    print("\n📥 下载数据...\n")
    all_data = download_all()
    print(f"\n✅ 成功下载 {len(all_data)}/{len(BLUE_CHIPS)} 个标的")

    print(f"\n🔍 运行回测...\n")
    signals = run_backtest(all_data)
    print(f"  共收集 {len(signals)} 个信号")

    print_report(signals)

    with open('/root/.openclaw/workspace/Caisen-analyzer/hsi_all_backtest.json', 'w') as f:
        json.dump(signals, f, indent=2, default=str)
    print(f"\n💾 详细结果已保存: hsi_all_backtest.json")


if __name__ == "__main__":
    main()
