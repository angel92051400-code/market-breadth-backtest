# 台股市場寬度 × 費波那契獨立回測

此專案獨立於 `my-market-breadth` 監控網站，不會修改其內容。從網站 `index.html` 取得市場寬度及加權指數歷史 OHLC，另外下載 0050 ETF 價格，以訊號隔日成交比較 A、B 策略。

## 策略
- A：市場寬度從 ≤20% 回升到 >20% 進場；從 <70% 上穿 70% 出場。
- B：A 的回升訊號在近 5 個交易日出現，且加權指數收盤價距離過去 120 交易日的費波那契 38.2%、50%、61.8% 之一不超過 3% 才進場；出場同 A。
- 進出場訊號皆於收盤後確認，在下一個共同交易日開盤執行；不使用未來高低點。

## 使用方式
1. GitHub Actions → Manual Strategy Backtest → Run workflow。
2. 輸入買進／賣出市場寬度門檻（預設 20／70）。
3. 完成後下載 Actions 的 `strategy-backtest-report`，打開 `report.html`。
4. 下載包包含 `summary.csv`、`summary.json`、`trades_A.csv`、`trades_B.csv`、`equity_A.csv`、`equity_B.csv` 與 `signal_diagnostics.csv`。

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