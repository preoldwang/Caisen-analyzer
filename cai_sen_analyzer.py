#!/usr/bin/env python3
"""
蔡森技术分析工具 v2.0 (Cai Sen Technical Analysis Tool)
=======================================================
基于蔡森的投资方法论 (26年实战经验):
1. 只看量与价 (Volume & Price only)
2. 破底翻 - 做多信号 (Bottom Breakdown & Recovery - Long Signal)
3. 假突破 - 做空信号 (False Breakout - Short Signal)
4. 颈线识别与型态分析 (Neckline & Pattern Recognition)
5. 涨幅满足计算 (Price Target Calculation)
6. 严格止损 (Strict Stop-Loss)
7. 多时间框架分析 (Multi-timeframe: Daily + Weekly + Hourly)
8. 岛型反转 (Island Reversal)
9. 量先价行 (Volume Leads Price)
10. 支撑分级 (Support Levels: Short-term vs Long-term)

Author: Stock Analysis Tool
Version: 2.1
Update: 2026-04-13
  - 新增: V型反轉检测 (V-Reversal Detection with Probability Scoring)
  - 新增: 量價背離检测 (Volume-Price Divergence Detector)
  - 新增: 基本面 vs 呬爛面过滤器 (Real vs Bluff Signal Filter)
  - 基于蔡森第462集《經典技術分析》20260407
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

warnings.filterwarnings('ignore')


# ============================================================
# Data Structures
# ============================================================

class SignalType(Enum):
    PO_DI_FAN = "破底翻"           # Bottom Breakdown & Recovery (Long)
    JIA_TU_PO = "假突破"           # False Breakout (Short)
    ZHEN_XIAN_TU_PO = "颈线突破"   # Neckline Breakout (Long)
    ZHEN_XIAN_DIE_PO = "颈线跌破"   # Neckline Breakdown (Short)
    HEAD_SHOULDER_TOP = "头肩顶"    # Head & Shoulders Top (Short)
    HEAD_SHOULDER_BOTTOM = "头肩底" # Head & Shoulders Bottom (Long)
    W_BOTTOM = "W底"              # W Bottom (Long)
    M_TOP = "M顶"                 # M Top (Short)
    ISLAND_REVERSAL_TOP = "岛型反转(顶)"  # Island Reversal Top (Short)
    ISLAND_REVERSAL_BOTTOM = "岛型反转(底)" # Island Reversal Bottom (Long)
    VOLUME_LEADS_PRICE = "量先价行"  # Volume Leads Price (Bullish)
    HUI_CAI_ZHI_CHENG = "回踩支撑"    # Pullback to Support in Uptrend (Long)
    ZHEN_TU_PO = "真突破"            # True Breakout with Volume (Long)
    DI_BU_FANG_LIANG = "底部放量突破"  # Bottom Volume Surge Breakout (Long)
    FAN_TAN_WU_LI = "反弹无力"        # Failed Bounce in Downtrend (Short)
    DIE_PO_ZHI_CHENG = "跌破支撑"      # Support Breakdown (Short)
    V_REVERSAL = "V型反转"             # V-Shaped Reversal (Long/Short)
    VOL_PRICE_DIVERGENCE_UP = "量价背离(上行)"   # Volume-Price Divergence Bullish
    VOL_PRICE_DIVERGENCE_DOWN = "量价背离(下行)"  # Volume-Price Divergence Bearish


class Trend(Enum):
    BULLISH = "多头"
    BEARISH = "空头"
    NEUTRAL = "盘整"


@dataclass
class Neckline:
    """颈线数据"""
    price: float
    start_idx: int
    end_idx: int
    touches: int
    line_type: str  # "support" or "resistance"
    strength: str = "medium"  # "strong", "medium", "weak"


@dataclass
class Pattern:
    """型态识别结果"""
    pattern_type: SignalType
    confidence: float
    neckline: float
    entry_price: float
    stop_loss: float
    target_price: float
    target_price_2: float  # 第二波目标 (黄金比例)
    risk_reward_ratio: float
    start_date: str
    signal_date: str
    description: str
    timeframe: str = "daily"  # "daily", "weekly", "hourly"
    signal_quality: str = "待定"  # "基本面" (real/fundamental) | "呬爛面" (bluff/fake) | "待定"
    v_reversal_probability: Optional[float] = None  # V型反转概率 (0~1)


@dataclass
class SupportLevel:
    """支撑/压力分级"""
    price: float
    level_type: str  # "strong_support", "weak_support", "strong_resistance", "weak_resistance"
    description: str


@dataclass
class AnalysisResult:
    """完整分析结果"""
    symbol: str
    analysis_date: str
    current_price: float
    current_trend: str
    daily_trend: str
    weekly_trend: str
    patterns: List[Pattern] = field(default_factory=list)
    support_levels: List[SupportLevel] = field(default_factory=list)
    volume_price_divergence: bool = False
    volume_leads_price: bool = False
    key_support: Optional[float] = None
    key_resistance: Optional[float] = None
    long_term_support: Optional[float] = None
    summary: str = ""


# ============================================================
# Core Analysis Engine
# ============================================================

class CaiSenAnalyzer:
    """蔡森技术分析核心引擎 v2.0"""

    def __init__(self, lookback_months: int = 12):
        self.lookback_months = lookback_months
        self.data: Optional[pd.DataFrame] = None
        self.weekly_data: Optional[pd.DataFrame] = None
        self.symbol: str = ""

    def fetch_data(self, symbol: str, period: str = "2y") -> pd.DataFrame:
        """获取股票数据 (默认2年以便周线分析)"""
        self.symbol = symbol
        ticker = yf.Ticker(symbol)
        self.data = ticker.history(period=period)
        if self.data.empty:
            raise ValueError(f"无法获取 {symbol} 的数据")
        # 生成周线数据
        self._build_weekly_data()
        return self.data

    def load_data(self, symbol: str, df: pd.DataFrame):
        """从已有 DataFrame 加载数据"""
        self.symbol = symbol
        self.data = df.copy()
        self._build_weekly_data()

    def _build_weekly_data(self):
        """从日线数据生成周线数据"""
        if self.data is None or len(self.data) < 20:
            self.weekly_data = None
            return
        df = self.data.copy()
        df['Week'] = df.index.isocalendar().week.values
        df['Year'] = df.index.isocalendar().year.values
        weekly = df.groupby(['Year', 'Week']).agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
        self.weekly_data = weekly

    def _get_current_price(self) -> float:
        """获取当前价格，处理 NaN"""
        if self.data is None or len(self.data) == 0:
            return 0.0
        close = self.data['Close'].values
        for i in range(len(close) - 1, -1, -1):
            if not np.isnan(close[i]):
                return float(close[i])
        return 0.0

    # --------------------------------------------------------
    # 1. Neckline Detection (颈线识别) - Enhanced
    # --------------------------------------------------------

    def find_support_resistance(self, window: int = 20, min_touches: int = 2) -> List[Neckline]:
        """识别支撑线和压力线"""
        df = self.data
        necklines = []

        highs = df['High'].values
        lows = df['Low'].values

        # 压力线
        resistance_levels = self._find_price_levels(highs, window, min_touches)
        for level, touches, start, end in resistance_levels:
            necklines.append(Neckline(
                price=level, start_idx=start, end_idx=end,
                touches=touches, line_type="resistance",
                strength="strong" if touches >= 3 else "medium"
            ))

        # 支撑线
        support_levels = self._find_price_levels(lows, window, min_touches)
        for level, touches, start, end in support_levels:
            necklines.append(Neckline(
                price=level, start_idx=start, end_idx=end,
                touches=touches, line_type="support",
                strength="strong" if touches >= 3 else "medium"
            ))

        necklines.sort(key=lambda x: x.touches, reverse=True)
        return necklines

    def _find_price_levels(self, prices: np.ndarray, window: int, min_touches: int,
                           tolerance_pct: float = 0.02) -> List[Tuple[float, int, int, int]]:
        """找出反复被触及的价格水平"""
        levels = []
        n = len(prices)

        extrema_indices = []
        for i in range(window, n - window):
            local = prices[i - window:i + window + 1]
            if prices[i] == max(local) or prices[i] == min(local):
                extrema_indices.append(i)

        clustered = []
        used = set()
        for i, idx in enumerate(extrema_indices):
            if idx in used:
                continue
            cluster = [idx]
            used.add(idx)
            for j, jdx in enumerate(extrema_indices):
                if jdx in used:
                    continue
                if abs(prices[idx] - prices[jdx]) / prices[idx] < tolerance_pct:
                    cluster.append(jdx)
                    used.add(jdx)
            if len(cluster) >= min_touches:
                avg_price = np.mean([prices[c] for c in cluster])
                clustered.append((
                    round(avg_price, 2), len(cluster), min(cluster), max(cluster)
                ))

        return clustered

    # --------------------------------------------------------
    # 2. Pattern Recognition (型态识别) - Enhanced v2
    # --------------------------------------------------------

    def detect_patterns(self) -> List[Pattern]:
        """识别所有技术型态"""
        patterns = []
        # 日线型态 (做空)
        patterns.extend(self._detect_po_di_fan())
        patterns.extend(self._detect_jia_tu_po())
        patterns.extend(self._detect_w_bottom())
        patterns.extend(self._detect_head_shoulders())
        patterns.extend(self._detect_island_reversal())
        patterns.extend(self._detect_volume_leads_price())
        # 日线型态 (做多) - v2.1 新增
        patterns.extend(self._detect_hui_cai_zhi_cheng())
        patterns.extend(self._detect_zhen_tu_po())
        patterns.extend(self._detect_di_bu_fang_liang())
        patterns.extend(self._detect_fan_tan_wu_li())
        patterns.extend(self._detect_die_po_zhi_cheng())
        # 周线型态 (更重大)
        patterns.extend(self._detect_weekly_po_di_fan())
        patterns.extend(self._detect_weekly_jia_tu_po())
        patterns.extend(self._detect_weekly_hui_cai())
        # v2.1 新增: V型反转 & 量价背離
        patterns.extend(self._detect_v_reversal())
        patterns.extend(self._detect_weekly_v_reversal())
        patterns.extend(self._detect_volume_price_divergence())
        # 应用基本面/呬爛面过滤
        patterns = self._apply_quality_filter(patterns)
        return patterns

    def _detect_po_di_fan(self) -> List[Pattern]:
        """
        破底翻检测 v2 (Bottom Breakdown & Recovery)
        =============================================
        改进:
        - 蔡森: "破底翻大都会越过前高" → 目标至少到前高
        - 更精确的底部区域识别
        - 量能确认要求更严格
        """
        patterns = []
        df = self.data
        if len(df) < 60:
            return patterns

        close = df['Close'].values
        volume = df['Volume'].values
        dates = df.index

        for lookback in [60, 90, 120]:
            if len(close) < lookback + 30:
                continue

            for end_idx in range(lookback + 30, len(close)):
                segment = close[end_idx - lookback:end_idx]
                seg_vol = volume[end_idx - lookback:end_idx]
                seg_high = df['High'].values[end_idx - lookback:end_idx]

                # 找到底部区域
                min_price = np.min(segment)
                min_idx = np.argmin(segment)

                # 颈线 = 底部区域的平均反弹高点
                if min_idx > 5 and min_idx < len(segment) - 5:
                    recovery_region = segment[min_idx:]
                    if len(recovery_region) > 3:
                        neckline_approx = np.percentile(recovery_region, 70)
                    else:
                        continue
                else:
                    continue

                # 找前期高点 (破底翻应至少涨到前高)
                pre_high = np.max(segment[:min_idx]) if min_idx > 10 else neckline_approx

                # 检查破底后翻回
                check_window = close[end_idx - 30:end_idx]
                if len(check_window) < 20:
                    continue

                # 破底检测
                broke_below = False
                broke_below_idx = -1
                for i, price in enumerate(check_window):
                    if price < min_price * 0.98:
                        broke_below = True
                        broke_below_idx = i
                        break

                if not broke_below or broke_below_idx >= len(check_window) - 3:
                    continue

                # 翻回检测
                after_break = check_window[broke_below_idx:]
                recovered = any(p > neckline_approx for p in after_break[-5:])

                if not recovered:
                    continue

                # 量能确认 (翻回时放量)
                recent_vol = volume[end_idx - 5:end_idx]
                avg_vol = np.mean(seg_vol)
                volume_confirm = np.mean(recent_vol) > avg_vol * 1.2

                # 计算信号
                current_price = close[end_idx - 1]
                entry = neckline_approx
                stop_loss = min_price * 0.97

                # 蔡森公式: 涨幅满足 = 底部到颈线距离
                distance = neckline_approx - min_price
                target_1 = neckline_approx + distance
                # 蔡森: "破底翻大都会越过前高" → 目标至少到前高
                target_1 = max(target_1, pre_high)
                target_2 = neckline_approx + distance * 1.618  # 黄金比例

                risk = entry - stop_loss
                reward = target_1 - entry
                rr_ratio = reward / risk if risk > 0 else 0

                confidence = 0.5
                if volume_confirm:
                    confidence += 0.2
                if rr_ratio >= 3:
                    confidence += 0.15
                if broke_below_idx > 5:
                    confidence += 0.15

                if confidence >= 0.5 and rr_ratio >= 1.5:
                    patterns.append(Pattern(
                        pattern_type=SignalType.PO_DI_FAN,
                        confidence=min(confidence, 1.0),
                        neckline=round(neckline_approx, 2),
                        entry_price=round(entry, 2),
                        stop_loss=round(stop_loss, 2),
                        target_price=round(target_1, 2),
                        target_price_2=round(target_2, 2),
                        risk_reward_ratio=round(rr_ratio, 2),
                        start_date=str(dates[end_idx - lookback].date()),
                        signal_date=str(dates[end_idx - 1].date()),
                        description=(
                            f"破底翻信号: 底部 {min_price:.2f} 被跌破后翻回颈线 {neckline_approx:.2f}"
                            f"{' (放量确认)' if volume_confirm else ''}"
                            f" | 前高参考: {pre_high:.2f}"
                        ),
                        timeframe="daily"
                    ))

        return self._deduplicate_patterns(patterns)

    def _detect_jia_tu_po(self) -> List[Pattern]:
        """
        假突破检测 v2 (False Breakout)
        ================================
        改进:
        - 量价背离检测更精确
        - 高档 vs 低档假突破区分
        """
        patterns = []
        df = self.data
        if len(df) < 60:
            return patterns

        close = df['Close'].values
        volume = df['Volume'].values
        dates = df.index

        for lookback in [60, 90, 120]:
            if len(close) < lookback + 30:
                continue

            for end_idx in range(lookback + 30, len(close)):
                segment = close[end_idx - lookback:end_idx]
                seg_vol = volume[end_idx - lookback:end_idx]

                max_price = np.max(segment)
                max_idx = np.argmax(segment)

                high_region = segment[max(0, max_idx - 10):max_idx + 10]
                neckline_approx = np.percentile(high_region, 80) if len(high_region) > 3 else max_price

                # 检查假突破
                check_window = close[end_idx - 30:end_idx]
                if len(check_window) < 20:
                    continue

                broke_above = False
                broke_above_idx = -1
                for i, price in enumerate(check_window):
                    if price > neckline_approx * 1.01:
                        broke_above = True
                        broke_above_idx = i
                        break

                if not broke_above or broke_above_idx >= len(check_window) - 3:
                    continue

                after_break = check_window[broke_above_idx:]
                fell_back = any(p < neckline_approx for p in after_break[-5:])

                if not fell_back:
                    continue

                # 量价背离: 价格创新高但量能不足
                vol_at_high = seg_vol[max_idx] if max_idx < len(seg_vol) else 0
                avg_vol = np.mean(seg_vol)
                vol_divergence = vol_at_high < avg_vol * 0.8

                # 高档判断
                is_high_level = segment[-1] > np.percentile(close[:end_idx], 75)

                current_price = close[end_idx - 1]
                entry = neckline_approx
                stop_loss = max_price * 1.03
                min_in_range = np.min(segment)
                distance = max_price - min_in_range
                target_1 = neckline_approx - distance
                target_2 = neckline_approx - distance * 1.618

                risk = stop_loss - entry
                reward = entry - target_1
                rr_ratio = reward / risk if risk > 0 else 0

                confidence = 0.5
                if vol_divergence:
                    confidence += 0.2
                if is_high_level:
                    confidence += 0.1  # 高档假突破更可靠
                if rr_ratio >= 3:
                    confidence += 0.15
                if current_price < neckline_approx:
                    confidence += 0.15

                if confidence >= 0.5 and rr_ratio >= 1.5:
                    level_text = "高档" if is_high_level else "低档"
                    patterns.append(Pattern(
                        pattern_type=SignalType.JIA_TU_PO,
                        confidence=min(confidence, 1.0),
                        neckline=round(neckline_approx, 2),
                        entry_price=round(entry, 2),
                        stop_loss=round(stop_loss, 2),
                        target_price=round(target_1, 2),
                        target_price_2=round(target_2, 2),
                        risk_reward_ratio=round(rr_ratio, 2),
                        start_date=str(dates[end_idx - lookback].date()),
                        signal_date=str(dates[end_idx - 1].date()),
                        description=(
                            f"{level_text}假突破: 突破前高 {max_price:.2f} 后跌回颈线 {neckline_approx:.2f}"
                            f"{' (量价背离)' if vol_divergence else ''}"
                        ),
                        timeframe="daily"
                    ))

        return self._deduplicate_patterns(patterns)

    def _detect_weekly_po_di_fan(self) -> List[Pattern]:
        """周线破底翻 — 蔡森: "量先价行上檔無壓", 周线信号更重大"""
        patterns = []
        if self.weekly_data is None or len(self.weekly_data) < 30:
            return patterns

        close = self.weekly_data['Close'].values
        volume = self.weekly_data['Volume'].values
        n = len(close)

        for lookback in [20, 30]:
            if n < lookback + 10:
                continue

            for end_idx in range(lookback + 10, n):
                segment = close[end_idx - lookback:end_idx]
                seg_vol = volume[end_idx - lookback:end_idx]

                min_price = np.min(segment)
                min_idx = np.argmin(segment)

                if min_idx < 3 or min_idx >= len(segment) - 3:
                    continue

                recovery = segment[min_idx:]
                neckline = np.percentile(recovery, 70) if len(recovery) > 2 else min_price * 1.05

                # 检查翻回
                recent = segment[-5:]
                if not any(p > neckline for p in recent):
                    continue

                # 检查量能突破
                recent_vol = np.mean(volume[end_idx - 3:end_idx])
                avg_vol = np.mean(seg_vol)
                vol_breakout = recent_vol > avg_vol * 1.5  # 周线需要更显著的放量

                if not vol_breakout:
                    continue

                # "量先价行上档无压"
                current = close[end_idx - 1]
                pre_high = np.max(segment[:min_idx]) if min_idx > 5 else neckline
                distance = neckline - min_price
                target_1 = max(neckline + distance, pre_high)
                target_2 = neckline + distance * 1.618

                entry = neckline
                stop_loss = min_price * 0.95
                risk = entry - stop_loss
                reward = target_1 - entry
                rr = reward / risk if risk > 0 else 0

                if rr >= 2:
                    patterns.append(Pattern(
                        pattern_type=SignalType.PO_DI_FAN,
                        confidence=min(0.7 + rr * 0.05, 0.95),
                        neckline=round(neckline, 2),
                        entry_price=round(entry, 2),
                        stop_loss=round(stop_loss, 2),
                        target_price=round(target_1, 2),
                        target_price_2=round(target_2, 2),
                        risk_reward_ratio=round(rr, 2),
                        start_date="N/A (weekly)",
                        signal_date="N/A (weekly)",
                        description=f"⭐ 周线破底翻! 量先价行上档无压 | 支撑 {min_price:.2f} → 颈线 {neckline:.2f}",
                        timeframe="weekly"
                    ))

        return patterns[:1]  # 周线只取最强信号

    def _detect_weekly_jia_tu_po(self) -> List[Pattern]:
        """周线假突破"""
        patterns = []
        if self.weekly_data is None or len(self.weekly_data) < 30:
            return patterns

        close = self.weekly_data['Close'].values
        volume = self.weekly_data['Volume'].values
        n = len(close)

        for lookback in [20, 30]:
            if n < lookback + 10:
                continue

            for end_idx in range(lookback + 10, n):
                segment = close[end_idx - lookback:end_idx]
                seg_vol = volume[end_idx - lookback:end_idx]

                max_price = np.max(segment)
                max_idx = np.argmax(segment)

                neckline = max_price * 0.97

                recent = segment[-5:]
                broke_above = any(p > neckline * 1.01 for p in recent)
                fell_back = any(p < neckline for p in segment[-3:])

                if not (broke_above and fell_back):
                    continue

                # 量价背离
                vol_at_high = seg_vol[max_idx] if max_idx < len(seg_vol) else 0
                avg_vol = np.mean(seg_vol)
                vol_div = vol_at_high < avg_vol * 0.7

                distance = max_price - np.min(segment)
                target_1 = neckline - distance
                target_2 = neckline - distance * 1.618

                entry = neckline
                stop_loss = max_price * 1.05
                risk = stop_loss - entry
                reward = entry - target_1
                rr = reward / risk if risk > 0 else 0

                if rr >= 2:
                    patterns.append(Pattern(
                        pattern_type=SignalType.JIA_TU_PO,
                        confidence=min(0.7 + rr * 0.05, 0.95),
                        neckline=round(neckline, 2),
                        entry_price=round(entry, 2),
                        stop_loss=round(stop_loss, 2),
                        target_price=round(target_1, 2),
                        target_price_2=round(target_2, 2),
                        risk_reward_ratio=round(rr, 2),
                        start_date="N/A (weekly)",
                        signal_date="N/A (weekly)",
                        description=f"⭐ 周线假突破!{' (量价背离)' if vol_div else ''} | 前高 {max_price:.2f} 跌破颈线 {neckline:.2f}",
                        timeframe="weekly"
                    ))

        return patterns[:1]

    def _detect_island_reversal(self) -> List[Pattern]:
        """
        岛型反转检测 (Island Reversal)
        蔡森博客提到的岛型反转结构
        特征: 跳空缺口后形成独立的价格岛屿, 再以反向缺口封闭
        """
        patterns = []
        df = self.data
        if len(df) < 40:
            return patterns

        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values
        volume = df['Volume'].values
        dates = df.index

        for i in range(15, len(close) - 5):
            # 顶部岛型: 先向上跳空, 再向下跳空封闭
            if (low[i] > high[i - 1] and  # 上跳空
                high[i + 5] < low[i + 6] if i + 6 < len(close) else False):  # 下跳空
                # 检查岛型区域
                island_high = np.max(high[i:i + 5])
                island_low = np.min(low[i:i + 5])
                island_vol = np.mean(volume[i:i + 5])
                pre_vol = np.mean(volume[max(0, i - 10):i])

                if island_vol > pre_vol * 1.5:  # 岛型区域放量
                    neckline = low[i]  # 上跳空缺口下缘
                    current = close[min(i + 8, len(close) - 1)]
                    distance = island_high - neckline
                    target_1 = neckline - distance
                    target_2 = neckline - distance * 1.618

                    entry = neckline
                    stop_loss = island_high * 1.02
                    risk = stop_loss - entry
                    reward = entry - target_1
                    rr = reward / risk if risk > 0 else 0

                    if rr >= 1.5:
                        patterns.append(Pattern(
                            pattern_type=SignalType.ISLAND_REVERSAL_TOP,
                            confidence=min(0.6 + rr * 0.05, 0.85),
                            neckline=round(neckline, 2),
                            entry_price=round(entry, 2),
                            stop_loss=round(stop_loss, 2),
                            target_price=round(target_1, 2),
                            target_price_2=round(target_2, 2),
                            risk_reward_ratio=round(rr, 2),
                            start_date=str(dates[max(0, i - 1)].date()),
                            signal_date=str(dates[min(i + 6, len(dates) - 1)].date()),
                            description=f"岛型反转(顶): 跳空缺口封闭形成翻转",
                            timeframe="daily"
                        ))

            # 底部岛型: 先向下跳空, 再向上跳空封闭
            if i + 6 < len(close):
                if (high[i] < low[i - 1] and  # 下跳空
                    low[i + 5] > high[i + 6]):  # 上跳空封闭
                    island_high = np.max(high[i:i + 5])
                    island_low = np.min(low[i:i + 5])
                    island_vol = np.mean(volume[i:i + 5])
                    post_vol = np.mean(volume[i + 5:min(i + 15, len(volume))])

                    if island_vol > post_vol * 0.5:  # 底部岛型不一定要放量
                        neckline = high[i]  # 下跳空缺口上缘
                        distance = neckline - island_low
                        target_1 = neckline + distance
                        target_2 = neckline + distance * 1.618

                        entry = neckline
                        stop_loss = island_low * 0.98
                        risk = entry - stop_loss
                        reward = target_1 - entry
                        rr = reward / risk if risk > 0 else 0

                        if rr >= 1.5:
                            patterns.append(Pattern(
                                pattern_type=SignalType.ISLAND_REVERSAL_BOTTOM,
                                confidence=min(0.6 + rr * 0.05, 0.85),
                                neckline=round(neckline, 2),
                                entry_price=round(entry, 2),
                                stop_loss=round(stop_loss, 2),
                                target_price=round(target_1, 2),
                                target_price_2=round(target_2, 2),
                                risk_reward_ratio=round(rr, 2),
                                start_date=str(dates[max(0, i - 1)].date()),
                                signal_date=str(dates[min(i + 6, len(dates) - 1)].date()),
                                description=f"岛型反转(底): 跳空缺口封闭形成翻转",
                                timeframe="daily"
                            ))

        return self._deduplicate_patterns(patterns)

    def _detect_volume_leads_price(self) -> List[Pattern]:
        """
        量先价行检测
        蔡森: "量先價行上檔無壓"
        特征: 量能先行突破(大幅放量), 价格尚未突破颈线但即将突破
        这是非常强的做多信号
        """
        patterns = []
        df = self.data
        if len(df) < 60:
            return patterns

        close = df['Close'].values
        volume = df['Volume'].values
        dates = df.index

        # 检查最近30天
        for end_idx in range(60, len(close)):
            segment = close[end_idx - 60:end_idx]
            seg_vol = volume[end_idx - 60:end_idx]

            # 找颈线 (近期反弹高点)
            recent_highs = []
            for i in range(len(segment) - 1):
                if segment[i] > segment[max(0, i-3)] and segment[i] > segment[min(len(segment)-1, i+3)]:
                    recent_highs.append(segment[i])

            if not recent_highs:
                continue

            neckline = np.percentile(recent_highs, 75)
            current = close[end_idx - 1]

            # 价格接近颈线但未突破
            near_neckline = neckline * 0.95 < current < neckline

            # 量能大幅突破
            recent_vol = np.mean(volume[end_idx - 5:end_idx])
            avg_vol = np.mean(seg_vol)
            vol_surge = recent_vol > avg_vol * 2.0  # 量能翻倍

            if near_neckline and vol_surge:
                distance = neckline - np.min(segment)
                target_1 = neckline + distance
                target_2 = neckline + distance * 1.618
                entry = neckline
                stop_loss = np.min(segment[-20:]) * 0.97
                risk = entry - stop_loss
                reward = target_1 - entry
                rr = reward / risk if risk > 0 else 0

                if rr >= 2:
                    patterns.append(Pattern(
                        pattern_type=SignalType.VOLUME_LEADS_PRICE,
                        confidence=min(0.7 + rr * 0.03, 0.9),
                        neckline=round(neckline, 2),
                        entry_price=round(entry, 2),
                        stop_loss=round(stop_loss, 2),
                        target_price=round(target_1, 2),
                        target_price_2=round(target_2, 2),
                        risk_reward_ratio=round(rr, 2),
                        start_date=str(dates[end_idx - 60].date()),
                        signal_date=str(dates[end_idx - 1].date()),
                        description=f"量先价行! 量能 {recent_vol/avg_vol:.1f}x 突破, 价格接近颈线 {neckline:.2f}",
                        timeframe="daily"
                    ))

        return self._deduplicate_patterns(patterns)

    def _detect_w_bottom(self) -> List[Pattern]:
        """W底检测"""
        patterns = []
        df = self.data
        if len(df) < 60:
            return patterns

        close = df['Close'].values
        dates = df.index

        try:
            from scipy.signal import argrelextrema
        except ImportError:
            return patterns

        for lookback in [60, 90]:
            if len(close) < lookback + 20:
                continue

            for end_idx in range(lookback + 20, len(close)):
                segment = close[end_idx - lookback:end_idx]

                try:
                    lows_idx = argrelextrema(segment, np.less, order=10)[0]
                except:
                    continue

                if len(lows_idx) < 2:
                    continue

                for i in range(len(lows_idx) - 1):
                    low1_idx, low2_idx = lows_idx[i], lows_idx[i + 1]
                    low1, low2 = segment[low1_idx], segment[low2_idx]

                    if abs(low1 - low2) / max(low1, low2) > 0.03:
                        continue

                    between = segment[low1_idx:low2_idx + 1]
                    middle_high = np.max(between)
                    if middle_high < low1 * 1.03:
                        continue

                    neckline = middle_high
                    current_price = segment[-1]

                    if current_price > neckline * 0.98:
                        entry = neckline
                        avg_low = (low1 + low2) / 2
                        distance = neckline - avg_low
                        stop_loss = avg_low * 0.97
                        target_1 = neckline + distance
                        # W底三波涨幅 (蔡森著作方法)
                        target_2 = neckline + distance * 1.618

                        risk = entry - stop_loss
                        reward = target_1 - entry
                        rr_ratio = reward / risk if risk > 0 else 0

                        if rr_ratio >= 2:
                            patterns.append(Pattern(
                                pattern_type=SignalType.W_BOTTOM,
                                confidence=min(0.6 + rr_ratio * 0.05, 0.9),
                                neckline=round(neckline, 2),
                                entry_price=round(entry, 2),
                                stop_loss=round(stop_loss, 2),
                                target_price=round(target_1, 2),
                                target_price_2=round(target_2, 2),
                                risk_reward_ratio=round(rr_ratio, 2),
                                start_date=str(dates[end_idx - lookback + low1_idx].date()),
                                signal_date=str(dates[end_idx - 1].date()),
                                description=f"W底: 两低点 {low1:.2f}/{low2:.2f}, 颈线 {neckline:.2f}",
                                timeframe="daily"
                            ))

        return self._deduplicate_patterns(patterns)

    def _detect_head_shoulders(self) -> List[Pattern]:
        """头肩顶/底检测"""
        patterns = []
        df = self.data
        if len(df) < 90:
            return patterns

        close = df['Close'].values
        dates = df.index

        try:
            from scipy.signal import argrelextrema
        except ImportError:
            return patterns

        for lookback in [90, 120]:
            if len(close) < lookback + 20:
                continue

            for end_idx in range(lookback + 20, len(close)):
                segment = close[end_idx - lookback:end_idx]

                try:
                    highs_idx = argrelextrema(segment, np.greater, order=10)[0]
                    lows_idx = argrelextrema(segment, np.less, order=10)[0]
                except:
                    continue

                # 头肩底
                if len(lows_idx) >= 3 and len(highs_idx) >= 2:
                    l = lows_idx[-3:]
                    lows = [segment[i] for i in l]

                    if len(lows) == 3:
                        sorted_lows = sorted(enumerate(lows), key=lambda x: x[1])
                        if sorted_lows[0][0] == 1:  # 中间最低
                            left_shoulder = lows[0]
                            head = lows[1]
                            right_shoulder = lows[2]

                            if abs(left_shoulder - right_shoulder) / max(left_shoulder, right_shoulder) < 0.05:
                                between_highs = []
                                for hi in highs_idx:
                                    if l[0] < hi < l[2]:
                                        between_highs.append(segment[hi])

                                if len(between_highs) >= 2:
                                    neckline = np.mean(sorted(between_highs)[-2:])

                                    if segment[-1] > neckline * 0.98:
                                        entry = neckline
                                        distance = neckline - head
                                        stop_loss = head * 0.97
                                        target_1 = neckline + distance
                                        target_2 = neckline + distance * 1.618

                                        risk = entry - stop_loss
                                        reward = target_1 - entry
                                        rr_ratio = reward / risk if risk > 0 else 0

                                        if rr_ratio >= 2:
                                            patterns.append(Pattern(
                                                pattern_type=SignalType.HEAD_SHOULDER_BOTTOM,
                                                confidence=min(0.65 + rr_ratio * 0.05, 0.95),
                                                neckline=round(neckline, 2),
                                                entry_price=round(entry, 2),
                                                stop_loss=round(stop_loss, 2),
                                                target_price=round(target_1, 2),
                                                target_price_2=round(target_2, 2),
                                                risk_reward_ratio=round(rr_ratio, 2),
                                                start_date=str(dates[end_idx - lookback + l[0]].date()),
                                                signal_date=str(dates[end_idx - 1].date()),
                                                description=f"头肩底: 左肩 {left_shoulder:.2f}, 头 {head:.2f}, 右肩 {right_shoulder:.2f}",
                                                timeframe="daily"
                                            ))

                # 头肩顶
                if len(highs_idx) >= 3 and len(lows_idx) >= 2:
                    h = highs_idx[-3:]
                    highs = [segment[i] for i in h]

                    if len(highs) == 3:
                        sorted_highs = sorted(enumerate(highs), key=lambda x: x[1], reverse=True)
                        if sorted_highs[0][0] == 1:  # 中间最高
                            left_shoulder = highs[0]
                            head = highs[1]
                            right_shoulder = highs[2]

                            if abs(left_shoulder - right_shoulder) / max(left_shoulder, right_shoulder) < 0.05:
                                between_lows = []
                                for li in lows_idx:
                                    if h[0] < li < h[2]:
                                        between_lows.append(segment[li])

                                if len(between_lows) >= 2:
                                    neckline = np.mean(sorted(between_lows)[:2])

                                    if segment[-1] < neckline * 1.02:
                                        entry = neckline
                                        distance = head - neckline
                                        stop_loss = head * 1.03
                                        target_1 = neckline - distance
                                        target_2 = neckline - distance * 1.618

                                        risk = stop_loss - entry
                                        reward = entry - target_1
                                        rr_ratio = reward / risk if risk > 0 else 0

                                        if rr_ratio >= 2:
                                            patterns.append(Pattern(
                                                pattern_type=SignalType.HEAD_SHOULDER_TOP,
                                                confidence=min(0.65 + rr_ratio * 0.05, 0.95),
                                                neckline=round(neckline, 2),
                                                entry_price=round(entry, 2),
                                                stop_loss=round(stop_loss, 2),
                                                target_price=round(target_1, 2),
                                                target_price_2=round(target_2, 2),
                                                risk_reward_ratio=round(rr_ratio, 2),
                                                start_date=str(dates[end_idx - lookback + h[0]].date()),
                                                signal_date=str(dates[end_idx - 1].date()),
                                                description=f"头肩顶: 左肩 {left_shoulder:.2f}, 头 {head:.2f}, 右肩 {right_shoulder:.2f}",
                                                timeframe="daily"
                                            ))

        return self._deduplicate_patterns(patterns)

    # --------------------------------------------------------
    # 2b. New LONG Signal Detection (做多信号) - v2.1
    # --------------------------------------------------------

    def _detect_hui_cai_zhi_cheng(self) -> List[Pattern]:
        """
        回踩支撑做多 (Pullback to Support in Uptrend)
        ================================================
        蔡森: 在多头趋势中，回踩支撑是最佳买点
        特征:
        - MA20 > MA60 (多头排列)
        - 价格回踩MA20或前期支撑线
        - 回踩时缩量，反弹时放量
        - 收盘站稳支撑之上
        """
        patterns = []
        df = self.data
        if len(df) < 60:
            return patterns

        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values
        volume = df['Volume'].values
        dates = df.index

        for end_idx in range(60, len(close)):
            # Check MA alignment (多头排列)
            ma20 = np.mean(close[end_idx - 20:end_idx])
            ma60 = np.mean(close[end_idx - 60:end_idx])
            ma20_prev = np.mean(close[end_idx - 25:end_idx - 5]) if end_idx >= 25 else ma20

            is_uptrend = ma20 > ma60 * 1.01  # MA20 above MA60 by at least 1%
            if not is_uptrend:
                continue

            # Check if price pulled back to MA20 area
            current = close[end_idx - 1]
            prev5 = close[end_idx - 6:end_idx - 1]
            lowest_recent = np.min(low[end_idx - 10:end_idx])

            # Price touched near MA20 (within 2%)
            touched_ma20 = lowest_recent <= ma20 * 1.02
            # Price bounced back above MA20
            closed_above_ma20 = current > ma20
            # Pullback was shallow (< 8% from recent high)
            recent_high = np.max(high[end_idx - 30:end_idx])
            pullback_pct = (recent_high - lowest_recent) / recent_high
            shallow_pullback = pullback_pct < 0.08

            if touched_ma20 and closed_above_ma20 and shallow_pullback:
                # Volume: pullback should be on lower volume
                pullback_vol = np.mean(volume[end_idx - 8:end_idx - 3])
                bounce_vol = np.mean(volume[end_idx - 3:end_idx])
                vol_confirmation = bounce_vol > pullback_vol * 1.1

                entry = current
                stop_loss = ma60 * 0.97  # Below MA60
                distance = entry - stop_loss
                target_1 = entry + distance * 2  # 2x risk
                target_2 = recent_high * 1.05  # Above recent high

                risk = entry - stop_loss
                reward = target_1 - entry
                rr = reward / risk if risk > 0 else 0

                confidence = 0.55
                if vol_confirmation:
                    confidence += 0.15
                if pullback_pct < 0.05:
                    confidence += 0.1
                if ma20 > ma60 * 1.03:
                    confidence += 0.1
                if rr >= 2:
                    confidence += 0.1

                if rr >= 1.5:
                    patterns.append(Pattern(
                        pattern_type=SignalType.HUI_CAI_ZHI_CHENG,
                        confidence=min(confidence, 0.95),
                        neckline=round(ma20, 2),
                        entry_price=round(entry, 2),
                        stop_loss=round(stop_loss, 2),
                        target_price=round(target_1, 2),
                        target_price_2=round(target_2, 2),
                        risk_reward_ratio=round(rr, 2),
                        start_date=str(dates[end_idx - 30].date()),
                        signal_date=str(dates[end_idx - 1].date()),
                        description=f"回踩支撑: 价格回踩MA20({ma20:.2f})后反弹, 多头趋势确认"
                                    f"{' (放量反弹)' if vol_confirmation else ' (缩量回踩)'}",
                        timeframe="daily"
                    ))

        return self._deduplicate_patterns(patterns)

    def _detect_zhen_tu_po(self) -> List[Pattern]:
        """
        真突破做多 (True Breakout with Volume)
        ========================================
        与假突破相反: 突破前高后站稳，量价齐升
        蔡森: 真突破需要量能配合
        特征:
        - 突破前期阻力位
        - 收盘站稳颈线之上 (3天以上)
        - 突破时放量
        - 价格创新高
        """
        patterns = []
        df = self.data
        if len(df) < 60:
            return patterns

        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values
        volume = df['Volume'].values
        dates = df.index

        for lookback in [40, 60, 90]:
            if len(close) < lookback + 10:
                continue

            for end_idx in range(lookback + 10, len(close)):
                segment = close[end_idx - lookback:end_idx]
                seg_high = high[end_idx - lookback:end_idx]
                seg_vol = volume[end_idx - lookback:end_idx]

                # Find resistance level (前高)
                prev_high = np.percentile(seg_high, 90)
                if prev_high == 0:
                    continue

                # Check if price recently broke above resistance
                recent_5 = close[end_idx - 5:end_idx]
                broke_above = any(p > prev_high * 1.005 for p in recent_5)
                if not broke_above:
                    continue

                # Check if it stayed above for at least 3 days
                stayed_above_count = sum(1 for p in recent_5 if p > prev_high * 0.995)
                if stayed_above_count < 3:
                    continue

                # Volume confirmation at breakout
                breakout_vol = np.mean(volume[end_idx - 5:end_idx])
                avg_vol = np.mean(seg_vol)
                vol_surge = breakout_vol > avg_vol * 1.3

                # Price making new highs
                current = close[end_idx - 1]
                is_new_high = current > np.max(segment) * 0.99

                if vol_surge and current > prev_high:
                    entry = current
                    stop_loss = prev_high * 0.97  # Below the broken resistance
                    distance = prev_high - np.min(segment)
                    target_1 = entry + distance
                    target_2 = entry + distance * 1.618

                    risk = entry - stop_loss
                    reward = target_1 - entry
                    rr = reward / risk if risk > 0 else 0

                    confidence = 0.6
                    if vol_surge:
                        confidence += 0.15
                    if is_new_high:
                        confidence += 0.1
                    if stayed_above_count >= 4:
                        confidence += 0.1
                    if rr >= 2:
                        confidence += 0.05

                    if rr >= 1.5:
                        patterns.append(Pattern(
                            pattern_type=SignalType.ZHEN_TU_PO,
                            confidence=min(confidence, 0.95),
                            neckline=round(prev_high, 2),
                            entry_price=round(entry, 2),
                            stop_loss=round(stop_loss, 2),
                            target_price=round(target_1, 2),
                            target_price_2=round(target_2, 2),
                            risk_reward_ratio=round(rr, 2),
                            start_date=str(dates[end_idx - lookback].date()),
                            signal_date=str(dates[end_idx - 1].date()),
                            description=f"真突破: 突破前高 {prev_high:.2f} 站稳 {stayed_above_count}天"
                                        f"{' (量价齐升)' if vol_surge else ''}",
                            timeframe="daily"
                        ))

        return self._deduplicate_patterns(patterns)

    def _detect_di_bu_fang_liang(self) -> List[Pattern]:
        """
        底部放量突破 (Bottom Volume Surge Breakout)
        ==============================================
        特征:
        - 长期下跌后出现底部盘整
        - 某天量能突然放大(>2x平均)
        - 价格突破底部盘整区间上沿
        - 类似底部岛型但不需要缺口
        """
        patterns = []
        df = self.data
        if len(df) < 90:
            return patterns

        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values
        volume = df['Volume'].values
        dates = df.index

        for end_idx in range(90, len(close)):
            # Check for extended decline (过去60天跌超过15%)
            old_price = close[end_idx - 60]
            current = close[end_idx - 1]
            if old_price <= 0:
                continue

            decline_pct = (old_price - np.min(close[end_idx - 60:end_idx])) / old_price
            if decline_pct < 0.15:
                continue  # Not a significant decline

            # Find the bottom range
            bottom_region = low[end_idx - 40:end_idx]
            bottom_low = np.min(bottom_region)
            bottom_high = np.percentile(bottom_region, 75)
            consolidation_range = (bottom_high - bottom_low) / bottom_low

            # Should be in a tight consolidation (< 15% range)
            if consolidation_range > 0.15:
                continue

            # Check for volume surge
            avg_vol_30 = np.mean(volume[end_idx - 30:end_idx])
            recent_vol = volume[end_idx - 3:end_idx]
            max_recent_vol = np.max(recent_vol)
            vol_surge = max_recent_vol > avg_vol_30 * 2.0

            if not vol_surge:
                continue

            # Price breaking above consolidation
            broke_out = current > bottom_high * 1.01
            if not broke_out:
                continue

            entry = current
            stop_loss = bottom_low * 0.97
            distance = bottom_high - bottom_low
            target_1 = entry + distance * 1.5
            target_2 = entry + distance * 2.618

            risk = entry - stop_loss
            reward = target_1 - entry
            rr = reward / risk if risk > 0 else 0

            confidence = 0.6
            if max_recent_vol > avg_vol_30 * 3:
                confidence += 0.15  # Extreme volume
            if decline_pct > 0.25:
                confidence += 0.1  # Deeper decline = bigger bounce
            if rr >= 2:
                confidence += 0.1

            if rr >= 1.5 and confidence >= 0.6:
                patterns.append(Pattern(
                    pattern_type=SignalType.DI_BU_FANG_LIANG,
                    confidence=min(confidence, 0.95),
                    neckline=round(bottom_high, 2),
                    entry_price=round(entry, 2),
                    stop_loss=round(stop_loss, 2),
                    target_price=round(target_1, 2),
                    target_price_2=round(target_2, 2),
                    risk_reward_ratio=round(rr, 2),
                    start_date=str(dates[end_idx - 60].date()),
                    signal_date=str(dates[end_idx - 1].date()),
                    description=f"底部放量突破: 下跌{decline_pct:.0%}后底部放量{max_recent_vol/avg_vol_30:.1f}x突破",
                    timeframe="daily"
                ))

        return self._deduplicate_patterns(patterns)

    def _detect_fan_tan_wu_li(self) -> List[Pattern]:
        """
        反弹无力做空 (Failed Bounce in Downtrend)
        =============================================
        蔡森: 空头趋势中反弹到压力位无法突破 = 做空点
        特征:
        - MA20 < MA60 (空头排列)
        - 价格反弹到MA20或前期支撑(变压力)
        - 反弹时缩量
        - 收盘回落到压力之下
        """
        patterns = []
        df = self.data
        if len(df) < 60:
            return patterns

        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values
        volume = df['Volume'].values
        dates = df.index

        for end_idx in range(60, len(close)):
            ma20 = np.mean(close[end_idx - 20:end_idx])
            ma60 = np.mean(close[end_idx - 60:end_idx])

            is_downtrend = ma20 < ma60 * 0.99
            if not is_downtrend:
                continue

            current = close[end_idx - 1]
            recent_high = np.max(high[end_idx - 10:end_idx])

            # Price rallied toward MA20 but couldn't break
            touched_ma20 = recent_high >= ma20 * 0.98
            closed_below = current < ma20 * 0.99
            rally_vol = np.mean(volume[end_idx - 8:end_idx])
            avg_vol = np.mean(volume[end_idx - 30:end_idx])
            weak_rally = rally_vol < avg_vol * 0.85  # Low volume rally

            if touched_ma20 and closed_below and weak_rally:
                entry = current
                stop_loss = ma20 * 1.03
                distance = ma20 - np.min(low[end_idx - 30:end_idx])
                target_1 = entry - distance
                target_2 = entry - distance * 1.618

                risk = stop_loss - entry
                reward = entry - target_1
                rr = reward / risk if risk > 0 else 0

                confidence = 0.55
                if weak_rally:
                    confidence += 0.15
                if ma20 < ma60 * 0.97:
                    confidence += 0.1  # Strong downtrend
                if rr >= 2:
                    confidence += 0.1

                if rr >= 1.5:
                    patterns.append(Pattern(
                        pattern_type=SignalType.FAN_TAN_WU_LI,
                        confidence=min(confidence, 0.9),
                        neckline=round(ma20, 2),
                        entry_price=round(entry, 2),
                        stop_loss=round(stop_loss, 2),
                        target_price=round(target_1, 2),
                        target_price_2=round(target_2, 2),
                        risk_reward_ratio=round(rr, 2),
                        start_date=str(dates[end_idx - 30].date()),
                        signal_date=str(dates[end_idx - 1].date()),
                        description=f"反弹无力: 价格反弹至MA20({ma20:.2f})但缩量无法突破, 空头趋势",
                        timeframe="daily"
                    ))

        return self._deduplicate_patterns(patterns)

    def _detect_die_po_zhi_cheng(self) -> List[Pattern]:
        """
        跌破支撑做空 (Support Breakdown)
        ====================================
        特征:
        - 价格跌破前期重要支撑位
        - 跌破时放量
        - 跌破后反弹不过支撑(变压力)
        """
        patterns = []
        df = self.data
        if len(df) < 60:
            return patterns

        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values
        volume = df['Volume'].values
        dates = df.index

        for lookback in [40, 60, 90]:
            if len(close) < lookback + 10:
                continue

            for end_idx in range(lookback + 10, len(close)):
                segment = close[end_idx - lookback:end_idx]
                seg_low = low[end_idx - lookback:end_idx]
                seg_vol = volume[end_idx - lookback:end_idx]

                # Find support level
                support = np.percentile(seg_low, 15)
                current = close[end_idx - 1]

                # Price broke below support
                broke_below = any(p < support * 0.99 for p in low[end_idx - 10:end_idx])
                if not broke_below:
                    continue

                # Price failed to recover above support
                failed_recovery = all(p < support * 1.01 for p in close[end_idx - 3:end_idx])

                # Volume on breakdown
                breakdown_vol = np.mean(volume[end_idx - 8:end_idx - 3])
                avg_vol = np.mean(seg_vol)
                vol_confirm = breakdown_vol > avg_vol * 1.2

                if broke_below and failed_recovery:
                    entry = current
                    stop_loss = support * 1.02
                    distance = support - np.min(seg_low)
                    target_1 = entry - distance
                    target_2 = entry - distance * 1.618

                    risk = stop_loss - entry
                    reward = entry - target_1
                    rr = reward / risk if risk > 0 else 0

                    confidence = 0.55
                    if vol_confirm:
                        confidence += 0.15
                    if rr >= 2:
                        confidence += 0.1

                    if rr >= 1.5 and current < support:
                        patterns.append(Pattern(
                            pattern_type=SignalType.DIE_PO_ZHI_CHENG,
                            confidence=min(confidence, 0.9),
                            neckline=round(support, 2),
                            entry_price=round(entry, 2),
                            stop_loss=round(stop_loss, 2),
                            target_price=round(target_1, 2),
                            target_price_2=round(target_2, 2),
                            risk_reward_ratio=round(rr, 2),
                            start_date=str(dates[end_idx - lookback].date()),
                            signal_date=str(dates[end_idx - 1].date()),
                            description=f"跌破支撑: 跌破 {support:.2f} 后反弹无力"
                                        f"{' (放量跌破)' if vol_confirm else ''}",
                            timeframe="daily"
                        ))

        return self._deduplicate_patterns(patterns)

    def _detect_weekly_hui_cai(self) -> List[Pattern]:
        """
        周线回踩支撑做多 — 蔡森强调周线更重大
        """
        patterns = []
        if self.weekly_data is None or len(self.weekly_data) < 30:
            return patterns

        close = self.weekly_data['Close'].values
        volume = self.weekly_data['Volume'].values
        n = len(close)

        if n < 20:
            return patterns

        ma10 = np.mean(close[-10:]) if n >= 10 else np.mean(close)
        ma20 = np.mean(close[-20:]) if n >= 20 else ma10

        is_uptrend = ma10 > ma20 * 1.01
        if not is_uptrend:
            return patterns

        current = close[-1]
        recent_low = np.min(close[-5:])

        # Touched MA10 and bounced
        touched = recent_low <= ma10 * 1.02
        bounced = current > ma10

        if touched and bounced:
            # Volume check
            avg_vol = np.mean(volume)
            recent_vol = np.mean(volume[-3:])
            vol_ok = recent_vol > avg_vol * 0.8

            entry = current
            stop_loss = ma20 * 0.97
            prev_high = np.max(close[-15:])
            target_1 = prev_high * 1.05
            target_2 = prev_high * 1.15

            risk = entry - stop_loss
            reward = target_1 - entry
            rr = reward / risk if risk > 0 else 0

            if rr >= 1.5:
                patterns.append(Pattern(
                    pattern_type=SignalType.HUI_CAI_ZHI_CHENG,
                    confidence=min(0.7 + rr * 0.05, 0.9),
                    neckline=round(ma10, 2),
                    entry_price=round(entry, 2),
                    stop_loss=round(stop_loss, 2),
                    target_price=round(target_1, 2),
                    target_price_2=round(target_2, 2),
                    risk_reward_ratio=round(rr, 2),
                    start_date="N/A (weekly)",
                    signal_date="N/A (weekly)",
                    description=f"⭐ 周线回踩支撑! MA10({ma10:.2f})支撑有效, 多头趋势",
                    timeframe="weekly"
                ))

        return patterns[:1]

    # --------------------------------------------------------
    # v2.1 新增: V型反转 & 量价背離 & 呬爛面过滤
    # 基于蔡森第462集《經典技術分析》20260407
    # --------------------------------------------------------

    def _detect_v_reversal(self) -> List[Pattern]:
        """
        V型反转检测 (V-Shaped Reversal)
        ================================
        蔡森第462集: V型反转的機率分析
        特征:
        - 快速下跌后快速反弹, 形成尖底
        - 下跌段和反弹段速度大致对称
        - 反弹时需放量确认 (量价配合)
        - 概率评分基于: 底部型态、量能变化、跌幅深度、反弹速度
        """
        patterns = []
        df = self.data
        if len(df) < 40:
            return patterns

        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values
        volume = df['Volume'].values
        dates = df.index

        for lookback in [30, 45, 60]:
            if len(close) < lookback + 10:
                continue

            for end_idx in range(lookback + 10, len(close)):
                segment = close[end_idx - lookback:end_idx]
                seg_vol = volume[end_idx - lookback:end_idx]
                seg_low = low[end_idx - lookback:end_idx]

                # 找到最低点 (V底)
                min_idx = np.argmin(segment)
                min_price = segment[min_idx]

                # V底必须在中间区域 (不能太靠两端)
                if min_idx < lookback * 0.2 or min_idx > lookback * 0.8:
                    continue

                # 前半段: 下跌
                pre_drop = segment[:min_idx + 1]
                # 后半段: 反弹
                post_rise = segment[min_idx:]

                if len(pre_drop) < 5 or len(post_rise) < 5:
                    continue

                peak_before = np.max(pre_drop)
                current_price = segment[-1]

                # 下跌幅度
                drop_pct = (peak_before - min_price) / peak_before

                # 反弹幅度 (从底部到当前)
                rise_pct = (current_price - min_price) / min_price if min_price > 0 else 0

                # 计算下跌和反弹的速度 (斜率)
                drop_speed = drop_pct / len(pre_drop) if len(pre_drop) > 0 else 0
                rise_speed = rise_pct / len(post_rise) if len(post_rise) > 0 else 0

                # V型条件: 快速下跌 + 快速反弹
                is_v_shape = (
                    drop_pct > 0.05 and  # 下跌至少5%
                    rise_pct > 0.03 and  # 反弹至少3%
                    drop_speed > 0.003 and  # 下跌速度足够快
                    rise_speed > 0.002  # 反弹速度足够快
                )

                if not is_v_shape:
                    continue

                # 量能分析: 反弹段放量
                pre_drop_vol = np.mean(seg_vol[:min_idx + 1]) if min_idx > 0 else np.mean(seg_vol)
                post_rise_vol = np.mean(seg_vol[min_idx:])
                avg_vol = np.mean(seg_vol)
                vol_surge = post_rise_vol > avg_vol * 1.3  # 反弹量能 > 平均130%

                # 底部型态: 尖底 vs 圆底
                bottom_range = seg_low[max(0, min_idx - 3):min_idx + 4]
                bottom_volatility = np.std(bottom_range) / np.mean(bottom_range) if np.mean(bottom_range) > 0 else 0
                is_sharp_bottom = bottom_volatility < 0.02  # 尖底波动小

                # === V型反转概率评分 ===
                probability = 0.3  # 基础概率

                # 因子1: 反弹速度 vs 下跌速度 (越对称越好)
                speed_ratio = rise_speed / drop_speed if drop_speed > 0 else 0
                if 0.5 <= speed_ratio <= 2.0:
                    probability += 0.15  # 速度对称
                elif speed_ratio > 2.0:
                    probability += 0.10  # 反弹过快, 略降

                # 因子2: 量能确认
                if vol_surge:
                    vol_ratio = post_rise_vol / avg_vol
                    probability += min(0.2, vol_ratio * 0.05)

                # 因子3: 尖底型态
                if is_sharp_bottom:
                    probability += 0.10

                # 因子4: 跌幅足够深 (>10%)
                if drop_pct > 0.10:
                    probability += 0.10
                elif drop_pct > 0.15:
                    probability += 0.15

                # 因子5: 已反弹超过跌幅的50%
                recovery_ratio = rise_pct / drop_pct if drop_pct > 0 else 0
                if recovery_ratio > 0.5:
                    probability += 0.10

                probability = min(probability, 0.95)

                # 计算交易参数
                neckline = peak_before  # 前高作为颈线
                entry = current_price
                stop_loss = min_price * 0.97

                distance = peak_before - min_price
                target_1 = min_price + distance  # 等幅反弹
                target_2 = min_price + distance * 1.618  # 黄金比例

                risk = entry - stop_loss
                reward = target_1 - entry
                rr = reward / risk if risk > 0 else 0

                # 呬爛面判定
                quality = self._classify_signal_quality(
                    vol_surge=vol_surge,
                    rr_ratio=rr,
                    drop_pct=drop_pct,
                    recovery_ratio=recovery_ratio,
                    is_sharp=is_sharp_bottom
                )

                if rr >= 1.0 and probability >= 0.45:
                    patterns.append(Pattern(
                        pattern_type=SignalType.V_REVERSAL,
                        confidence=min(probability, 1.0),
                        neckline=round(neckline, 2),
                        entry_price=round(entry, 2),
                        stop_loss=round(stop_loss, 2),
                        target_price=round(target_1, 2),
                        target_price_2=round(target_2, 2),
                        risk_reward_ratio=round(rr, 2),
                        start_date=str(dates[end_idx - lookback].date()),
                        signal_date=str(dates[end_idx - 1].date()),
                        description=(
                            f"V型反转! 下跌 {drop_pct:.1%} → 反弹 {rise_pct:.1%}"
                            f" | 速度比: {speed_ratio:.2f}"
                            f"{' (放量确认)' if vol_surge else ' (量能不足⚠️)'}"
                            f" | 概率: {probability:.0%}"
                        ),
                        timeframe="daily",
                        signal_quality=quality,
                        v_reversal_probability=round(probability, 2)
                    ))

        return self._deduplicate_patterns(patterns)

    def _detect_weekly_v_reversal(self) -> List[Pattern]:
        """
        周线V型反转 — 蔡森: 周线信号更重大
        """
        patterns = []
        if self.weekly_data is None or len(self.weekly_data) < 15:
            return patterns

        close = self.weekly_data['Close'].values
        volume = self.weekly_data['Volume'].values
        n = len(close)

        if n < 12:
            return patterns

        lookback = min(n, 16)
        segment = close[-lookback:]
        seg_vol = volume[-lookback:]

        min_idx = np.argmin(segment)
        min_price = segment[min_idx]

        if min_idx < 3 or min_idx > lookback - 4:
            return patterns

        pre_drop = segment[:min_idx + 1]
        post_rise = segment[min_idx:]

        peak_before = np.max(pre_drop)
        current_price = segment[-1]

        drop_pct = (peak_before - min_price) / peak_before
        rise_pct = (current_price - min_price) / min_price if min_price > 0 else 0

        is_v = drop_pct > 0.06 and rise_pct > 0.04
        if not is_v:
            return patterns

        avg_vol = np.mean(seg_vol)
        post_vol = np.mean(seg_vol[min_idx:])
        vol_surge = post_vol > avg_vol * 1.2

        recovery_ratio = rise_pct / drop_pct if drop_pct > 0 else 0
        probability = 0.4
        if vol_surge:
            probability += 0.15
        if recovery_ratio > 0.5:
            probability += 0.15
        if drop_pct > 0.10:
            probability += 0.10

        entry = current_price
        stop_loss = min_price * 0.97
        distance = peak_before - min_price
        target_1 = min_price + distance
        target_2 = min_price + distance * 1.618
        risk = entry - stop_loss
        reward = target_1 - entry
        rr = reward / risk if risk > 0 else 0

        quality = self._classify_signal_quality(
            vol_surge=vol_surge, rr_ratio=rr,
            drop_pct=drop_pct, recovery_ratio=recovery_ratio, is_sharp=True
        )

        if rr >= 1.0 and probability >= 0.45:
            patterns.append(Pattern(
                pattern_type=SignalType.V_REVERSAL,
                confidence=min(probability, 1.0),
                neckline=round(peak_before, 2),
                entry_price=round(entry, 2),
                stop_loss=round(stop_loss, 2),
                target_price=round(target_1, 2),
                target_price_2=round(target_2, 2),
                risk_reward_ratio=round(rr, 2),
                start_date="N/A (weekly)",
                signal_date="N/A (weekly)",
                description=(
                    f"⭐ 周线V型反转! 下跌 {drop_pct:.1%} → 反弹 {rise_pct:.1%}"
                    f"{' (放量确认)' if vol_surge else ' (量能不足⚠️)'}"
                ),
                timeframe="weekly",
                signal_quality=quality,
                v_reversal_probability=round(probability, 2)
            ))

        return patterns[:1]

    def _detect_volume_price_divergence(self) -> List[Pattern]:
        """
        量價背離检测
        ==================
        蔡森: 量价背離是判断呬爛面(假突破)的关键工具

        上行背離 (看多): 价格创新低, 但成交量不创新高 (卖压减弱)
        下行背離 (看空): 价格创新高, 但成交量不创新高 (买盘减弱 = 假突破信号)
        """
        patterns = []
        df = self.data
        if len(df) < 40:
            return patterns

        close = df['Close'].values
        volume = df['Volume'].values
        dates = df.index

        # 检查最近30天
        check_window = min(30, len(close))
        for end_idx in range(40, len(close)):
            seg_close = close[end_idx - check_window:end_idx]
            seg_vol = volume[end_idx - check_window:end_idx]

            # 找局部极值
            price_highs = []
            price_lows = []
            vol_at_highs = []
            vol_at_lows = []

            for i in range(3, len(seg_close) - 3):
                # 局部高点
                if seg_close[i] == max(seg_close[i - 3:i + 4]):
                    price_highs.append(seg_close[i])
                    vol_at_highs.append(seg_vol[i])
                # 局部低点
                if seg_close[i] == min(seg_close[i - 3:i + 4]):
                    price_lows.append(seg_close[i])
                    vol_at_lows.append(seg_vol[i])

            # 下行背離: 价格创新高但量能未创新高
            if len(price_highs) >= 2 and len(vol_at_highs) >= 2:
                if price_highs[-1] > price_highs[-2] and vol_at_highs[-1] < vol_at_highs[-2]:
                    vol_decline_pct = (vol_at_highs[-2] - vol_at_highs[-1]) / vol_at_highs[-2]
                    if vol_decline_pct > 0.15:  # 量能下降超过15%
                        current = close[end_idx - 1]
                        patterns.append(Pattern(
                            pattern_type=SignalType.VOL_PRICE_DIVERGENCE_DOWN,
                            confidence=min(0.5 + vol_decline_pct, 0.85),
                            neckline=round(price_highs[-1], 2),
                            entry_price=round(current, 2),
                            stop_loss=round(price_highs[-1] * 1.03, 2),
                            target_price=round(price_highs[-2], 2),
                            target_price_2=round(price_highs[-2] * 0.95, 2),
                            risk_reward_ratio=2.0,
                            start_date=str(dates[end_idx - check_window].date()),
                            signal_date=str(dates[end_idx - 1].date()),
                            description=(
                                f"⚠️ 量价背离(下行): 价创新高 {price_highs[-1]:.2f}"
                                f" 但量能下降 {vol_decline_pct:.0%}"
                                f" → 假突破风险!"
                            ),
                            timeframe="daily",
                            signal_quality="呬爛面"
                        ))

            # 上行背離: 价格创新低但量能未创新高 (卖压减弱 = 底部信号)
            if len(price_lows) >= 2 and len(vol_at_lows) >= 2:
                if price_lows[-1] < price_lows[-2] and vol_at_lows[-1] < vol_at_lows[-2]:
                    vol_decline_pct = (vol_at_lows[-2] - vol_at_lows[-1]) / vol_at_lows[-2]
                    if vol_decline_pct > 0.15:
                        current = close[end_idx - 1]
                        patterns.append(Pattern(
                            pattern_type=SignalType.VOL_PRICE_DIVERGENCE_UP,
                            confidence=min(0.5 + vol_decline_pct, 0.85),
                            neckline=round(price_lows[-2], 2),
                            entry_price=round(current, 2),
                            stop_loss=round(price_lows[-1] * 0.97, 2),
                            target_price=round(price_lows[-2] * 1.05, 2),
                            target_price_2=round(price_lows[-2] * 1.10, 2),
                            risk_reward_ratio=2.5,
                            start_date=str(dates[end_idx - check_window].date()),
                            signal_date=str(dates[end_idx - 1].date()),
                            description=(
                                f"🟢 量价背离(上行): 价创新低 {price_lows[-1]:.2f}"
                                f" 但量能萎缩 {vol_decline_pct:.0%}"
                                f" → 卖压减弱, 底部信号"
                            ),
                            timeframe="daily",
                            signal_quality="基本面"
                        ))

        return self._deduplicate_patterns(patterns)

    def _classify_signal_quality(self, vol_surge: bool, rr_ratio: float,
                                  drop_pct: float, recovery_ratio: float,
                                  is_sharp: bool) -> str:
        """
        呬爛面过滤器 — 基本面 vs 呬爛面
        ==================================
        蔡森第462集核心观点:
        - 呬爛面 (Bluff): 没有量能配合的假突破, 风险回报比差
        - 基本面 (Real): 量价配合, 结构完整, 风险回报比 >= 3:1

        判定标准:
        - 基本面: 量能配合 + R:R >= 2 + 跌幅 >= 8% + 反弹超50%
        - 呬爛面: 量能不足 或 R:R < 1.5 或 跌幅太浅
        """
        score = 0

        # 量能配合 (最重要)
        if vol_surge:
            score += 3
        else:
            score -= 2

        # 风险回报比
        if rr_ratio >= 3.0:
            score += 3
        elif rr_ratio >= 2.0:
            score += 2
        elif rr_ratio >= 1.5:
            score += 1
        else:
            score -= 1

        # 跌幅深度
        if drop_pct >= 0.15:
            score += 2
        elif drop_pct >= 0.08:
            score += 1
        elif drop_pct < 0.05:
            score -= 1

        # 反弹力度
        if recovery_ratio >= 0.6:
            score += 2
        elif recovery_ratio >= 0.4:
            score += 1
        else:
            score -= 1

        # 尖底型态加分
        if is_sharp:
            score += 1

        if score >= 5:
            return "基本面"
        elif score <= 0:
            return "呬爛面"
        else:
            return "待定"

    def _apply_quality_filter(self, patterns: List[Pattern]) -> List[Pattern]:
        """
        对所有信号应用基本面/呬爛面过滤
        对于已有的信号类型, 补充质量评估
        """
        for p in patterns:
            if p.signal_quality != "待定":
                continue

            # 基于已有参数推断
            has_vol = "放量" in p.description or "量能" in p.description
            good_rr = p.risk_reward_ratio >= 2.0
            high_conf = p.confidence >= 0.7

            if has_vol and good_rr and high_conf:
                p.signal_quality = "基本面"
            elif not has_vol or p.risk_reward_ratio < 1.5:
                p.signal_quality = "呬爛面"
            elif high_conf and good_rr:
                p.signal_quality = "基本面"
            else:
                p.signal_quality = "待定"

        return patterns

    # --------------------------------------------------------
    # 3. Volume-Price Analysis (量价分析) - Enhanced
    # --------------------------------------------------------

    def analyze_volume_price(self) -> Dict:
        """
        量价关系分析 v2
        蔡森: "量价是所有技术指标之首"
        新增: 量先价行检测、支撑/收盘价判断逻辑
        """
        df = self.data
        if len(df) < 20:
            return {"divergence": False, "trend": "unknown"}

        close = df['Close'].values
        volume = df['Volume'].values

        recent_close = close[-20:]
        prev_close = close[-40:-20] if len(close) >= 40 else close[:len(close)//2]
        recent_vol = volume[-20:]
        prev_vol = volume[-40:-20] if len(volume) >= 40 else volume[:len(volume)//2]

        price_change = (recent_close[-1] - recent_close[0]) / recent_close[0]
        vol_change = (np.mean(recent_vol) - np.mean(prev_vol)) / np.mean(prev_vol) if np.mean(prev_vol) > 0 else 0

        # 量价背离
        divergence = False
        if price_change > 0.05 and vol_change < -0.2:
            divergence = True
        elif price_change < -0.05 and vol_change > 0.3:
            divergence = True

        # 高档量价背离
        high_position = recent_close[-1] > np.percentile(close, 80)
        price_up_vol_down = price_change > 0 and vol_change < -0.15
        high_level_divergence = high_position and price_up_vol_down

        # 量先价行: 近期量能大幅增加但价格尚未大动
        volume_leads = vol_change > 0.5 and abs(price_change) < 0.05

        # 量价齐升 (健康多头)
        healthy_bullish = price_change > 0.03 and vol_change > 0.1

        return {
            "divergence": divergence,
            "high_level_divergence": high_level_divergence,
            "volume_leads_price": volume_leads,
            "healthy_bullish": healthy_bullish,
            "price_change_pct": round(price_change * 100, 2),
            "volume_change_pct": round(vol_change * 100, 2),
            "avg_recent_volume": int(np.mean(recent_vol)),
            "avg_prev_volume": int(np.mean(prev_vol)),
            "trend": "多头" if price_change > 0.02 else ("空头" if price_change < -0.02 else "盘整"),
            "warning": (
                "⚠️ 高档量价背离! 价格走高但量能萎缩，警惕假突破!" if high_level_divergence
                else "💡 量先价行! 量能先行放大，关注价格突破颈线!" if volume_leads
                else ""
            )
        }

    # --------------------------------------------------------
    # 4. Support Levels (支撑分级) - New in v2
    # --------------------------------------------------------

    def classify_support_levels(self) -> List[SupportLevel]:
        """
        支撑/压力分级
        蔡森区分: 短期强弱支撑 vs 长线大支撑
        """
        current = self._get_current_price()
        necklines = self.find_support_resistance()
        levels = []

        for n in necklines:
            if n.line_type == "support" and n.price < current:
                dist_pct = (current - n.price) / current * 100
                if dist_pct < 3:
                    level_type = "短期强支撑"
                    desc = f"距当前价 {dist_pct:.1f}%，跌破即止损"
                elif dist_pct < 10:
                    level_type = "短期弱支撑"
                    desc = f"距当前价 {dist_pct:.1f}%，正常回调区域"
                else:
                    level_type = "长线大支撑"
                    desc = f"距当前价 {dist_pct:.1f}%，底部结构重要支撑"

                levels.append(SupportLevel(
                    price=n.price, level_type=level_type,
                    description=f"{desc} (触及{n.touches}次)"
                ))
            elif n.line_type == "resistance" and n.price > current:
                dist_pct = (n.price - current) / current * 100
                if dist_pct < 3:
                    level_type = "近期压力"
                    desc = f"距当前价 {dist_pct:.1f}%，突破即买入"
                elif dist_pct < 10:
                    level_type = "中期压力"
                    desc = f"距当前价 {dist_pct:.1f}%"
                else:
                    level_type = "长线压力"
                    desc = f"距当前价 {dist_pct:.1f}%"

                levels.append(SupportLevel(
                    price=n.price, level_type=level_type,
                    description=f"{desc} (触及{n.touches}次)"
                ))

        return levels

    # --------------------------------------------------------
    # 5. Trend Analysis (趋势分析)
    # --------------------------------------------------------

    def get_trend(self, df: pd.DataFrame = None) -> str:
        """判断趋势方向"""
        if df is None:
            df = self.data
        if df is None or len(df) < 20:
            return "盘整"

        close = df['Close'].values
        ma20 = np.mean(close[-20:])
        ma60 = np.mean(close[-60:]) if len(close) >= 60 else ma20
        current = close[-1]

        if current > ma20 > ma60:
            return "多头"
        elif current < ma20 < ma60:
            return "空头"
        else:
            return "盘整"

    # --------------------------------------------------------
    # Full Analysis (完整分析)
    # --------------------------------------------------------

    def analyze(self, symbol: str = None) -> AnalysisResult:
        """执行完整分析 v2"""
        if symbol and self.data is None:
            self.fetch_data(symbol)

        sym = symbol or self.symbol
        current = self._get_current_price()

        # 量价分析
        vp = self.analyze_volume_price()

        # 型态识别 (含周线)
        raw_patterns = self.detect_patterns()
        patterns = self._deduplicate_patterns(raw_patterns)

        # 支撑分级
        support_levels = self.classify_support_levels()

        # 趋势
        daily_trend = self.get_trend()
        weekly_trend = self.get_trend(self.weekly_data) if self.weekly_data is not None else "N/A"

        # 关键支撑/压力
        supports = [sl for sl in support_levels if "支撑" in sl.level_type]
        resistances = [sl for sl in support_levels if "压力" in sl.level_type]

        key_support = max(supports, key=lambda x: x.price).price if supports else None
        key_resistance = min(resistances, key=lambda x: x.price).price if resistances else None
        long_term = [sl for sl in support_levels if "长线" in sl.level_type and "支撑" in sl.level_type]
        long_term_support = min(long_term, key=lambda x: x.price).price if long_term else None

        # 生成摘要
        lines = []
        lines.append(f"📊 {sym} 蔡森技术分析报告 v2.1")
        lines.append(f"📅 分析日期: {datetime.now().strftime('%Y-%m-%d')}")
        lines.append(f"💰 当前价格: {current:.2f}")
        lines.append(f"📈 日线趋势: {daily_trend} | 周线趋势: {weekly_trend}")
        lines.append(f"📉 量价变化: 价格 {vp.get('price_change_pct', 0):+.1f}%, 量能 {vp.get('volume_change_pct', 0):+.1f}%")

        if key_support:
            lines.append(f"🟢 短期支撑: {key_support:.2f}")
        if key_resistance:
            lines.append(f"🔴 近期压力: {key_resistance:.2f}")
        if long_term_support:
            lines.append(f"🟢 长线大支撑: {long_term_support:.2f}")

        if vp.get('warning'):
            lines.append(vp['warning'])

        # 量价背離警告
        divergence_patterns = [p for p in patterns
                               if p.pattern_type in (SignalType.VOL_PRICE_DIVERGENCE_UP,
                                                      SignalType.VOL_PRICE_DIVERGENCE_DOWN)]
        if divergence_patterns:
            lines.append(f"\n⚡ 量价背離检测到 {len(divergence_patterns)} 个信号!")

        if patterns:
            lines.append(f"\n🔍 发现 {len(patterns)} 个交易信号:")
            for p in patterns:
                LONG_SIGNALS = {"破底翻", "W底", "头肩底", "岛型反转(底)", "量先价行",
                                "颈线突破", "回踩支撑", "真突破", "底部放量突破",
                                "V型反转", "量价背离(上行)"}
                SHORT_SIGNALS = {"假突破", "头肩顶", "M顶", "岛型反转(顶)",
                                 "颈线跌破", "反弹无力", "跌破支撑",
                                 "量价背离(下行)"}
                if p.pattern_type.value in LONG_SIGNALS:
                    emoji = "🟢"
                elif p.pattern_type.value in SHORT_SIGNALS:
                    emoji = "🔴"
                else:
                    emoji = "⚪"

                tf_tag = "【周线】" if p.timeframe == "weekly" else ""

                # 基本面/呬爛面标签
                quality_tag = ""
                if p.signal_quality == "基本面":
                    quality_tag = " ✅基本面"
                elif p.signal_quality == "呬爛面":
                    quality_tag = " ⚠️呬爛面"
                elif p.signal_quality == "待定":
                    quality_tag = " ❓待定"

                # V型反转概率
                v_prob = ""
                if p.v_reversal_probability is not None:
                    v_prob = f" | V型概率: {p.v_reversal_probability:.0%}"

                lines.append(
                    f"  {emoji} {tf_tag}{p.pattern_type.value} (置信度: {p.confidence:.0%}){quality_tag}{v_prob}\n"
                    f"     颈线: {p.neckline} | 入场: {p.entry_price} | "
                    f"止损: {p.stop_loss}\n"
                    f"     目标1: {p.target_price} | 目标2: {p.target_price_2} (黄金比例)\n"
                    f"     风险回报比: 1:{p.risk_reward_ratio:.1f}\n"
                    f"     {p.description}"
                )
        else:
            lines.append("\n🔍 当前无明确型态信号，建议等待")

        lines.append("\n💡 蔡森三心法则:")
        lines.append("   耐心 — 等待型态完成")
        lines.append("   决心 — 信号出现果断进场")
        lines.append("   平常心 — 设好止损，不焦虑短线震荡")
        lines.append("\n📌 蔡森提醒:")
        lines.append("   • 破底翻大都会越过前高")
        lines.append("   • 利空时看收盘价判断支撑，无利空时盘中破就跑")
        lines.append("   • 量价是所有技术指标之首")
        lines.append("   • 基本面信号可信, 呬爛面信号要小心!")
        lines.append("   • V型反转看概率, 量价配合是关键 (第462集)")

        # 统计基本面/呬爛面
        real_signals = [p for p in patterns if p.signal_quality == "基本面"]
        bluff_signals = [p for p in patterns if p.signal_quality == "呬爛面"]
        if real_signals or bluff_signals:
            lines.append(f"\n🏷️ 信号质量: ✅基本面 {len(real_signals)} | ⚠️呬爛面 {len(bluff_signals)}")

        return AnalysisResult(
            symbol=sym,
            analysis_date=datetime.now().strftime('%Y-%m-%d'),
            current_price=current,
            current_trend=daily_trend,
            daily_trend=daily_trend,
            weekly_trend=weekly_trend,
            patterns=patterns,
            support_levels=support_levels,
            volume_price_divergence=vp.get('divergence', False),
            volume_leads_price=vp.get('volume_leads_price', False),
            key_support=key_support,
            key_resistance=key_resistance,
            long_term_support=long_term_support,
            summary="\n".join(lines)
        )

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def _deduplicate_patterns(self, patterns: List[Pattern]) -> List[Pattern]:
        """去重，只保留最近期、最高质量的信号"""
        if not patterns:
            return patterns

        patterns.sort(key=lambda x: (x.signal_date, -x.confidence), reverse=True)

        clusters = []
        for p in patterns:
            found = False
            for cluster in clusters:
                representative = cluster[0]
                if (p.pattern_type == representative.pattern_type and
                    abs(p.neckline - representative.neckline) / representative.neckline < 0.01):
                    cluster.append(p)
                    found = True
                    break
            if not found:
                clusters.append([p])

        result = [max(cluster, key=lambda x: x.confidence) for cluster in clusters]

        # 周线信号优先保留, 然后按置信度排序
        weekly = [p for p in result if p.timeframe == "weekly"]
        daily = [p for p in result if p.timeframe == "daily"]
        daily.sort(key=lambda x: x.confidence, reverse=True)

        final = weekly + daily[:3]
        return final


# ============================================================
# Watchlist Scanner (多股扫描)
# ============================================================

class WatchlistScanner:
    """批量扫描观察清单"""

    def __init__(self, symbols: List[str]):
        self.symbols = symbols

    def scan(self) -> List[AnalysisResult]:
        """扫描所有标的"""
        results = []
        for sym in self.symbols:
            try:
                analyzer = CaiSenAnalyzer()
                analyzer.fetch_data(sym)
                result = analyzer.analyze()
                if result.patterns:
                    results.append(result)
                    print(f"✅ {sym}: 发现 {len(result.patterns)} 个信号")
                else:
                    print(f"⚪ {sym}: 无信号")
            except Exception as e:
                print(f"❌ {sym}: {e}")
        return results


# ============================================================
# Main Entry Point
# ============================================================

def main():
    """命令行入口"""
    if len(sys.argv) < 2:
        print("蔡森技术分析工具 v2.0")
        print("=" * 50)
        print("用法:")
        print("  python cai_sen_analyzer.py <股票代码>")
        print("  python cai_sen_analyzer.py <股票代码1> <股票代码2> ...")
        print("")
        print("示例:")
        print("  python cai_sen_analyzer.py 2330.TW      # 台积电")
        print("  python cai_sen_analyzer.py AAPL          # 苹果")
        print("  python cai_sen_analyzer.py 600519.SS     # 贵州茅台")
        print("  python cai_sen_analyzer.py 000001.SZ     # 平安银行")
        print("  python cai_sen_analyzer.py 0700.HK       # 腾讯")
        print("")
        print("v2.0 新增:")
        print("  ⭐ 周线破底翻/假突破 (量先价行上档无压)")
        print("  ⭐ 岛型反转检测")
        print("  ⭐ 量先价行信号")
        print("  ⭐ 支撑分级 (短期/长线)")
        print("  ⭐ 双目标计算 (涨幅满足 + 黄金比例)")
        print("  ⭐ 日线+周线多时间框架分析")
        sys.exit(0)

    symbols = sys.argv[1:]

    if len(symbols) == 1:
        analyzer = CaiSenAnalyzer()
        print(f"🔄 正在获取 {symbols[0]} 数据...")
        analyzer.fetch_data(symbols[0])
        print(f"📊 正在分析 (日线 + 周线)...")
        result = analyzer.analyze()
        print("\n" + result.summary)

        # JSON output
        print("\n📋 详细数据 (JSON):")
        output = {
            "symbol": result.symbol,
            "date": result.analysis_date,
            "price": result.current_price,
            "daily_trend": result.daily_trend,
            "weekly_trend": result.weekly_trend,
            "support": result.key_support,
            "resistance": result.key_resistance,
            "long_term_support": result.long_term_support,
            "divergence": bool(result.volume_price_divergence),
            "volume_leads_price": bool(result.volume_leads_price),
            "patterns": [
                {
                    "type": p.pattern_type.value,
                    "timeframe": p.timeframe,
                    "confidence": p.confidence,
                    "neckline": p.neckline,
                    "entry": p.entry_price,
                    "stop_loss": p.stop_loss,
                    "target": p.target_price,
                    "target_2": p.target_price_2,
                    "risk_reward": p.risk_reward_ratio,
                    "description": p.description
                }
                for p in result.patterns
            ]
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"🔍 开始扫描 {len(symbols)} 个标的...")
        print("=" * 50)
        scanner = WatchlistScanner(symbols)
        results = scanner.scan()
        print("\n" + "=" * 50)
        print(f"📊 扫描完成: {len(results)} 个标的有信号")
        for r in results:
            print(f"\n{'='*50}")
            print(r.summary)


if __name__ == "__main__":
    main()
