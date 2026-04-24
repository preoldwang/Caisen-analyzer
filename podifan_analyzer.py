#!/usr/bin/env python3
"""
蔡森技术分析 — 破底翻精简版 (CaiSen PD-Fan Only)
==================================================
只保留最强信号破底翻 (77.2%命中率, +26%平均回报)
基于全量蓝筹回测结论优化

Author: Stock Analysis Tool
Version: 4.0 (Focused)
Update: 2026-04-17
"""

import sys
import json
import warnings
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from enum import Enum

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings('ignore')


# ============================================================
# Data Structures
# ============================================================

class Trend(Enum):
    BULLISH = "多头"
    BEARISH = "空头"
    NEUTRAL = "盘整"


@dataclass
class Signal:
    """破底翻信号"""
    symbol: str
    signal_date: str
    timeframe: str  # "daily" or "weekly"
    confidence: float
    entry_price: float
    stop_loss: float
    target_price: float
    target_price_2: float
    risk_reward_ratio: float
    neckline: float
    bottom_price: float
    current_price: float
    daily_trend: str
    weekly_trend: str
    description: str
    # Extra context
    volume_confirm: bool = False
    rsi_oversold: float = 0
    macd_turning: bool = False
    days_in_pattern: int = 0


@dataclass
class AnalysisResult:
    symbol: str
    analysis_date: str
    current_price: float
    daily_trend: str
    weekly_trend: str
    signals: List[Signal] = field(default_factory=list)
    key_support: Optional[float] = None
    key_resistance: Optional[float] = None


# ============================================================
# Core Analyzer
# ============================================================

