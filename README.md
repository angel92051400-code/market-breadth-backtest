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
- 不排程每天運行，僅手動回測。