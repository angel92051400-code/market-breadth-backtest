# 台股市場寬度 × 費波那契獨立回測

此專案獨立於 `my-market-breadth` 監控網站，不會修改其內容。從網站 `index.html` 取得市場寬度及加權指數歷史 OHLC，另外下載 0050 ETF 價格，以訊號隔日成交比較 A、B、C 三種策略。

## 固定網址直接查看回測報告

每次手動回測完成後，GitHub Actions 會更新 `docs/index.html`、互動圖表和 CSV。啟用 GitHub Pages 後，可以直接用固定網址查看最新結果，無須下載 Actions 附件。

**一次性啟用設定（須由儲存庫管理員在 GitHub 介面設定）**：

1. 打開本專案 **Settings → Pages**。
2. 在 **Build and deployment** 選擇 **Deploy from a branch**。
3. 選擇 **main** 分支、**/docs** 資料夾，點 **Save**。
4. 部署成功後，公開網站網址通常是 `https://angel92051400-code.github.io/market-breadth-backtest/`，請以 Settings → Pages 顯示的網站網址為準。

**隱私與方案限制**：本儲存庫已設為 Public 且使用 GitHub Pages。公開網站的回測結果與 CSV 可由任何人讀取。

## 策略
- A：市場寬度從 ≤20% 回升到 >20% 進場；從 <70% 上穿 70% 出場。
- B（純費波那契）：僅看加權指數，不讀市場寬度。以過去 120 個**已完成**交易日的高低點計算 38.2%、50%、61.8% 價位；價格由下向上收復其中一個支撐（收盤價距離支撐不超過 +3%）時，隔日買進 0050。從進場訊號當日鎖定下一級較高費波那契價位作停利、支撐下方 3% 作失效出場；條件成立隔日開盤賣出。風控判斷使用加權指數，交易標的是 0050。
- C（綜合策略）：A 的回升訊號發生後 5 個交易日內，且加權指數接近 38.2%、50%、61.8% 任一回撤價位 ±3%，隔日進場；當市場寬度從低於 70% 上穿 70% 時隔日出場。
- 進出場訊號皆於收盤後確認，在下一個共同交易日開盤執行；不使用未來高低點。

## 與市場寬度網站自動連動

GitHub Actions 每小時的第 23 分鐘檢查上游 `my-market-breadth/main/index.html` 是否有新版本。**只有來源 HTML 雜湊值與上次報告不同**，才自動重新執行 A/B/C 三組回測並更新 `docs/` 的 GitHub Pages 報告。手動 Run workflow 仍可自訂買賣門檻；上游變更後的自動回測使用固定基準 20%／70%。

GitHub 的排程可能延遲，因此這是**近即時的版本檢查**，並不是上游一更新就秒級推送。若股價下載或資料檢查失敗，上一版網頁仍會保留。報告 `summary.json` 的 `source.source_sha256` 記錄實際使用的上游 HTML 版本，便於稽核。

## 純費波那契基準策略的限制

B 的入場必須從下方重新站上過去 120 個已完成交易日形成的費波那契支撐，且價格在該線上方 3% 內；出場依進場訊號時鎖定的下一級價位或支撐下方 3%。其交易次數可能很少、空手期間較長；請不要單用總報酬或勝率判斷策略優劣，並與相同期間的 0050 持有比較。

## 使用方式
1. GitHub Actions → Manual Strategy Backtest → Run workflow。
2. 輸入買進／賣出市場寬度門檻（預設 20／70）。
3. 完成後下載 Actions 的 `strategy-backtest-report`，打開 `report.html`。
4. 下載包包含 `summary.csv`、`summary.json`、`trades_A.csv`、`trades_B.csv`、`trades_C.csv`、`equity_A.csv`、`equity_B.csv`、`equity_C.csv` 與 `signal_diagnostics.csv`。

本機：
```bash
python -m pip install -r requirements.txt
python -m pytest -q
python run_backtest.py --buy 20 --sell 70
```

## 研究限制
- 使用當前市值前 640 大回推歷史，**存在歷史成分股前視偏差與存活者偏差**。
- 2025 年資料若未修復，覆蓋率 <95% 的交易日不允許產生訊號；此段不能用插值製造訊號。
- Yahoo 調整後價格是含配息／拆分的績效代理，不是可實際成交的原始開盤價。
- 未平倉不計入勝率，並以同期間 ETF Buy & Hold 比較。
- 樣本期間短／交易筆數少，統計結果不代表策略有預測能力。
- 除手動回測外，系統每小時檢查一次市場寬度來源版本，有異動才更新回測。