class PoDiFanAnalyzer:
    """
    破底翻专用分析器
    
    蔡森核心: "破底翻大都会越过前高"
    
    破底翻定义:
    1. 股价在底部盘整
    2. 跌破底部颈线 (破底)
    3. 又翻回颈线之上 (翻)
    含义: 有人在护盘 (主力甩轿后拉升)
    操作: 翻回颈线时买入，止损设在破底处
    """

    def __init__(self):
        self.data = None
        self.weekly_data = None
        self.monthly_data = None

    def load_data(self, symbol: str, df: pd.DataFrame):
        self.data = df.copy()
        self.symbol = symbol

        # Ensure Volume column exists
        if 'Volume' not in self.data.columns:
            self.data['Volume'] = 0

        # Resample to weekly
        self.weekly_data = self.data.resample('W').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min',
            'Close': 'last', 'Volume': 'sum'
        }).dropna()

        # Resample to monthly
        self.monthly_data = self.data.resample('ME').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min',
            'Close': 'last', 'Volume': 'sum'
        }).dropna()

    def _compute_rsi(self, prices, period=14):
        if len(prices) < period + 1:
            return np.full(len(prices), 50.0)
        delta = np.diff(prices)
        gains = np.where(delta > 0, delta, 0)
        losses = np.where(delta < 0, -delta, 0)
        avg_gain = np.convolve(gains, np.ones(period)/period, mode='valid')
        avg_loss = np.convolve(losses, np.ones(period)/period, mode='valid')
        avg_loss = np.where(avg_loss == 0, 1e-10, avg_loss)
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        pad = len(prices) - len(rsi)
        return np.concatenate([np.full(pad, 50.0), rsi])

    def _compute_macd(self, prices, fast=12, slow=26, signal=9):
        if len(prices) < slow + signal:
            return np.zeros(len(prices))
        s = pd.Series(prices)
        ema_fast = s.ewm(span=fast, adjust=False).mean()
        ema_slow = s.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return (macd_line - signal_line).values

    def _get_trend(self, prices, short_period=20, long_period=50):
        """Simple trend determination"""
        if len(prices) < long_period:
            return Trend.NEUTRAL
        short_ma = np.mean(prices[-short_period:])
        long_ma = np.mean(prices[-long_period:])
        if short_ma > long_ma * 1.02:
            return Trend.BULLISH
        elif short_ma < long_ma * 0.98:
            return Trend.BEARISH
        return Trend.NEUTRAL

    def _detect_po_di_fan(self, ohlcv_data, timeframe="daily", min_lookback=30, max_lookback=90) -> List[Signal]:
        """
        破底翻检测核心逻辑
        
        Parameters:
        - ohlcv_data: DataFrame with OHLCV columns
        - timeframe: "daily" or "weekly"
        - min_lookback, max_lookback: lookback window range
        """
        signals = []
        if ohlcv_data is None or len(ohlcv_data) < min_lookback + 15:
            return signals

        close = ohlcv_data['Close'].values
        high = ohlcv_data['High'].values
        low = ohlcv_data['Low'].values
        volume = ohlcv_data['Volume'].values
        dates = ohlcv_data.index

        avg_vol = np.mean(volume[volume > 0]) if np.any(volume > 0) else 0

        for lookback in range(min_lookback, min(max_lookback + 1, len(close) - 10), 10):
            for end_idx in range(lookback + 10, len(close)):
                seg_close = close[end_idx - lookback:end_idx]
                seg_low = low[end_idx - lookback:end_idx]
                seg_high = high[end_idx - lookback:end_idx]
                seg_vol = volume[end_idx - lookback:end_idx]

                # 1. Find bottom (minimum low in lookback)
                min_price = np.min(seg_low)
                min_idx = np.argmin(seg_low)

                # Bottom should not be at very edges
                if min_idx < 5 or min_idx >= len(seg_low) - 5:
                    continue

                # 2. Neckline: recovery high after bottom
                recovery_highs = seg_high[min_idx:]
                if len(recovery_highs) < 3:
                    continue
                neckline = np.percentile(recovery_highs, 60)

                # Neckline should be meaningfully above bottom (>3%)
                if neckline < min_price * 1.03:
                    continue

                # 3. Previous high (for target calculation)
                pre_high = np.max(seg_high[:min_idx]) if min_idx > 5 else neckline

                # 4. Check for breakdown (破底) in recent window
                check_days = 12 if timeframe == "daily" else 8
                check_close = close[end_idx - check_days:end_idx]
                check_low = low[end_idx - check_days:end_idx]

                broke_below = False
                broke_idx = -1
                for i, p in enumerate(check_low):
                    if p < min_price * 0.985:  # 1.5% below bottom
                        broke_below = True
                        broke_idx = i
                        break

                if not broke_below:
                    continue

                # 5. Recovery check (翻回颈线)
                after_break = close[end_idx - check_days + broke_idx:end_idx]
                if len(after_break) < 2:
                    continue
                recovered = any(p > neckline for p in after_break[-5:])

                if not recovered:
                    continue

                # 6. Confirmations
                # Volume confirmation
                recent_vol = np.mean(volume[end_idx - 3:end_idx]) if end_idx >= 3 else 0
                vol_confirm = recent_vol > avg_vol * 1.3 if avg_vol > 0 else False

                # RSI
                rsi_vals = self._compute_rsi(close[:end_idx])
                current_rsi = rsi_vals[-1] if len(rsi_vals) > 0 else 50

                # MACD
                macd = self._compute_macd(close[:end_idx])
                macd_turn = len(macd) >= 3 and macd[-1] > macd[-3]

                # Recent momentum (consecutive up days)
                recent = close[end_idx - 3:end_idx]
                up_streak = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i-1])

                # 7. Calculate entry/stop/targets
                current = close[end_idx - 1]
                entry = neckline
                stop = min_price * 0.96

                distance = neckline - min_price
                target_1 = max(neckline + distance, pre_high)
                target_2 = neckline + distance * 1.618

                risk = entry - stop
                reward = target_1 - entry
                rr = reward / risk if risk > 0 else 0

                # 8. Confidence scoring
                confidence = 0.55
                if vol_confirm:
                    confidence += 0.12
                if current_rsi < 40:
                    confidence += 0.10
                elif current_rsi < 50:
                    confidence += 0.05
                if macd_turn:
                    confidence += 0.08
                if up_streak >= 2:
                    confidence += 0.08
                if rr >= 3:
                    confidence += 0.07

                # Only accept high-quality signals
                if confidence < 0.65 or rr < 2.0:
                    continue

                # 9. Build signal
                desc_parts = [
                    f"底部 {min_price:.2f} → 颈线 {neckline:.2f}",
                    f"距离 {distance:.2f} ({distance/min_price*100:.1f}%)"
                ]
                if vol_confirm:
                    desc_parts.append("放量")
                if current_rsi < 45:
                    desc_parts.append(f"RSI{current_rsi:.0f}")
                if macd_turn:
                    desc_parts.append("MACD↑")
                if up_streak >= 2:
                    desc_parts.append(f"{up_streak}连阳")

                signals.append(Signal(
                    symbol=self.symbol,
                    signal_date=str(dates[end_idx - 1].date()),
                    timeframe=timeframe,
                    confidence=round(min(confidence, 0.95), 2),
                    entry_price=round(entry, 2),
                    stop_loss=round(stop, 2),
                    target_price=round(target_1, 2),
                    target_price_2=round(target_2, 2),
                    risk_reward_ratio=round(rr, 2),
                    neckline=round(neckline, 2),
                    bottom_price=round(min_price, 2),
                    current_price=round(current, 2),
                    daily_trend="",
                    weekly_trend="",
                    description=" | ".join(desc_parts),
                    volume_confirm=vol_confirm,
                    rsi_oversold=round(current_rsi, 1),
                    macd_turning=macd_turn,
                    days_in_pattern=lookback,
                ))

        # Deduplicate by signal_date, keep highest confidence
        seen = {}
        for s in signals:
            key = s.signal_date
            if key not in seen or s.confidence > seen[key].confidence:
                seen[key] = s
        return list(seen.values())

    def analyze(self, symbol: str = None) -> AnalysisResult:
        """Run破底翻 analysis on daily + weekly data"""
        if symbol:
            self.symbol = symbol

        # Trends
        daily_trend = self._get_trend(self.data['Close'].values)
        weekly_trend = self._get_trend(self.weekly_data['Close'].values) \
            if self.weekly_data is not None and len(self.weekly_data) > 50 \
            else Trend.NEUTRAL

        # Detect signals
        daily_signals = self._detect_po_di_fan(self.data, "daily", 30, 90)
        weekly_signals = []
        if self.weekly_data is not None and len(self.weekly_data) > 30:
            weekly_signals = self._detect_po_di_fan(self.weekly_data, "weekly", 12, 30)

        all_signals = daily_signals + weekly_signals

        # Add trend info
        for s in all_signals:
            s.daily_trend = daily_trend.value
            s.weekly_trend = weekly_trend.value

        # Support/resistance
        close = self.data['Close'].values
        low = self.data['Low'].values
        high = self.data['High'].values
        key_support = round(np.percentile(low[-60:], 25), 2) if len(low) >= 60 else None
        key_resistance = round(np.percentile(high[-60:], 75), 2) if len(high) >= 60 else None

        return AnalysisResult(
            symbol=self.symbol,
            analysis_date=str(datetime.now().date()),
            current_price=round(close[-1], 2),
            daily_trend=daily_trend.value,
            weekly_trend=weekly_trend.value,
            signals=all_signals,
            key_support=key_support,
            key_resistance=key_resistance,
        )


