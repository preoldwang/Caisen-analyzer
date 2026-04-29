# 蔡森技術分析全台股掃描器

每日自動掃描全台股（上市＋上櫃 ~1,957 檔），以蔡森 12 招型態識別交易訊號。

## 📊 報告網址

| 頁面 | 連結 |
|---|---|
| 今日報告 | [preoldwang.github.io/Caisen-analyzer](https://preoldwang.github.io/Caisen-analyzer/) |
| 歷史報告 | [preoldwang.github.io/Caisen-analyzer/history.html](https://preoldwang.github.io/Caisen-analyzer/history.html) |

## ⚙️ 系統功能

- 每日 15:35 自動觸發，國定假日自動跳過
- Matrix 4 平行掃描，約 20 分鐘完成
- 富邦 Neo API 橋接對應權證（價外10–20%、剩餘≥60天、均量≥200張）
- Supabase 歷史資料庫，追蹤訊號持續天數
- 訊號標示：🆕 新訊號 / 🔁 持續2天 / 🔥 持續3天以上

## ⚠️ 免責聲明

本工具基於蔡森技術分析方法論，僅供學習參考，不構成任何投資建議。
