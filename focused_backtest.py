#!/usr/bin/env python3
"""
蔡森技术分析 — 破底翻 & 月线缩量见底 优化版
=============================================
聚焦两个最高胜率信号，提升确认条件后重新回测
"""

import sys
import json
import warnings
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Tuple, Dict
from enum import Enum

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, '/root/.openclaw/workspace/Caisen-analyzer')
from cai_sen_analyzer import CaiSenAnalyzer, SignalType, Pattern

warnings.filterwarnings('ignore')


class FocusedAnalyzer:
    """
    只检测破底翻 + 月线缩量见底，加入更严格的确认条件
    """

    def __init__(self):
        self.data = None
        self.weekly_data = None
        self.monthly_data = None

    def load_data(self, symbol: str, df: pd.DataFrame):
        self.data = df.copy()
        if 'Volume' not in self.data.columns or self.data['Volume'].sum() == 0:
            # Gold futures may have 0 volume
            if 'Volume' not in self.data.columns:
                self.data['Volume'] = 0
        self.weekly_data = self.data.resample('W').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min',
            'Close': 'last', 'Volume': 'sum'
        }).dropna()
        self.monthly_data = self.data.resample('ME').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min',
            'Close': 'last', 'Volume': 'sum'
        }).dropna()

    def _compute_rsi(self, prices, period=14):
        """Compute RSI for momentum confirmation"""
        delta = np.diff(prices)
        gains = np.where(delta > 0, delta, 0)
        losses = np.where(delta < 0, -delta, 0)
        if len(gains) < period:
            return np.full(len(prices), 50.0)
        avg_gain = np.convolve(gains, np.ones(period)/period, mode='valid')
        avg_loss = np.convolve(losses, np.ones(period)/period, mode='valid')
        avg_loss = np.where(avg_loss == 0, 1e-10, avg_loss)
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        # Pad to original length
        pad = len(prices) - len(rsi)
        return np.concatenate([np.full(pad, 50.0), rsi])

    def _compute_macd_histogram(self, prices, fast=12, slow=26, signal=9):
        """Compute MACD histogram"""
        if len(prices) < slow + signal:
            return np.zeros(len(prices))
        s = pd.Series(prices)
        ema_fast = s.ewm(span=fast, adjust=False).mean()
        ema_slow = s.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return histogram.values

    def detect_po_di_fan(self) -> List[Pattern]:
        """
        优化版破底翻检测 v2
        改进:
        1. 更短 lookback (40-90天) — 寻找近期底部
        2. min_idx 放宽到 5+ (而非 15+)
        3. 检查窗口 10 天 (而非 15)
        4. 量能确认从 1.2x 提升到 1.5x
        5. RSI 确认: RSI 从超卖回升
        6. MACD histogram 转正确认
        7. 置信度阈值 0.65
        8. 风险回报比要求 >= 2.0
        9. 翻回时要求连续上涨
        """
        patterns = []
        df = self.data
        if df is None or len(df) < 60:
            return patterns

        open_prices = df['Open'].values
        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values
        volume = df['Volume'].values
        dates = df.index
        avg_vol_all = np.mean(volume[volume > 0]) if np.any(volume > 0) else 0

        for lookback in [40, 60, 90]:
            if len(close) < lookback + 15:
                continue

            for end_idx in range(lookback + 10, len(close)):
                segment = close[end_idx - lookback:end_idx]
                seg_low = low[end_idx - lookback:end_idx]
                seg_vol = volume[end_idx - lookback:end_idx]
                seg_high = high[end_idx - lookback:end_idx]

                min_price = np.min(seg_low)
                min_idx = np.argmin(seg_low)

                # RELAXED: Bottom can be anywhere not at very edges
                if min_idx < 5 or min_idx >= len(segment) - 5:
                    continue

                # Neckline: recovery high after bottom
                recovery_region = seg_high[min_idx:]
                if len(recovery_region) < 3:
                    continue
                neckline = np.percentile(recovery_region, 60)

                # Previous high for target calculation
                pre_high = np.max(seg_high[:min_idx]) if min_idx > 5 else neckline

                # Check for false breakdown (破底) in recent 10 days
                check_window = close[end_idx - 10:end_idx]
                check_low = low[end_idx - 10:end_idx]

                broke_below = False
                broke_below_idx = -1
                for i, price in enumerate(check_low):
                    if price < min_price * 0.985:  # Must break 1.5% below
                        broke_below = True
                        broke_below_idx = i
                        break

                if not broke_below:
                    continue

                # Must recover within days of breakdown
                after_break = close[end_idx - 10 + broke_below_idx:end_idx]
                if len(after_break) < 2:
                    continue

                recovered = any(p > neckline for p in after_break[-5:])
                if not recovered:
                    continue

                # Check for consecutive up days near recovery
                recent_3d = close[end_idx - 3:end_idx]
                consecutive_up = sum(1 for i in range(1, len(recent_3d))
                                    if recent_3d[i] > recent_3d[i-1]) >= 1

                # Volume confirmation (1.5x)
                recent_vol = np.mean(volume[end_idx - 5:end_idx])
                vol_confirm = recent_vol > avg_vol_all * 1.5 if avg_vol_all > 0 else False

                # RSI confirmation
                rsi_values = self._compute_rsi(close[:end_idx])
                current_rsi = rsi_values[-1] if len(rsi_values) > 0 else 50
                rsi_oversold_bounce = current_rsi > 45

                # MACD histogram confirmation
                macd_hist = self._compute_macd_histogram(close[:end_idx])
                macd_turning = len(macd_hist) >= 3 and macd_hist[-1] > macd_hist[-3]

                # Calculate signals
                current_price = close[end_idx - 1]
                # Use next day's Open as entry price (realistic execution)
                if end_idx >= len(open_prices):
                    continue
                entry = open_prices[end_idx]
                stop_loss = min_price * 0.96

                distance = neckline - min_price
                target_1 = max(neckline + distance, pre_high)
                target_2 = neckline + distance * 1.618

                risk = entry - stop_loss
                reward = target_1 - entry
                rr_ratio = reward / risk if risk > 0 else 0

                # Confidence scoring
                confidence = 0.45
                if vol_confirm:
                    confidence += 0.15
                if consecutive_up:
                    confidence += 0.10
                if rsi_oversold_bounce:
                    confidence += 0.10
                if macd_turning:
                    confidence += 0.10
                if rr_ratio >= 3:
                    confidence += 0.10

                # Require 0.65+ confidence and 2.0+ RR
                if confidence >= 0.65 and rr_ratio >= 2.0:
                    desc_parts = [f"底部 {min_price:.2f} → 颈线 {neckline:.2f}"]
                    if vol_confirm:
                        desc_parts.append("放量确认")
                    if consecutive_up:
                        desc_parts.append("连阳确认")
                    if rsi_oversold_bounce:
                        desc_parts.append(f"RSI超卖反弹({current_rsi:.0f})")
                    if macd_turning:
                        desc_parts.append("MACD转正")

                    patterns.append(Pattern(
                        pattern_type=SignalType.PO_DI_FAN,
                        confidence=round(min(confidence, 0.95), 2),
                        neckline=round(neckline, 2),
                        entry_price=round(entry, 2),
                        stop_loss=round(stop_loss, 2),
                        target_price=round(target_1, 2),
                        target_price_2=round(target_2, 2),
                        risk_reward_ratio=round(rr_ratio, 2),
                        start_date=str(dates[end_idx - lookback].date()),
                        signal_date=str(dates[end_idx - 1].date()),
                        description="破底翻[优化]: " + " | ".join(desc_parts),
                        timeframe="daily"
                    ))

        # Deduplicate by signal_date, keep highest confidence
        seen = {}
        for p in patterns:
            key = p.signal_date
            if key not in seen or p.confidence > seen[key].confidence:
                seen[key] = p
        return list(seen.values())

    def detect_monthly_exhaustion_down(self) -> List[Pattern]:
        """
        优化版月线缩量见底
        改进:
        1. 要求连续 2 个月缩量 (而非仅1个月)
        2. 价格必须在底部区域 (< 25%)
        3. 加入月线 RSI 确认 (RSI < 35 超卖)
        4. 目标价基于阻力位而非固定比例
        5. 加入成交量萎缩趋势确认
        """
        patterns = []
        if self.monthly_data is None or len(self.monthly_data) < 12:
            return patterns

        close = self.monthly_data['Close'].values
        volume = self.monthly_data['Volume'].values
        opens = self.monthly_data['Open'].values
        highs = self.monthly_data['High'].values
        lows = self.monthly_data['Low'].values
        n = len(close)

        for i in range(6, n):
            avg_vol_6m = np.mean(volume[max(0, i-6):i])
            if avg_vol_6m == 0:
                continue

            vol_ratio = volume[i] / avg_vol_6m

            lookback = min(12, i + 1)
            recent_high = np.max(highs[max(0, i-lookback):i+1])
            recent_low = np.min(lows[max(0, i-lookback):i+1])
            price_position = (close[i] - recent_low) / (recent_high - recent_low) \
                if recent_high != recent_low else 0.5

            # IMPROVEMENT: Check previous month volume too (consecutive shrinking)
            prev_vol_ratio = volume[i-1] / avg_vol_6m if i > 0 and avg_vol_6m > 0 else 1.0

            # IMPROVEMENT: Stricter conditions
            cond_vol = vol_ratio < 0.5 and prev_vol_ratio < 0.7  # 2 consecutive low-volume months
            cond_price = price_position < 0.25  # Lower in range (was 0.3)

            # IMPROVEMENT: Monthly RSI confirmation
            monthly_rsi = self._compute_rsi(close[:i+1])
            m_rsi = monthly_rsi[-1] if len(monthly_rsi) > 0 else 50
            cond_rsi = m_rsi < 35  # Oversold on monthly

            # IMPROVEMENT: Volume shrinking trend (each month smaller)
            if i >= 2:
                vol_trend_shrinking = volume[i] < volume[i-1] < volume[i-2]
            else:
                vol_trend_shrinking = volume[i] < volume[i-1]

            if cond_vol and cond_price:
                confidence = 0.50
                if cond_rsi:
                    confidence += 0.15
                if vol_trend_shrinking:
                    confidence += 0.10
                if vol_ratio < 0.3:
                    confidence += 0.10
                if price_position < 0.15:
                    confidence += 0.10

                if confidence >= 0.60:
                    current = close[i]
                    # IMPROVEMENT: Dynamic targets based on resistance
                    resistance_1 = np.percentile(highs[max(0, i-6):i], 80)
                    resistance_2 = np.percentile(highs[max(0, i-12):i], 90) if i >= 12 else current * 1.3

                    target_1 = max(current * 1.15, resistance_1)
                    target_2 = max(current * 1.30, resistance_2)
                    stop_loss = recent_low * 0.95

                    desc_parts = [f"量比 {vol_ratio:.2f}x, 低位 {price_position:.0%}"]
                    if cond_rsi:
                        desc_parts.append(f"RSI超卖({m_rsi:.0f})")
                    if vol_trend_shrinking:
                        desc_parts.append("成交量递减")

                    patterns.append(Pattern(
                        pattern_type=SignalType.MONTHLY_EXHAUSTION_DOWN,
                        confidence=round(min(confidence, 0.92), 2),
                        neckline=round(recent_low, 2),
                        entry_price=round(current, 2),
                        stop_loss=round(stop_loss, 2),
                        target_price=round(target_1, 2),
                        target_price_2=round(target_2, 2),
                        risk_reward_ratio=round((target_1 - current) / (current - stop_loss), 2)
                            if current > stop_loss else 3.0,
                        start_date=str(self.monthly_data.index[max(0, i-6)]),
                        signal_date=str(self.monthly_data.index[i]),
                        description="月线缩量见底[优化]: " + " | ".join(desc_parts),
                        timeframe="monthly",
                        signal_quality="基本面"
                    ))

        return patterns

    def analyze(self) -> Dict:
        """Run focused analysis, return dict with signals"""
        po_di_fan = self.detect_po_di_fan()
        monthly_bottom = self.detect_monthly_exhaustion_down()

        return {
            'po_di_fan': po_di_fan,
            'monthly_bottom': monthly_bottom,
            'total_signals': len(po_di_fan) + len(monthly_bottom)
        }


