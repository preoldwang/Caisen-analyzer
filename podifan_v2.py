#!/usr/bin/env python3
"""
蔡森技术分析 — 破底翻精简版 v2
================================
直接复用原始分析器的破底翻检测逻辑 (已验证有效)
仅过滤其他信号，专注破底翻
"""

import sys, json, warnings
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime

sys.path.insert(0, '/root/.openclaw/workspace/Caisen-analyzer')
from cai_sen_analyzer import CaiSenAnalyzer, SignalType

warnings.filterwarnings('ignore')

# HSI Blue Chips
BLUE_CHIPS = {
    '0005.HK': 'HSBC', '0006.HK': 'Power Assets', '0011.HK': 'Hang Seng Bank',
    '0012.HK': 'Henderson Land', '0016.HK': 'SHK Properties', '0027.HK': 'Galaxy Ent',
    '0066.HK': 'MTR Corp', '0175.HK': 'Geely Auto', '0241.HK': 'Ali Health',
    '0267.HK': 'CITIC', '0288.HK': 'WH Group', '0386.HK': 'Sinopec',
    '0388.HK': 'HKEX', '0669.HK': 'Techtronic', '0688.HK': 'China Overseas',
    '0700.HK': 'Tencent', '0728.HK': 'China Telecom', '0762.HK': 'China Unicom',
    '0788.HK': 'China Tower', '0823.HK': 'Link REIT', '0836.HK': 'CR Power',
    '0857.HK': 'PetroChina', '0883.HK': 'CNOOC', '0916.HK': 'Longyuan Power',
    '0939.HK': 'CCB', '0941.HK': 'China Mobile', '0960.HK': 'Longfor',
    '0968.HK': 'Xinyi Solar', '0981.HK': 'SMIC', '0992.HK': 'Lenovo',
    '1024.HK': 'Kuaishou', '1038.HK': 'CKI Holdings', '1044.HK': 'Hengan Intl',
    '1088.HK': 'China Shenhua', '1093.HK': 'CSPC Pharma', '1109.HK': 'CR Land',
    '1113.HK': 'CKA', '1177.HK': 'Sino Biopharma', '1209.HK': 'CR Mixc',
    '1211.HK': 'BYD', '1299.HK': 'AIA Group', '1378.HK': 'China Hongqiao',
    '1398.HK': 'ICBC', '1810.HK': 'Xiaomi', '1876.HK': 'Budweiser APAC',
    '1880.HK': 'LVMH', '1928.HK': 'Sands China', '1929.HK': 'Chow Tai Fook',
    '1997.HK': 'Wharf REIC', '2007.HK': 'Country Garden', '2013.HK': 'Weimob',
    '2015.HK': 'Li Auto', '2020.HK': 'Anta Sports', '2050.HK': '361 Degrees',
    '2269.HK': 'WuXi Biologics', '2313.HK': 'Shenzhou Intl', '2318.HK': 'Ping An',
    '2319.HK': 'Mengniu Dairy', '2331.HK': 'Li Ning', '2359.HK': 'WuXi AppTec',
    '2382.HK': 'Sunny Optical', '2628.HK': 'China Life', '2688.HK': 'ENN Energy',
    '2899.HK': 'Zijin Mining', '3690.HK': 'Meituan', '3692.HK': 'Hansoh Pharma',
    '3968.HK': 'CMB', '6030.HK': 'CITIC Securities', '6618.HK': 'JD Health',
    '6690.HK': 'Haier SmartHome', '9618.HK': 'JD.com', '9626.HK': 'Bilibili',
    '9633.HK': 'Nongfu Spring', '9698.HK': 'GDS Holdings', '9888.HK': 'Baidu',
    '9866.HK': 'NIO', '9901.HK': 'New Oriental', '9961.HK': 'Trip.com',
    '9988.HK': 'Alibaba', '9999.HK': 'NetEase', 'GC=F': 'Gold Futures',
}

CUTOFF_DATES = [
    "2025-05-01", "2025-06-01", "2025-07-01", "2025-08-01",
    "2025-09-01", "2025-10-01", "2025-11-01", "2025-12-01",
    "2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01",
]
VERIFY_1M = 22
VERIFY_3M = 66

BULLISH = {"破底翻", "W底", "头肩底", "岛型反转(底)", "量先价行",
           "颈线突破", "回踩支撑", "真突破", "底部放量突破", "V型反转",
           "量价背离(上行)", "康波上行期", "月线缩量见底", "棒康多点", "对数图量幅"}


