#!/usr/bin/env python3
"""
權證橋接模組 — 正股訊號 → 對應權證篩選
篩選條件（依使用者設定）：
  - 類型：一般型認購權證
  - 價內外：價外 10%–20%
  - 剩餘天數：≥ 60 天
  - 權證價格：0.8–1.5 元
  - 5日均量：≥ 200 張
"""
import os, json, base64, tempfile
from datetime import datetime, date

def get_fubon_sdk():
    """初始化富邦 SDK，從環境變數讀取憑證"""
    try:
        from fubon_neo.sdk import FubonSDK
    except ImportError:
        print("  [警告] fubon_neo 未安裝，跳過權證橋接")
        return None

    api_key   = os.environ.get("FAK", "")
    cert_b64  = os.environ.get("FS89", "")
    cert_pass = os.environ.get("FP", "")

    if not all([api_key, cert_b64, cert_pass]):
        print("  [警告] 富邦 API 環境變數未設定，跳過權證橋接")
        return None

    # 將 base64 憑證解碼為暫存 .p12 檔案
    cert_bytes = base64.b64decode(cert_b64)
    tmp = tempfile.NamedTemporaryFile(suffix=".p12", delete=False)
    tmp.write(cert_bytes)
    tmp.close()

    try:
        sdk = FubonSDK()
        sdk.apikey_login(
            os.environ.get("FUBON_ID", ""),  # 身分證字號（選填，部分版本不需要）
            api_key,
            tmp.path,
            cert_pass
        )
        return sdk
    except Exception as e:
        print(f"  [警告] 富邦登入失敗: {e}")
        return None
    finally:
        os.unlink(tmp.name)

def filter_warrants(warrants, underlying_price):
    """
    套用篩選條件：
      - 一般型（非可展延）
      - 認購（Call）
      - 價外 10%–20%（履約價 / 現價 = 1.10–1.20）
      - 剩餘天數 ≥ 60
      - 權證價格 0.8–1.5 元
      - 5日均量 ≥ 200 張
    """
    results = []
    today = date.today()

    for w in warrants:
        try:
            # 型態：一般型認購
            if w.get("type") not in ("CALL", "認購"):
                continue
            if w.get("is_extendable", False):
                continue

            # 剩餘天數
            exp = w.get("expiration_date", "")
            if exp:
                exp_date = datetime.strptime(exp[:10], "%Y-%m-%d").date()
                days_left = (exp_date - today).days
                if days_left < 60:
                    continue
            else:
                continue

            # 履約價 / 正股現價 → 價外比例
            strike = float(w.get("strike_price", 0) or 0)
            if strike <= 0 or underlying_price <= 0:
                continue
            moneyness = strike / underlying_price
            if not (1.10 <= moneyness <= 1.20):
                continue

            # 權證市價
            price = float(w.get("close_price", 0) or w.get("last_price", 0) or 0)
            if not (0.8 <= price <= 1.5):
                continue

            # 5日均量（張）
            vol5 = float(w.get("volume_5d_avg", 0) or 0)
            if vol5 < 200:
                continue

            results.append({
                "code":        w.get("symbol", ""),
                "name":        w.get("name", ""),
                "issuer":      w.get("issuer", ""),
                "price":       round(price, 2),
                "strike":      round(strike, 2),
                "moneyness":   f"價外{(moneyness-1)*100:.1f}%",
                "days_left":   days_left,
                "vol5":        int(vol5),
                "exp_date":    exp[:10],
            })
        except Exception:
            continue

    # 排序：5日均量由高到低（流動性優先）
    results.sort(key=lambda x: x["vol5"], reverse=True)
    return results[:5]  # 最多回傳 5 檔

def find_warrants_for_signals(signals):
    """
    主入口：對每個正股訊號查詢對應權證
    回傳：{ticker: [warrant_list]}
    """
    sdk = get_fubon_sdk()
    warrant_map = {}

    if sdk is None:
        # 無法連線時，回傳空字典（報告仍可正常產出，只是沒有權證欄位）
        return warrant_map

    try:
        sdk.init_realtime()
        # 取得全部上市認購權證
        all_warrants = sdk.marketdata.rest_client.stock.tickers(
            type="WARRANT", exchange="TWSE"
        )
        print(f"  富邦 API：取得 {len(all_warrants)} 檔權證")
    except Exception as e:
        print(f"  [警告] 取得權證清單失敗: {e}")
        return warrant_map

    for signal in signals:
        ticker = signal["ticker"].replace(".TW", "").replace(".TWO", "")
        entry  = signal.get("entry", 0)

        # 篩選對應正股的權證
        underlying_warrants = [
            w for w in all_warrants
            if str(w.get("underlying_symbol", "")) == ticker
        ]

        if underlying_warrants:
            filtered = filter_warrants(underlying_warrants, entry)
            if filtered:
                warrant_map[signal["ticker"]] = filtered
                print(f"  {signal['name']}({ticker}): {len(filtered)} 檔符合條件的權證")

    return warrant_map

if __name__ == "__main__":
    # 測試用
    test_signals = [{"ticker": "2330.TW", "name": "台積電", "entry": 850.0}]
    result = find_warrants_for_signals(test_signals)
    print(json.dumps(result, ensure_ascii=False, indent=2))