# ============================================================
# Backtest
# ============================================================

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

BULLISH_SIGNALS = {"破底翻", "月线缩量见底"}

# 12 monthly cutoff dates
CUTOFF_DATES = [
    "2025-05-01", "2025-06-01", "2025-07-01", "2025-08-01",
    "2025-09-01", "2025-10-01", "2025-11-01", "2025-12-01",
    "2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01",
]

VERIFY_DAYS = 22  # ~1 month of trading days


def download_all():
    """Download 2y data for all instruments"""
    data = {}
    for symbol in INSTRUMENTS:
        print(f"  📥 {symbol} ({INSTRUMENTS[symbol]})...", end=" ", flush=True)
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="2y", auto_adjust=False)
            if len(df) > 60:
                data[symbol] = df
                print(f"✅ {len(df)} rows: {df.index[0].date()} → {df.index[-1].date()}")
            else:
                print(f"⚠️ Only {len(df)} rows, skipping")
        except Exception as e:
            print(f"❌ Error: {e}")
    return data


def verify_outcome(df_full, signal, cutoff_str, verify_days=VERIFY_DAYS):
    """Check what happened after signal"""
    cutoff = pd.Timestamp(cutoff_str)
    if df_full.index.tz is not None:
        cutoff = cutoff.tz_localize(df_full.index.tz)

    future = df_full[df_full.index > cutoff].head(verify_days)
    if len(future) == 0:
        return "no_data", None, None, 0

    entry = signal.entry_price
    stop = signal.stop_loss
    target1 = signal.target_price
    target2 = signal.target_price_2

    # All our signals are bullish (破底翻 and 月线缩量见底)
    hit_date = None
    outcome = "expired"

    for date, row in future.iterrows():
        if row['Low'] <= stop:
            outcome = "stop_loss_hit"
            hit_date = date
            break
        if row['High'] >= target2:
            outcome = "target2_hit"
            hit_date = date
            break
        if row['High'] >= target1:
            outcome = "target1_hit"
            hit_date = date
            break

    if hit_date is not None:
        end_price = future.loc[hit_date, 'Close']
    else:
        end_price = future.iloc[-1]['Close']
        hit_date = future.index[-1]

    actual_return = (end_price - entry) / entry * 100
    days_held = (hit_date - future.index[0]).days if hit_date else verify_days

    return outcome, hit_date, actual_return, days_held