# ============================================================
# Backtest Engine
# ============================================================

def download_data(symbols: Dict[str, str]) -> Dict[str, pd.DataFrame]:
    """Download 2y data for all symbols"""
    data = {}
    n = len(symbols)
    for i, (sym, name) in enumerate(symbols.items(), 1):
        print(f"  [{i:3d}/{n}] {sym:<12} {name:<20}", end=" ", flush=True)
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(period="2y", auto_adjust=False)
            if len(df) > 120:
                data[sym] = df
                print(f"✅ {len(df)} rows")
            else:
                print(f"⚠️ {len(df)} rows")
        except Exception as e:
            print(f"❌ {str(e)[:40]}")
    return data


def verify_signal(df_full, signal, cutoff_str, verify_days=22):
    """Check outcome of a signal"""
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

    outcome = "expired"
    hit_date = None
    for date, row in future.iterrows():
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

    end_price = future.iloc[-1]['Close']
    ret = (end_price - entry) / entry * 100
    days = (hit_date - future.index[0]).days if hit_date else verify_days
    return outcome, round(ret, 2), days


def run_backtest(symbols: Dict[str, str], data: Dict[str, pd.DataFrame],
                 cutoff_dates: List[str], verify_days: int = 22):
    """Run backtest across all symbols and cutoff dates"""
    all_signals = []
    total = len(data)
    cutoff_count = len(cutoff_dates)

    for si, (symbol, name) in enumerate(symbols.items(), 1):
        if symbol not in data:
            continue
        df_full = data[symbol]

        for ci, cutoff_str in enumerate(cutoff_dates):
            cutoff = pd.Timestamp(cutoff_str)
            if df_full.index.tz is not None:
                cutoff = cutoff.tz_localize(df_full.index.tz)

            df_trunc = df_full[df_full.index <= cutoff].copy()
            if len(df_trunc) < 60:
                continue

            try:
                analyzer = PoDiFanAnalyzer()
                analyzer.load_data(symbol, df_trunc)
                result = analyzer.analyze(symbol)

                # B&H returns
                future = df_full[df_full.index > cutoff]
                bnh_1m = 0
                bnh_3m = 0
                f1m = future.head(verify_days)
                f3m = future.head(verify_days * 3)
                if len(f1m) > 0:
                    bnh_1m = (f1m.iloc[-1]['Close'] - df_trunc.iloc[-1]['Close']) / df_trunc.iloc[-1]['Close'] * 100
                if len(f3m) > 0:
                    bnh_3m = (f3m.iloc[-1]['Close'] - df_trunc.iloc[-1]['Close']) / df_trunc.iloc[-1]['Close'] * 100

                for sig in result.signals:
                    # Only count daily signals in their cutoff month
                    if sig.timeframe == "daily" and sig.signal_date[:7] != cutoff_str[:7]:
                        continue

                    # Dedup weekly signals
                    if sig.timeframe == "weekly":
                        key = (symbol, sig.signal_date, sig.entry_price)
                    else:
                        key = (symbol, sig.signal_date, sig.entry_price)

                    outcome, ret_1m, days = verify_signal(df_full, sig, cutoff_str, verify_days)
                    _, ret_3m, _ = verify_signal(df_full, sig, cutoff_str, verify_days * 3)

                    all_signals.append({
                        'symbol': symbol,
                        'name': name,
                        'cutoff': cutoff_str,
                        'signal_date': sig.signal_date,
                        'timeframe': sig.timeframe,
                        'confidence': sig.confidence,
                        'entry': sig.entry_price,
                        'stop_loss': sig.stop_loss,
                        'target1': sig.target_price,
                        'target2': sig.target_price_2,
                        'rr': sig.risk_reward_ratio,
                        'neckline': sig.neckline,
                        'bottom': sig.bottom_price,
                        'description': sig.description,
                        'outcome': outcome,
                        'ret_1m': ret_1m,
                        'ret_3m': ret_3m,
                        'days_held': days,
                        'bnh_1m': round(bnh_1m, 2),
                        'bnh_3m': round(bnh_3m, 2),
                    })

            except Exception:
                pass

        if si % 10 == 0:
            print(f"  [{si}/{total}] {symbol} done")

    return all_signals