def download_all():
    data = {}
    n = len(BLUE_CHIPS)
    for i, (sym, name) in enumerate(BLUE_CHIPS.items(), 1):
        print(f"  [{i:3d}/{n}] {sym:<12} {name:<18}", end=" ", flush=True)
        try:
            df = yf.Ticker(sym).history(period="2y", auto_adjust=False)
            if len(df) > 120:
                data[sym] = df
                print(f"✅ {len(df)}")
            else:
                print(f"⚠️ {len(df)}")
        except Exception as e:
            print(f"❌ {str(e)[:35]}")
    return data


def verify(df_full, sig, cutoff_str, verify_days):
    cutoff = pd.Timestamp(cutoff_str)
    if df_full.index.tz is not None:
        cutoff = cutoff.tz_localize(df_full.index.tz)
    future = df_full[df_full.index > cutoff].head(verify_days)
    if len(future) == 0:
        return "no_data", 0, 0
    entry = sig.entry_price
    stop = sig.stop_loss
    t1 = sig.target_price
    t2 = sig.target_price_2
    is_bull = sig.pattern_type.value in BULLISH
    outcome = "expired"
    hit_date = None
    for date, row in future.iterrows():
        if is_bull:
            if row['Low'] <= stop:
                outcome = "stop_loss"; hit_date = date; break
            if row['High'] >= t2:
                outcome = "target2"; hit_date = date; break
            if row['High'] >= t1:
                outcome = "target1"; hit_date = date; break
        else:
            if row['High'] >= stop:
                outcome = "stop_loss"; hit_date = date; break
            if row['Low'] <= t2:
                outcome = "target2"; hit_date = date; break
            if row['Low'] <= t1:
                outcome = "target1"; hit_date = date; break
    end_p = future.iloc[-1]['Close']
    ret = (end_p - entry) / entry * 100 if is_bull else (entry - end_p) / entry * 100
    days = (hit_date - future.index[0]).days if hit_date else verify_days
    return outcome, round(ret, 2), days


def run_backtest(all_data):
    signals = []
    seen_weekly = set()
    total = len(all_data)

    for si, (sym, name) in enumerate(BLUE_CHIPS.items(), 1):
        if sym not in all_data:
            continue
        df_full = all_data[sym]

        for ci, cutoff_str in enumerate(CUTOFF_DATES):
            cutoff = pd.Timestamp(cutoff_str)
            if df_full.index.tz is not None:
                cutoff = cutoff.tz_localize(df_full.index.tz)
            df_trunc = df_full[df_full.index <= cutoff].copy()
            if len(df_trunc) < 90:
                continue

            try:
                analyzer = CaiSenAnalyzer()
                analyzer.load_data(sym, df_trunc)
                result = analyzer.analyze()

                # Filter to 破底翻 ONLY
                pdf = [p for p in result.patterns if p.pattern_type.value == "破底翻"]

                # B&H
                future = df_full[df_full.index > cutoff]
                f1m = future.head(VERIFY_1M)
                f3m = future.head(VERIFY_3M)
                bnh_1m = (f1m.iloc[-1]['Close'] - df_trunc.iloc[-1]['Close']) / df_trunc.iloc[-1]['Close'] * 100 if len(f1m) > 0 else 0
                bnh_3m = (f3m.iloc[-1]['Close'] - df_trunc.iloc[-1]['Close']) / df_trunc.iloc[-1]['Close'] * 100 if len(f3m) > 0 else 0

                for sig in pdf:
                    # Dedup: weekly signals have "N/A (weekly)" as signal_date
                    if sig.timeframe == "weekly":
                        key = (sym, sig.entry_price, round(sig.target_price, 1), cutoff_str)
                        if key in seen_weekly:
                            continue
                        seen_weekly.add(key)
                    elif sig.timeframe == "daily":
                        if sig.signal_date[:7] != cutoff_str[:7]:
                            continue

                    outcome, ret_1m, days = verify(df_full, sig, cutoff_str, VERIFY_1M)
                    _, ret_3m, _ = verify(df_full, sig, cutoff_str, VERIFY_3M)

                    signals.append({
                        'symbol': sym, 'name': name, 'cutoff': cutoff_str,
                        'signal_date': str(sig.signal_date),
                        'timeframe': sig.timeframe,
                        'confidence': sig.confidence,
                        'entry': sig.entry_price,
                        'stop_loss': sig.stop_loss,
                        'target1': sig.target_price,
                        'target2': sig.target_price_2,
                        'rr': sig.risk_reward_ratio,
                        'neckline': sig.neckline,
                        'description': sig.description[:80],
                        'outcome': outcome,
                        'ret_1m': ret_1m,
                        'ret_3m': ret_3m,
                        'days_held': days,
                        'bnh_1m': round(bnh_1m, 2),
                        'bnh_3m': round(bnh_3m, 2),
                    })

            except Exception:
                pass

        if si % 15 == 0:
            print(f"  [{si}/{total}] {sym}")

    return signals