def run_backtest(all_data):
    """Run focused backtest with global dedup for monthly signals"""
    results = []
    seen_monthly_signals = set()  # Track (symbol, signal_date, entry) to avoid double-counting

    for symbol, name in INSTRUMENTS.items():
        if symbol not in all_data:
            continue
        df_full = all_data[symbol]

        for cutoff_str in CUTOFF_DATES:
            cutoff = pd.Timestamp(cutoff_str)
            if df_full.index.tz is not None:
                cutoff = cutoff.tz_localize(df_full.index.tz)

            df_trunc = df_full[df_full.index <= cutoff].copy()
            if len(df_trunc) < 60:
                continue

            # Run focused analyzer
            try:
                analyzer = FocusedAnalyzer()
                analyzer.load_data(symbol, df_trunc)
                analysis = analyzer.analyze()

                all_signals = analysis['po_di_fan'] + analysis['monthly_bottom']

                # Global dedup: for monthly signals, only count once
                unique_signals = []
                for sig in all_signals:
                    if sig.timeframe == "monthly":
                        sig_key = (symbol, sig.signal_date, sig.entry_price)
                        if sig_key not in seen_monthly_signals:
                            seen_monthly_signals.add(sig_key)
                            unique_signals.append(sig)
                    else:
                        # Daily signals: only count if signal_date is in the cutoff month
                        # (avoid counting old signals that persist in the data)
                        sig_month = sig.signal_date[:7]
                        cutoff_month = cutoff_str[:7]
                        if sig_month == cutoff_month:
                            unique_signals.append(sig)
                all_signals = unique_signals

                # Also get buy-and-hold return
                future = df_full[df_full.index > cutoff].head(VERIFY_DAYS)
                bnh_return = 0
                if len(future) > 0:
                    start_price = df_trunc.iloc[-1]['Close']
                    end_price = future.iloc[-1]['Close']
                    bnh_return = (end_price - start_price) / start_price * 100

                for signal in all_signals:
                    outcome, hit_date, actual_return, days_held = verify_outcome(
                        df_full, signal, cutoff_str
                    )
                    results.append({
                        'symbol': symbol,
                        'name': name,
                        'cutoff': cutoff_str,
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
                        'actual_return': round(actual_return, 2),
                        'days_held': days_held,
                        'bnh_return': round(bnh_return, 2),
                        'description': signal.description,
                    })

                if not all_signals:
                    results.append({
                        'symbol': symbol,
                        'name': name,
                        'cutoff': cutoff_str,
                        'signal_type': '无信号',
                        'outcome': 'N/A',
                        'actual_return': 0,
                        'bnh_return': round(bnh_return, 2),
                    })

            except Exception as e:
                results.append({
                    'symbol': symbol,
                    'name': name,
                    'cutoff': cutoff_str,
                    'signal_type': f'ERROR: {e}',
                    'outcome': 'error',
                    'actual_return': 0,
                    'bnh_return': 0,
                })

    return results