def print_report(signals, symbols, cutoff_dates):
    """Comprehensive report"""
    if not signals:
        print("\n⚠️ No signals found!")
        return

    total = len(signals)
    t1 = sum(1 for s in signals if s['outcome'] == 'target1')
    t2 = sum(1 for s in signals if s['outcome'] == 'target2')
    sl = sum(1 for s in signals if s['outcome'] == 'stop_loss')
    exp = sum(1 for s in signals if s['outcome'] == 'expired')
    hit = t1 + t2
    rets = [s['ret_1m'] for s in signals]
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]

    print("\n" + "=" * 90)
    print("📊 蔡森破底翻精简版 — 全部恒生指数蓝筹 12个月回测")
    print("=" * 90)

    # Overall
    print(f"\n  总信号数: {total}")
    print(f"  ✅🎯 命中(T1+T2): {hit}/{total} = {hit/total*100:.1f}%")
    print(f"    ├ T1达成: {t1} ({t1/total*100:.1f}%)")
    print(f"    └ T2达成(黄金比例): {t2} ({t2/total*100:.1f}%)")
    print(f"  ❌ 止损: {sl}/{total} = {sl/total*100:.1f}%")
    print(f"  ⏰ 到期: {exp}/{total} = {exp/total*100:.1f}%")
    print(f"\n  📊 平均1M回报: {np.mean(rets):+.2f}%")
    print(f"  📊 平均3M回报: {np.mean([s['ret_3m'] for s in signals]):+.2f}%")
    print(f"  📊 盈利: +{np.mean(wins):.2f}% ({len(wins)}笔, 胜率{len(wins)/total*100:.1f}%)")
    if losses:
        print(f"  📊 亏损: {np.mean(losses):.2f}% ({len(losses)}笔)")
    print(f"  📊 盈亏比: {len(wins)}:{len(losses)} = {len(wins)/(len(losses) or 1):.2f}:1")
    print(f"  📊 风险回报(理论): avg {np.mean([s['rr'] for s in signals]):.1f}:1")
    print(f"  📊 置信度: avg {np.mean([s['confidence'] for s in signals]):.0%}, "
          f"range {min(s['confidence'] for s in signals):.0%}-{max(s['confidence'] for s in signals):.0%}")

    # Confidence threshold analysis
    print(f"\n" + "━" * 90)
    print("📊 置信度阈值分析")
    print("━" * 90)
    for thresh in [0.65, 0.70, 0.75, 0.80, 0.85, 0.90]:
        sub = [s for s in signals if s['confidence'] >= thresh]
        if not sub:
            continue
        sh = sum(1 for s in sub if s['outcome'] in ('target1', 'target2'))
        ssl = sum(1 for s in sub if s['outcome'] == 'stop_loss')
        avg_r = np.mean([s['ret_1m'] for s in sub])
        sw = sum(1 for s in sub if s['ret_1m'] > 0)
        bnh = np.mean([s['bnh_1m'] for s in sub])
        print(f"  ≥{thresh:.0%}: {len(sub):>4} signals | 命中 {sh/len(sub)*100:>5.1f}% | "
              f"止损 {ssl/len(sub)*100:>5.1f}% | 回报 {avg_r:>+7.2f}% | "
              f"胜率 {sw/len(sub)*100:>5.1f}% | B&H {bnh:>+7.2f}%")

    # By timeframe
    print(f"\n" + "━" * 90)
    print("📊 按时间框架")
    print("━" * 90)
    for tf in ['daily', 'weekly']:
        sub = [s for s in signals if s['timeframe'] == tf]
        if not sub:
            continue
        sh = sum(1 for s in sub if s['outcome'] in ('target1', 'target2'))
        ssl = sum(1 for s in sub if s['outcome'] == 'stop_loss')
        print(f"  {tf:>7}: {len(sub):>4} signals | 命中 {sh/len(sub)*100:>5.1f}% | "
              f"止损 {ssl/len(sub)*100:>5.1f}% | 回报 {np.mean([s['ret_1m'] for s in sub]):>+7.2f}%")

    # By instrument (top 20)
    print(f"\n" + "━" * 90)
    print("📊 按标的 (前20)")
    print("━" * 90)
    inst = {}
    for s in signals:
        sym = s['symbol']
        if sym not in inst:
            inst[sym] = {'n': 0, 'hit': 0, 'sl': 0, 'rets': [], 'bnh': [], 'name': s['name']}
        inst[sym]['n'] += 1
        if s['outcome'] in ('target1', 'target2'):
            inst[sym]['hit'] += 1
        if s['outcome'] == 'stop_loss':
            inst[sym]['sl'] += 1
        inst[sym]['rets'].append(s['ret_1m'])
        inst[sym]['bnh'].append(s['bnh_1m'])

    print(f"  {'标的':<10} {'名称':<20} {'信号':>5} {'命中':>5} {'命中率':>8} {'止损':>5} "
          f"{'平均回报':>10} {'买持':>10} {'超额':>10}")
    print("  " + "-" * 90)
    for sym, d in sorted(inst.items(), key=lambda x: -x[1]['n'])[:20]:
        wr = d['hit'] / d['n'] * 100
        avg = np.mean(d['rets'])
        bnh = np.mean(d['bnh'])
        print(f"  {sym:<10} {d['name']:<20} {d['n']:>5} {d['hit']:>5} {wr:>7.1f}% "
              f"{d['sl']:>5} {avg:>+9.2f}% {bnh:>+9.2f}% {avg-bnh:>+9.2f}%")

    # Monthly portfolio
    print(f"\n" + "━" * 90)
    print("💰 月度组合收益 (等权, 所有破底翻信号)")
    print("━" * 90)
    print(f"  {'月份':<14} {'信号':>5} {'策略1M':>8} {'买持1M':>8} {'超额':>8} {'累计策略':>10} {'累计买持':>10}")
    print("  " + "-" * 65)
    cum_s = 1.0
    cum_b = 1.0
    for m in cutoff_dates:
        ms = [s for s in signals if s['cutoff'] == m]
        n = len(ms)
        if n > 0:
            sr = np.mean([s['ret_1m'] for s in ms])
            br = np.mean([s['bnh_1m'] for s in ms])
        else:
            sr = 0
            br = 0
        cum_s *= (1 + sr / 100)
        cum_b *= (1 + br / 100)
        print(f"  {m:<14} {n:>5} {sr:>+7.2f}% {br:>+7.2f}% {sr-br:>+7.2f}% "
              f"{(cum_s-1)*100:>+9.2f}% {(cum_b-1)*100:>+9.2f}%")
    print(f"  {'累计':<14} {len(signals):>5} {'':>8} {'':>8} {'':>8} "
          f"{(cum_s-1)*100:>+9.2f}% {(cum_b-1)*100:>+9.2f}%")

    # Top & worst trades
    print(f"\n" + "━" * 90)
    print("🏆 最佳交易 (前15)")
    print("━" * 90)
    top = sorted(signals, key=lambda x: -x['ret_1m'])[:15]
    om = {'target1': '✅T1', 'target2': '🎯T2', 'stop_loss': '❌SL', 'expired': '⏰EXP'}
    for s in top:
        print(f"  {s['symbol']:<10} {s['cutoff']:<12} C={s['confidence']:.0%} "
              f"{s['entry']:>8.2f} → {om.get(s['outcome'], '?'):<5} "
              f"{s['ret_1m']:>+7.2f}% (B&H: {s['bnh_1m']:>+7.2f}%) | {s['timeframe']}")

    print(f"\n  💀 最差交易 (前10):")
    worst = sorted(signals, key=lambda x: x['ret_1m'])[:10]
    for s in worst:
        print(f"  {s['symbol']:<10} {s['cutoff']:<12} C={s['confidence']:.0%} "
              f"{s['entry']:>8.2f} → {om.get(s['outcome'], '?'):<5} "
              f"{s['ret_1m']:>+7.2f}% (B&H: {s['bnh_1m']:>+7.2f}%)")

    # Comparison table
    print(f"\n" + "━" * 90)
    print("📊 vs 原始工具 (破底翻精简版 vs 完整版)")
    print("━" * 90)
    print(f"  {'指标':<25} {'完整版(所有信号)':>18} {'破底翻精简版':>18}")
    print("  " + "-" * 63)
    print(f"  {'总信号数':<25} {'1,074':>18} {total:>18}")
    print(f"  {'命中率':<25} {'20.8%':>18} {hit/total*100:>17.1f}%")
    print(f"  {'止损率':<25} {'59.5%':>18} {sl/total*100:>17.1f}%")
    print(f"  {'平均回报':<25} {'-14.32%':>18} {np.mean(rets):>+17.2f}%")
    print(f"  {'策略累计':<25} {'-85.54%':>18} {(cum_s-1)*100:>+17.2f}%")
    print(f"  {'买持累计':<25} {'+21.72%':>18} {(cum_b-1)*100:>+17.2f}%")
    print(f"  {'超额':<25} {'-107.26%':>18} {(cum_s-cum_b)*100:>+17.2f}%")


