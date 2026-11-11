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
    files = ["report.html", "summary.json", "summary.csv", "signal_diagnostics.csv"]
    for strategy in ("A", "B", "C", "A2", "B2", "C2"):
        files.extend((f"trades_{strategy}.csv", f"equity_{strategy}.csv"))
    for filename in files:
        file = source / filename
        if not file.is_file():
            raise FileNotFoundError(f"Missing backtest output: {file}")
        shutil.copyfile(file, dest / filename)
    (dest / ".nojekyll").write_text("", encoding="utf-8")

    strategy_desc = (
        '<p><strong>A｜純市場寬度</strong>：過冷後回升買進、上穿過熱門檻賣出。</p>'
        '<p><strong>B｜純費波那契</strong>：價格向上收復過去 120 日費波那契支撐，'
        '隔日買進；依訊號當日固定的下一級壓力目標或支撐失效價位出場，不使用市場寬度。</p>'
        '<p><strong>C｜綜合策略</strong>：過冷回升後五日內且接近費波那契價位買進；'
        '市場寬度上穿過熱門檻賣出。</p>'
        '<p><strong>A2｜寬度波段</strong>：上穿40%進場；失守40%、達65%或30交易日退出。</p>'
        '<p><strong>B2｜費波那契反彈</strong>：靠近支撐且止跌反彈買進；回落6%、支撐失效或45交易日退出。</p>'
        '<p><strong>C2｜綜合波段</strong>：寬度上穿40%且高於費波那契50%價位買進；'
        '寬度失守、指數跌破Fib50%或45交易日退出。</p>'
    )
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
        f"<td>{display(r.get('exposure_pct'),1,'%')}</td>"
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
iframe{{width:100%;min-height:1100px;border:0;background:#14171d;border-radius:10px}}
a{{color:#8ac4ff}}
.files{{display:flex;gap:10px;flex-wrap:wrap}}
.files a{{padding:5px 10px;border:1px solid #495b74;border-radius:8px;text-decoration:none}}
@media(max-width:640px){{iframe{{min-height:960px}} h1{{font-size:22px}}}}
</style>
</head>
<body><main>
<p class="muted">獨立研究專案 · 使用交易日資料、隔日開盤成交</p>
<h1>台股市場寬度 × 費波那契策略回測</h1>
<p>標的 {ticker}　|　市場資料截至 {snapshot}　|　首筆資料 {html.escape(str(rows[0].get('first_date', '—')))}　|　末筆資料 {html.escape(str(rows[0].get('last_date', '—')))}　|　原版買進門檻 {config['buy']:g}%　|　賣出門檻 {config['sell']:g}%</p>
<section class="panel warn">
<strong>研究用途，非投資建議</strong>
<p>2025 年資料缺漏或歷史成分股回推可能影響結果。交易筆數極少時，勝率不具統計意義。
本模型僅在收盤後計算訊號，隔日開盤假設成交；以調整後價格估算，非可保證成交的實際報酬。
目前資料使用當前前 640 大股票回推，存在存活者偏差。</p>
</section>
<section class="panel">
<h2>六組策略規則（原版 A/B/C＋新增 A2/B2/C2）</h2>
{strategy_desc}
</section>
<section class="panel">
<h2>策略績效比較</h2>
<div class="table-wrap"><table>
<thead><tr><th>策略</th><th>完成交易</th><th>勝率</th><th>策略總報酬</th><th>最大回撤</th><th>持倉比例</th><th>0050 持有報酬*</th></tr></thead>
<tbody>{body_rows}</tbody></table></div>
<p class="muted">* 相同期間的 0050 持有基準。持倉比例指有部位的交易日占比；未平倉不計入完成交易與勝率，但包含期末總報酬。六組策略屬預先指定的研究假設，並非最適化結果。資料從目前來源最早日期開始；費波那契須先累積120個已完成交易日才有訊號。</p>
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
