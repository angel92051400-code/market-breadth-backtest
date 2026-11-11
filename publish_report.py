"""Prepare the latest completed backtest report for static GitHub Pages hosting."""
from __future__ import annotations
import html
import json
import shutil
from pathlib import Path


def display(value, digits=2, suffix=""):
    if value is None:
        return "—"
    return f"{value:,.{digits}f}{suffix}"


def generate(source=Path("output"), dest=Path("docs")):
    source, dest = Path(source), Path(dest)
    payload = json.loads((source / "summary.json").read_text(encoding="utf-8"))
    rows = payload["results"]
    dest.mkdir(parents=True, exist_ok=True)
    files = [
        "report.html",
        "summary.json",
        "summary.csv",
        "signal_diagnostics.csv",
        "trades_A.csv",
        "trades_B.csv",
        "equity_A.csv",
        "equity_B.csv",
    ]
    for filename in files:
        file = source / filename
        if not file.is_file():
            raise FileNotFoundError(f"Missing backtest output: {file}")
        shutil.copyfile(file, dest / filename)
    (dest / ".nojekyll").write_text("", encoding="utf-8")

    ticker = html.escape(str(payload.get("ticker", "0050.TW")))
    config = payload["config"]
    snapshot = html.escape(str(payload["source"].get("snapshot_date", "—")))
    body_rows = "\n".join(
        "<tr>"
        f"<td>策略 {html.escape(str(r['strategy']))}</td>"
        f"<td>{r['completed_trades']}</td>"
        f"<td>{display(r['win_rate_pct'],1,'%')}</td>"
        f"<td>{display(r['strategy_return_pct'],2,'%')}</td>"
        f"<td>{display(r['max_drawdown_pct'],2,'%')}</td>"
        f"<td>{display(r['buy_hold_return_pct'],2,'%')}</td>"
        "</tr>"
        for r in rows
    )
    links = "".join(
        f'<a href="{html.escape(name)}" download>{html.escape(name)}</a>'
        for name in files if name != "report.html"
    )
    page = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>市場寬度策略回測｜0050</title>
<style>
:root{{color-scheme:dark}}
*{{box-sizing:border-box}}
body{{background:#10141d;color:#e5eaf3;font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:0}}
main{{max-width:1320px;margin:auto;padding:26px 18px 48px}}
h1{{font-size:26px;margin:4px 0 6px}}
h2{{font-size:18px}}
p,.muted{{color:#a6b3c6}}
.panel{{background:#1a2030;border:1px solid #364154;border-radius:14px;padding:17px;margin:16px 0}}
.warn{{border-left:4px solid #f7b955}}
.table-wrap{{overflow-x:auto}}
table{{border-collapse:collapse;width:100%;min-width:610px}}
th,td{{padding:12px;text-align:right;border-bottom:1px solid #364154}}
th:first-child,td:first-child{{text-align:left}}
th{{color:#a6b3c6;font-weight:600}}
iframe{{width:100%;min-height:820px;border:0;background:#14171d;border-radius:10px}}
a{{color:#8ac4ff}}
.files{{display:flex;gap:10px;flex-wrap:wrap}}
.files a{{padding:5px 10px;border:1px solid #495b74;border-radius:8px;text-decoration:none}}
@media(max-width:640px){{iframe{{min-height:760px}} h1{{font-size:22px}}}}
</style>
</head>
<body><main>
<p class="muted">獨立研究專案 · 使用交易日資料、隔日開盤成交</p>
<h1>台股市場寬度 × 費波那契策略回測</h1>
<p>標的 {ticker}　|　市場資料截至 {snapshot}　|　買進門檻 {config['buy']:g}%　|　賣出門檻 {config['sell']:g}%</p>
<section class="panel warn">
<strong>研究用途，非投資建議</strong>
<p>2025 年資料缺漏或歷史成分股回推可能影響結果。交易筆數極少時，勝率不具統計意義。
本模型僅在收盤後計算訊號，隔日開盤假設成交；以調整後價格估算，非可保證成交的實際報酬。
目前資料使用當前前 640 大股票回推，存在存活者偏差。</p>
</section>
<section class="panel">
<h2>策略績效比較</h2>
<div class="table-wrap"><table>
<thead><tr><th>策略</th><th>完成交易</th><th>勝率</th><th>策略總報酬</th><th>最大回撤</th><th>0050 持有報酬*</th></tr></thead>
<tbody>{body_rows}</tbody></table></div>
<p class="muted">* 比較基準與策略期間一致；請以逐筆交易及每日資金曲線核對所有結果，未平倉不列入已完成交易勝率。</p>
</section>
<section class="panel">
<h2>互動圖表</h2>
<iframe src="report.html" title="策略回測互動圖表" loading="lazy"></iframe>
<p><a href="report.html" target="_blank" rel="noopener">另開完整互動圖表</a></p>
</section>
<section class="panel">
<h2>下載資料與診斷</h2>
<div class="files">{links}</div>
</section>
</main></body></html>"""
    (dest / "index.html").write_text(page, encoding="utf-8")
    print(f"Static report prepared: {dest / 'index.html'} and {len(files)} data files")


if __name__ == "__main__":
    generate()