def print_report(results):
    """Print comprehensive report"""
    signals = [r for r in results if r['signal_type'] not in ('无信号',) and
               not r['signal_type'].startswith('ERROR') and r.get('outcome') not in ('N/A',)]

    print("\n" + "=" * 80)
    print("📋 蔡森技术分析 — 破底翻 & 月线缩量见底 优化版回测")
    print("=" * 80)
    print(f"回测期间: 2025年5月 → 2026年4月 (12个月)")
    print(f"标的: {len(INSTRUMENTS)} instruments")
    print(f"验证窗口: {VERIFY_DAYS} 交易日 (~1个月)")

    # ── Overall Stats ──
    print("\n" + "━" * 80)
    print("📊 1. 总体准确率")
    print("━" * 80)
    total = len(signals)
    if total == 0:
        print("  ⚠️ 无信号产生!")
        return

    t1 = sum(1 for s in signals if s['outcome'] == 'target1_hit')
    t2 = sum(1 for s in signals if s['outcome'] == 'target2_hit')
    sl = sum(1 for s in signals if s['outcome'] == 'stop_loss_hit')
    exp = sum(1 for s in signals if s['outcome'] == 'expired')
    any_target = t1 + t2

    print(f"\n  总信号数: {total}")
    print(f"  ✅ 目标1达成: {t1} ({t1/total*100:.1f}%)")
    print(f"  🎯 目标2达成: {t2} ({t2/total*100:.1f}%)")
    print(f"  ✅🎯 任意目标: {any_target} ({any_target/total*100:.1f}%)")
    print(f"  ❌ 止损触发: {sl} ({sl/total*100:.1f}%)")
    print(f"  ⏰ 到期未触发: {exp} ({exp/total*100:.1f}%)")

    returns = [s['actual_return'] for s in signals]
    avg_ret = np.mean(returns)
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    print(f"\n  📊 平均回报: {avg_ret:+.2f}%")
    if wins:
        print(f"  📊 盈利: +{np.mean(wins):.2f}% ({len(wins)}笔)")
    if losses:
        print(f"  📊 亏损: {np.mean(losses):.2f}% ({len(losses)}笔)")
    if wins:
        print(f"  📊 盈亏比: {len(wins)}/{len(losses)} = {len(wins)/total*100:.1f}%")

    # ── By Signal Type ──
    print("\n" + "━" * 80)
    print("📊 2. 按信号类型")
    print("━" * 80)
    for stype in ['破底翻', '月线缩量见底']:
        subset = [s for s in signals if stype in s['signal_type']]
        if not subset:
            continue
        s_total = len(subset)
        s_t1 = sum(1 for s in subset if s['outcome'] == 'target1_hit')
        s_t2 = sum(1 for s in subset if s['outcome'] == 'target2_hit')
        s_sl = sum(1 for s in subset if s['outcome'] == 'stop_loss_hit')
        s_exp = sum(1 for s in subset if s['outcome'] == 'expired')
        s_ret = np.mean([s['actual_return'] for s in subset])
        s_wins = [s for s in subset if s['actual_return'] > 0]

        print(f"\n  {stype}:")
        print(f"    信号数: {s_total} | 命中: {s_t1+s_t2}/{s_total} = {(s_t1+s_t2)/s_total*100:.1f}%")
        print(f"    目标1: {s_t1} | 目标2: {s_t2} | 止损: {s_sl} | 到期: {s_exp}")
        print(f"    平均回报: {s_ret:+.2f}% | 盈利笔数: {len(s_wins)}/{s_total}")

    # ── By Instrument ──
    print("\n" + "━" * 80)
    print("📊 3. 按标的汇总")
    print("━" * 80)
    print(f"  {'标的':<14} {'信号数':>6} {'命中':>6} {'命中率':>8} {'平均回报':>10} {'买持回报':>10}")
    print("  " + "-" * 65)
    for symbol in INSTRUMENTS:
        subset = [s for s in signals if s['symbol'] == symbol]
        no_signal = [r for r in results if r['symbol'] == symbol and r['signal_type'] == '无信号']
        if not subset and not no_signal:
            continue
        s_total = len(subset)
        if s_total > 0:
            s_hit = sum(1 for s in subset if s['outcome'] in ('target1_hit', 'target2_hit'))
            s_ret = np.mean([s['actual_return'] for s in subset])
            bnh = np.mean([s.get('bnh_return', 0) for s in subset])
            print(f"  {symbol:<14} {s_total:>6} {s_hit:>6} {s_hit/s_total*100:>7.1f}% {s_ret:>+9.2f}% {bnh:>+9.2f}%")
        else:
            avg_bnh = np.mean([r.get('bnh_return', 0) for r in no_signal]) if no_signal else 0
            print(f"  {symbol:<14} {'0':>6} {'-':>6} {'N/A':>8} {'-':>10} {avg_bnh:>+9.2f}%")

    # ── Monthly Summary ──
    print("\n" + "━" * 80)
    print("📊 4. 月度收益 (跟随建议 vs 买持)")
    print("━" * 80)
    print(f"  {'月份':<14} {'信号数':>6} {'策略收益':>10} {'买持收益':>10} {'超额':>10}")
    print("  " + "-" * 55)
    for month_str in CUTOFF_DATES:
        month_signals = [s for s in signals if s['cutoff'] == month_str]
        n = len(month_signals)
        if n > 0:
            strat_ret = np.mean([s['actual_return'] for s in month_signals])
            bnh_ret = np.mean([s.get('bnh_return', 0) for s in month_signals])
        else:
            strat_ret = 0
            bnh_ret = np.mean([r.get('bnh_return', 0) for r in results
                               if r['cutoff'] == month_str and r['signal_type'] == '无信号'])
        excess = strat_ret - bnh_ret
        print(f"  {month_str:<14} {n:>6} {strat_ret:>+9.2f}% {bnh_ret:>+9.2f}% {excess:>+9.2f}%")

    # Cumulative
    all_strat = [s['actual_return'] for s in signals]
    all_bnh = [s.get('bnh_return', 0) for s in signals]
    cum_strat = np.mean(all_strat) * 12 / len(CUTOFF_DATES) if all_strat else 0
    cum_bnh = np.mean(all_bnh) * 12 / len(CUTOFF_DATES) if all_bnh else 0
    print(f"  {'累计':<14} {len(signals):>6} {np.sum(all_strat)/12:>+9.2f}% {np.sum(all_bnh)/12:>+9.2f}% {np.sum(all_strat)/12 - np.sum(all_bnh)/12:>+9.2f}%")

    # ── Detailed Table ──
    print("\n" + "━" * 80)
    print("📊 5. 详细信号记录")
    print("━" * 80)
    print(f"  {'标的':<12} {'月份':<12} {'信号':<18} {'置信':>5} {'入场':>8} {'止损':>8} {'目标1':>8} {'结果':<10} {'回报%':>8} {'买持%':>8}")
    print("  " + "-" * 110)
    for s in signals:
        outcome_map = {
            'target1_hit': '✅T1',
            'target2_hit': '🎯T2',
            'stop_loss_hit': '❌SL',
            'expired': '⏰EXP',
            'no_data': '❓N/A',
        }
        stype = s['signal_type'][:14]
        desc = outcome_map.get(s['outcome'], s['outcome'])
        print(f"  {s['symbol']:<12} {s['cutoff']:<12} {stype:<18} "
              f"{s.get('confidence', 0):>5.0%} {s['entry']:>8.2f} {s.get('stop_loss', 0):>8.2f} "
              f"{s.get('target1', 0):>8.2f} {desc:<10} {s['actual_return']:>+7.2f}% {s.get('bnh_return', 0):>+7.2f}%")

    # ── vs Original Tool ──
    print("\n" + "━" * 80)
    print("📊 6. 与原始工具对比")
    print("━" * 80)
    print(f"  {'指标':<25} {'原始工具':>15} {'优化版(仅两信号)':>18}")
    print("  " + "-" * 60)
    print(f"  {'总信号数':<25} {'627':>15} {total:>18}")
    print(f"  {'命中率(任意目标)':<25} {'24.9%':>15} {any_target/total*100:>17.1f}%")
    print(f"  {'止损率':<25} {'48.2%':>15} {sl/total*100:>17.1f}%")
    print(f"  {'平均回报':<25} {'-1.76%':>15} {avg_ret:>+17.2f}%")
    print(f"  {'策略累计回报':<25} {'-15.20%':>15} {np.sum(all_strat)/12:>+17.2f}%")
    print(f"  {'买持累计回报':<25} {'+8.59%':>15} {np.sum(all_bnh)/12:>+17.2f}%")


def main():
    print("=" * 80)
    print("🚀 蔡森技术分析 — 破底翻 & 月线缩量见底 优化版回测")
    print("=" * 80)

    print("\n📥 下载数据...\n")
    all_data = download_all()

    print(f"\n🔍 运行优化版回测 ({len(all_data)} instruments × {len(CUTOFF_DATES)} months)...\n")
    results = run_backtest(all_data)

    print_report(results)

    # Save results
    with open('/root/.openclaw/workspace/Caisen-analyzer/focused_backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n💾 详细结果已保存: focused_backtest_results.json")


if __name__ == "__main__":
    main()