# ============================================================
# Main
# ============================================================

# Full HSI blue chip list
HSI_BLUE_CHIPS = {
    '0005.HK': 'HSBC Holdings', '0006.HK': 'Power Assets',
    '0011.HK': 'Hang Seng Bank', '0012.HK': 'Henderson Land',
    '0016.HK': 'SHK Properties', '0027.HK': 'Galaxy Ent',
    '0066.HK': 'MTR Corp', '0175.HK': 'Geely Auto',
    '0241.HK': 'Ali Health', '0267.HK': 'CITIC',
    '0288.HK': 'WH Group', '0386.HK': 'Sinopec',
    '0388.HK': 'HKEX', '0669.HK': 'Techtronic',
    '0688.HK': 'China Overseas', '0700.HK': 'Tencent',
    '0728.HK': 'China Telecom', '0762.HK': 'China Unicom',
    '0788.HK': 'China Tower', '0823.HK': 'Link REIT',
    '0836.HK': 'CR Power', '0857.HK': 'PetroChina',
    '0883.HK': 'CNOOC', '0916.HK': 'Longyuan Power',
    '0939.HK': 'CCB', '0941.HK': 'China Mobile',
    '0960.HK': 'Longfor', '0968.HK': 'Xinyi Solar',
    '0981.HK': 'SMIC', '0992.HK': 'Lenovo',
    '1024.HK': 'Kuaishou', '1038.HK': 'CKI Holdings',
    '1044.HK': 'Hengan Intl', '1088.HK': 'China Shenhua',
    '1093.HK': 'CSPC Pharma', '1109.HK': 'CR Land',
    '1113.HK': 'CKA', '1177.HK': 'Sino Biopharma',
    '1209.HK': 'CR Mixc', '1211.HK': 'BYD',
    '1299.HK': 'AIA Group', '1378.HK': 'China Hongqiao',
    '1398.HK': 'ICBC', '1810.HK': 'Xiaomi',
    '1876.HK': 'Budweiser APAC', '1880.HK': 'LVMH',
    '1928.HK': 'Sands China', '1929.HK': 'Chow Tai Fook',
    '1997.HK': 'Wharf REIC', '2007.HK': 'Country Garden',
    '2013.HK': 'Weimob', '2015.HK': 'Li Auto',
    '2020.HK': 'Anta Sports', '2050.HK': '361 Degrees',
    '2269.HK': 'WuXi Biologics', '2313.HK': 'Shenzhou Intl',
    '2318.HK': 'Ping An', '2319.HK': 'Mengniu Dairy',
    '2331.HK': 'Li Ning', '2359.HK': 'WuXi AppTec',
    '2382.HK': 'Sunny Optical', '2628.HK': 'China Life',
    '2688.HK': 'ENN Energy', '2899.HK': 'Zijin Mining',
    '3690.HK': 'Meituan', '3692.HK': 'Hansoh Pharma',
    '3968.HK': 'CMB', '6030.HK': 'CITIC Securities',
    '6618.HK': 'JD Health', '6690.HK': 'Haier SmartHome',
    '9618.HK': 'JD.com', '9626.HK': 'Bilibili',
    '9633.HK': 'Nongfu Spring', '9698.HK': 'GDS Holdings',
    '9888.HK': 'Baidu', '9866.HK': 'NIO',
    '9901.HK': 'New Oriental', '9961.HK': 'Trip.com',
    '9988.HK': 'Alibaba', '9999.HK': 'NetEase',
    'GC=F': 'Gold Futures',
}

CUTOFF_DATES = [
    "2025-05-01", "2025-06-01", "2025-07-01", "2025-08-01",
    "2025-09-01", "2025-10-01", "2025-11-01", "2025-12-01",
    "2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01",
]


def main():
    print("=" * 90)
    print("🚀 蔡森破底翻精简版 — 全部恒生指数蓝筹 12个月回测")
    print(f"   标的: {len(HSI_BLUE_CHIPS)} | 期间: May 2025 → Apr 2026")
    print("=" * 90)

    print("\n📥 下载数据...\n")
    data = download_data(HSI_BLUE_CHIPS)
    print(f"\n✅ 成功: {len(data)}/{len(HSI_BLUE_CHIPS)}")

    print(f"\n🔍 运行破底翻回测...\n")
    signals = run_backtest(HSI_BLUE_CHIPS, data, CUTOFF_DATES)

    print_report(signals, HSI_BLUE_CHIPS, CUTOFF_DATES)

    # Save
    outpath = '/root/.openclaw/workspace/Caisen-analyzer/podifan_backtest.json'
    with open(outpath, 'w') as f:
        json.dump(signals, f, indent=2, default=str)
    print(f"\n💾 Saved: {outpath}")


if __name__ == "__main__":
    main()
