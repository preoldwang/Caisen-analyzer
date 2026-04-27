# Analyzer Configuration Backup
> Generated: 2026-04-27
> Purpose: Document all analyzer/backtest parameters for reproducibility

---

## 1. backtest_po_di_fan_smart.py (Smart Backtest - Top 2 + Filters)

```python
# Backtest Period
BACKTEST_START = "2019-01-01"
BACKTEST_END = "2026-03-31"

# Selection
TOP_N = 2                    # Top picks per month
MAX_HOLD_DAYS = 30           # Max holding period

# Signal Quality Filters
MIN_CONFIDENCE = 0.7         # Minimum confidence score
MIN_RR = 3.0                 # Minimum risk-reward ratio

# Technical Filters
REQUIRE_VOLUME = True        # Require volume confirmation
REQUIRE_MA_UPTREND = True    # Require MA uptrend
MA_PERIOD = 20               # Moving average period

# Market Filter
MARKET_FILTER = True         # Skip if HSI below 60-day MA (bear filter)
MIN_AVG_VOLUME = 500_000     # Min avg daily volume (shares)
HSI_TICKER = "^HSI"          # HSI index ticker for market regime
SKIP_RECENT_MONTHS = 2       # Skip most recent months (avoid lookahead bias)
```

**Filter Logic:**
- Confidence ≥ 0.7
- Risk:Reward ≥ 3.0
- Volume confirmation (recent > avg * 1.2)
- MA uptrend (MA20 rising)
- Liquidity: avg volume > 500K shares
- Market regime: HSI above 60-day MA

---

## 2. backtest_po_di_fan.py (Full Backtest - No Filters)

```python
# Backtest Period
BACKTEST_START = "2019-01-01"
BACKTEST_END = "2026-03-31"

# Selection
TOP_N = 2                    # Top picks per month
MAX_HOLD_DAYS = 30           # Max holding period (inferred from exit logic)
```

**Note:** This version runs all signals without quality filters.

---

## 3. podifan_analyzer.py (Core Po Di Fan Detector)

```python
# Pattern Detection
# Lookback range: 60, 90, 120 days
# Neckline: 60th percentile of recovery highs after bottom
# Break below threshold: price < min_price * 0.985 (1.5% below bottom)
# Recovery check: price > neckline in last 5 bars

# Entry/Exit
entry = open_prices[end_idx]    # Next day's Open (FIXED 2026-04-27)
stop_loss = min_price * 0.96    # 4% below bottom
target_1 = max(neckline + distance, pre_high)
target_2 = neckline + distance * 1.618

# Signal Quality
# Min confidence: 0.65
# Min R:R ratio: 2.0
# Volume confirmation: recent > avg * 1.3
# RSI confirmation: < 40 (+0.10), < 50 (+0.05)
# MACD turning: +0.08
# Up streak >= 2: +0.08
# R:R >= 3: +0.07
```

---

## 4. cai_sen_analyzer.py (Full Cai Sen Pattern Suite)

### Pattern Types Detected:
| Pattern | Chinese | Direction |
|---------|---------|-----------|
| PO_DI_FAN | 破底翻 | Long |
| JIA_TU_PO | 假突破 | Long |
| ZHEN_XIAN_DIE_PO | 颈线跌破 | Short |
| HEAD_SHOULDER_TOP | 头肩顶 | Short |
| HEAD_SHOULDER_BOTTOM | 头肩底 | Long |
| W_BOTTOM | W底 | Long |
| M_TOP | M顶 | Short |
| ISLAND_REVERSAL_TOP | 岛型反转(顶) | Short |
| ISLAND_REVERSAL_BOTTOM | 岛型反转(底) | Long |
| VOLUME_LEADS_PRICE | 量先价行 | Bullish |
| HUI_CAI_ZHI_CHENG | 回踩支撑 | Long |
| FAN_TAN_WU_LI | 反弹无力 | Short |
| DIE_PO_ZHI_CHENG | 跌破支撑 | Short |
| V_REVERSAL | V型反转 | Long/Short |
| VOL_PRICE_DIVERGENCE_UP | 量价背离(上行) | Bullish |
| VOL_PRICE_DIVERGENCE_DOWN | 量价背离(下行) | Bearish |
| KANGBO_CYCLE_UP | 康波上行期 | Long Macro |
| KANGBO_CYCLE_DOWN | 康波下行期 | Bearish Macro |
| EIGHT_YEAR_CYCLE | 八年循环转折 | Turning Point |
| MONTHLY_EXHAUSTION_UP | 月线爆量翻黑 | Short |
| MONTHLY_EXHAUSTION_DOWN | 月线缩量见底 | Long |
| NECKLINE_BATTLE | 颈线割喉战 | Zone |
| BANGCON_SHORT | 棒康空点 | Short |
| BANGCON_LONG | 棒康多点 | Long |
| LOG_SCALE_TARGET | 对数图量幅 | Target |
| MONTHLY_HEAD_SHOULDER | 月线头肩型态 | Pattern |

### Lookback Periods:
- Daily patterns: 60, 90, 120 days
- Weekly patterns: uses `self.weekly_data`
- Monthly analysis: uses `self.monthly_data`

### Entry Price (FIXED 2026-04-27):
```python
# All patterns now use:
entry = open_prices[end_idx]  # Next day's Open price
```

---

## 5. focused_backtest.py (Focused Instrument Backtest)

```python
# Target Instruments
INSTRUMENTS = {
    # HK blue chips + gold futures
}

# Signal Filter
BULLISH_SIGNALS = {"破底翻", "月线缩量见底"}

# Cutoff dates for rolling backtests
CUTOFF_DATES = [...]

# Entry Price (FIXED 2026-04-27):
entry = open_prices[end_idx]  # Next day's Open price
stop_loss = min_price * 0.96
```

---

## 6. podifan_v2.py (Smart Signal Runner)

```python
# Blue chip universe
BLUE_CHIPS = {...}  # Full list of HK blue chips

# Verification periods
VERIFY_1M = 22      # ~1 month trading days
VERIFY_3M = 66      # ~3 months trading days

# Bullish signal types
BULLISH = {"破底翻", "W底", "头肩底", "岛型反转(底)", "量先价行", ...}

# Cutoff dates
CUTOFF_DATES = [...]
```

---

## Critical Fix Applied (2026-04-27)

### Bug: `entry = neckline` used theoretical pattern level as entry price
- Neckline was often unreachable on entry date
- 68.4% of trades in full backtest had impossible entry prices
- Caused cumulative returns to show +421% instead of actual -89%

### Fix: `entry = open_prices[end_idx]`
- Uses actual next-day Open price for realistic execution
- Applied to all 5 analyzer files (14 total occurrences)
- Corrected HTML reports generated and pushed to GitHub

### Files Modified:
1. `podifan_analyzer.py` - 1 fix
2. `backtest_po_di_fan.py` - 1 fix
3. `backtest_po_di_fan_smart.py` - 1 fix
4. `focused_backtest.py` - 1 fix
5. `cai_sen_analyzer.py` - 10 fixes