def print_report(sigs):
    if not sigs:
        print("\n⚠️ No signals!")
        return

    T = len(sigs)
    t1 = sum(1 for s in sigs if s['outcome'] == 'target1')
    t2 = sum(1 for s in sigs if s['outcome'] == 'target2')
    sl = sum(1 for s in sigs if s['outcome'] == 'stop_loss')
    exp = sum(1 for s in sigs if s['outcome'] == 'expired')
    hit = t1 + t2
    rets = [s['ret_1m'] for s in sigs]
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]

    print("\n" + "=" * 95)
    print("📊 蔡森破底翻精简版 — 全部恒生指数蓝筹 12个月回测")
    print("=" * 95)

    print(f"\n  总信号数: {T}")
    print(f"  ✅🎯 命中(T1+T2): {hit}/{T} = {hit/T*100:.1f}%")
    print(f"    ├ T1达成: {t1} ({t1/T*100:.1f}%)")
    print(f"    └ T2达成(黄金比例): {t2} ({t2/T*100:.1f}%)")
    print(f"  ❌ 止损: {sl}/{T} = {sl/T*100:.1f}%")
    print(f"  ⏰ 到期: {exp}/{T} = {exp/T*100:.1f}%")
    print(f"\n  📊 平均1M回报: {np.mean(rets):+.2f}%")
    print(f"  📊 平均3M回报: {np.mean([s['ret_3m'] for s in sigs]):+.2f}%")
    print(f"  📊 盈利: +{np.mean(wins):.2f}% ({len(wins)}笔, 胜率{len(wins)/T*100:.1f}%)")
    if losses:
        print(f"  📊 亏损: {np.mean(losses):.2f}% ({len(losses)}笔)")
    print(f"  📊 盈亏比: {len(wins)}:{len(losses)} = {len(wins)/(len(losses) or 1):.2f}:1")

    # By timeframe
    print(f"\n" + "━" * 95)
    print("📊 按时间框架")
    print("━" * 95)
    for tf in ['daily', 'weekly']:
        sub = [s for s in sigs if s['timeframe'] == tf]
        if not sub:
            print(f"  {tf:>7}: 0 signals")
            continue
        sh = sum(1 for s in sub if s['outcome'] in ('target1', 'target2'))
        ssl = sum(1 for s in sub if s['outcome'] == 'stop_loss')
        print(f"  {tf:>7}: {len(sub):>4} signals | 命中 {sh/len(sub)*100:>5.1f}% | "
              f"止损 {ssl/len(sub)*100:>5.1f}% | 回报 {np.mean([s['ret_1m'] for s in sub]):>+7.2f}%")

    # By instrument
    print(f"\n" + "━" * 95)
    print("📊 按标的 (所有)")
    print("━" * 95)
    inst = {}
    for s in sigs:
        sym = s['symbol']
        if sym not in inst:
            inst[sym] = {'n': 0, 'hit': 0, 'sl': 0, 'rets': [], 'bnh': [], 'name': s['name']}
        inst[sym]['n'] += 1
        if s['outcome'] in ('target1', 'target2'): inst[sym]['hit'] += 1
        if s['outcome'] == 'stop_loss': inst[sym]['sl'] += 1
        inst[sym]['rets'].append(s['ret_1m'])
        inst[sym]['bnh'].append(s['bnh_1m'])

    print(f"  {'标的':<10} {'名称':<18} {'信号':>5} {'命中':>5} {'命中率':>8} {'止损':>5} "
          f"{'平均回报':>10} {'买持':>10} {'超额':>10}")
    print("  " + "-" * 88)
    for sym, d in sorted(inst.items(), key=lambda x: -x[1]['n']):
        wr = d['hit'] / d['n'] * 100
        avg = np.mean(d['rets'])
        bnh = np.mean(d['bnh'])
        print(f"  {sym:<10} {d['name']:<18} {d['n']:>5} {d['hit']:>5} {wr:>7.1f}% "
              f"{d['sl']:>5} {avg:>+9.2f}% {bnh:>+9.2f}% {avg-bnh:>+9.2f}%")

    # Monthly
    print(f"\n" + "━" * 95)
    print("💰 月度组合收益")
    print("━" * 95)
    print(f"  {'月份':<14} {'信号':>5} {'策略1M':>8} {'买持1M':>8} {'超额':>8} {'累计策略':>10} {'累计买持':>10}")
    print("  " + "-" * 65)
    cum_s = cum_b = 1.0
    for m in CUTOFF_DATES:
        ms = [s for s in sigs if s['cutoff'] == m]
        n = len(ms)
        sr = np.mean([s['ret_1m'] for s in ms]) if n else 0
        br = np.mean([s['bnh_1m'] for s in ms]) if n else 0
        cum_s *= (1 + sr/100)
        cum_b *= (1 + br/100)
        print(f"  {m:<14} {n:>5} {sr:>+7.2f}% {br:>+7.2f}% {sr-br:>+7.2f}% "
              f"{(cum_s-1)*100:>+9.2f}% {(cum_b-1)*100:>+9.2f}%")
    print(f"  {'累计':<14} {T:>5} {'':>8} {'':>8} {'':>8} {(cum_s-1)*100:>+9.2f}% {(cum_b-1)*100:>+9.2f}%")

    # Best & worst
    om = {'target1': '✅T1', 'target2': '🎯T2', 'stop_loss': '❌SL', 'expired': '⏰EXP'}
    print(f"\n" + "━" * 95)
    print("🏆 最佳交易 (前15)")
    print("━" * 95)
    for s in sorted(sigs, key=lambda x: -x['ret_1m'])[:15]:
        print(f"  {s['symbol']:<10} {s['cutoff']:<12} {s['timeframe']:<7} C={s['confidence']:.0%} "
              f"E={s['entry']:>8.2f} → {om.get(s['outcome'],'?'):<5} {s['ret_1m']:>+7.2f}% "
              f"(B&H: {s['bnh_1m']:>+7.2f}%)")

    print(f"\n  💀 最差交易 (前10):")
    for s in sorted(sigs, key=lambda x: x['ret_1m'])[:10]:
        print(f"  {s['symbol']:<10} {s['cutoff']:<12} {s['timeframe']:<7} C={s['confidence']:.0%} "
              f"E={s['entry']:>8.2f} → {om.get(s['outcome'],'?'):<5} {s['ret_1m']:>+7.2f}% "
              f"(B&H: {s['bnh_1m']:>+7.2f}%)")

    # Comparison
    print(f"\n" + "━" * 95)
    print("📊 vs 完整版工具")
    print("━" * 95)
    print(f"  {'指标':<22} {'完整版(全部信号)':>18} {'破底翻only':>15}")
    print("  " + "-" * 57)
    print(f"  {'总信号数':<22} {'1,074':>18} {T:>15}")
    print(f"  {'命中率':<22} {'20.8%':>18} {hit/T*100:>14.1f}%")
    print(f"  {'止损率':<22} {'59.5%':>18} {sl/T*100:>14.1f}%")
    print(f"  {'平均回报':<22} {'-14.32%':>18} {np.mean(rets):>+14.2f}%")
    print(f"  {'策略累计':<22} {'-85.54%':>18} {(cum_s-1)*100:>+14.2f}%")
    print(f"  {'买持累计':<22} {'+21.72%':>18} {(cum_b-1)*100:>+14.2f}%")
    print(f"  {'超额':<22} {'-107.26%':>18} {(cum_s-cum_b)*100:>+14.2f}%")

    # Confidence threshold optimization
    print(f"\n" + "━" * 95)
    print("📊 置信度阈值优化")
    print("━" * 95)
    for thresh in [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90]:
        sub = [s for s in sigs if s['confidence'] >= thresh]
        if not sub: continue
        sh = sum(1 for s in sub if s['outcome'] in ('target1', 'target2'))
        ssl = sum(1 for s in sub if s['outcome'] == 'stop_loss')
        sw = sum(1 for s in sub if s['ret_1m'] > 0)
        avg_r = np.mean([s['ret_1m'] for s in sub])
        bnh = np.mean([s['bnh_1m'] for s in sub])
        print(f"  ≥{thresh:.0%}: {len(sub):>4} sigs | 命中 {sh/len(sub)*100:>5.1f}% | "
              f"止损 {ssl/len(sub)*100:>5.1f}% | 回报 {avg_r:>+7.2f}% | "
              f"胜率 {sw/len(sub)*100:>5.1f}% | B&H {bnh:>+7.2f}%")


def main():
    print("=" * 95)
    print("🚀 蔡森破底翻精简版 v2 — 全部恒生指数蓝筹 12个月回测")
    print(f"   标的: {len(BLUE_CHIPS)} | 期间: May 2025 → Apr 2026")
    print("=" * 95)

    print("\n📥 下载数据...\n")
    data = download_all()
    print(f"\n✅ {len(data)}/{len(BLUE_CHIPS)}")

    print(f"\n🔍 回测中...\n")
    sigs = run_backtest(data)
    print(f"  共 {len(sigs)} 个破底翻信号")

    print_report(sigs)

    with open('/root/.openclaw/workspace/Caisen-analyzer/podifan_v2_results.json', 'w') as f:
        json.dump(sigs, f, indent=2, default=str)
    print(f"\n💾 Saved: podifan_v2_results.json")


if __name__ == "__main__":
    main()
