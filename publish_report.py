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
    for strategy in ("A", "B", "C", "A2", "B2", "C2", "B3", "DCA"):
        files.extend((f"trades_{strategy}.csv", f"equity_{strategy}.csv"))
        files.extend((f"trades_00631L_{strategy}.csv", f"equity_00631L_{strategy}.csv"))
    files.append("comparison_00631L.json")
    for filename in files:
        file = source / filename
        if not file.is_file():
            raise FileNotFoundError(f"Missing backtest output: {file}")
        shutil.copyfile(file, dest / filename)
    (dest / ".nojekyll").write_text("", encoding="utf-8")

    strategy_desc = (
        '<p><strong>A｜純市場寬度</strong>：過冷後回升買進、上穿50%或60%分批賣出。</p>'
        '<p><strong>B｜純費波那契</strong>：價格向上收復過去 120 日費波那契支撐，'
        '隔日買進；依訊號當日固定的下一級壓力目標或支撐失效價位出場，不使用市場寬度。</p>'
        '<p><strong>C｜綜合策略</strong>：過冷回升後五日內且接近費波那契價位買進；'
        '市場寬度上穿50%或60%分批賣出。</p>'
        '<p><strong>A2｜寬度波段</strong>：上穿40%進場；失守40%、上穿50/60%或30交易日減碼。</p>'
        '<p><strong>B2｜費波那契反彈</strong>：靠近支撐且止跌反彈買進；回落6%、支撐失效或45交易日減碼。</p>'
        '<p><strong>C2｜綜合波段</strong>：寬度上穿40%且高於費波那契50%價位買進；'
        '上穿50/60%減碼；寬度失守、指數跌破Fib50%或45交易日再減碼。</p>'
        '<p><strong>B3｜寬鬆費波那契</strong>：價格上漲且距23.6/38.2/50/61.8/78.6%回撤位不超過6%買進；'
        '參考1.414倍延伸目標、支撐跌破6%或60日減碼50%。仍屬探索性策略。</p>'
    )
    leveraged=payload.get("leveraged_comparison")
    if not leveraged or leveraged.get("ticker") != "00631L.TW":
        raise ValueError("Missing true-price 00631L comparison")
    lever_rows=leveraged["results"]
    paired={r["strategy"]:r for r in lever_rows}
    combined_rows="\n".join(
        "<tr>"
        f"<td>{html.escape(str(r['strategy']))}</td>"
        f"<td>{display(r.get('invested_return_pct'),2,'%')}</td>"
        f"<td>{display(paired[r['strategy']].get('invested_return_pct'),2,'%')}</td>"
        f"<td>{display(r['max_drawdown_pct'],2,'%')}</td>"
        f"<td>{display(paired[r['strategy']]['max_drawdown_pct'],2,'%')}</td>"
        f"<td>{int(r.get('buy_orders',0))} / {int(paired[r['strategy']].get('buy_orders',0))}</td>"
        "</tr>" for r in rows
    )
    leveraged_details=(
        '<p>兩檔標的使用相同市場寬度／加權指數訊號、共同交易日期、'
        '起始可用資金10萬元、訊號策略每次買進1萬元並賣出持股50%。閒置現金不計入投入報酬率。'
        '00631L是真實調整後ETF價格，不是把0050乘以二。</p>'
        '<div class="table-wrap"><table><thead><tr><th>策略</th>'
        '<th>0050投入報酬</th><th>00631L投入報酬</th><th>0050最大回撤</th>'
        '<th>00631L最大回撤</th><th>買入筆數 0050 / 00631L</th>'
        '</tr></thead><tbody>'+combined_rows+'</tbody></table></div>'
        f'<p>共同交易區間：{html.escape(leveraged["first_date"])}～'
        f'{html.escape(leveraged["last_date"])}（{leveraged["matched_dates"]}天）。'
        '00631L以臺灣50單日兩倍漲跌為目標；長期報酬並不等於0050報酬的兩倍，'
        '且可能有顯著放大回撤與波動耗損。須符合槓桿ETF適格條件。</p>'
    )
    dca = next((r for r in rows if r['strategy'] == 'DCA'), None)
    if dca is None:
        raise ValueError("Missing monthly DCA summary")
    strategy_desc += (
        '<p><strong>0050 月初定期定額</strong>：每個月 1 日（休市順延下一個交易日）'
        '買進3,000元。公平比較版本使用與六組策略相同的初始10萬元，從現金扣除；'
        '一般定期定額則每月另存3,000元，獨立顯示累計投入與XIRR。</p>'
    )
    ticker = html.escape(str(payload.get("ticker", "0050.TW")))
    config = payload["config"]
    snapshot = html.escape(str(payload["source"].get("snapshot_date", "—")))
    body_rows = "\n".join(
        "<tr>"
        f"<td>{'0050 月初定期定額' if r['strategy']=='DCA' else '策略 ' + html.escape(str(r['strategy']))}</td>"
        f"<td>{r.get('buy_orders', 0)}</td>"
        f"<td>{r.get('sell_orders', 0)}</td>"
        f"<td>{display(r.get('win_rate_pct'),1,'%')}</td>"
        f"<td>NT$ {display(r.get('total_invested'),0)}</td>"
        f"<td>NT$ {display(r.get('trading_profit'),0)}</td>"
        f"<td>{display(r.get('invested_return_pct'),2,'%')}</td>"
        f"<td>{display(r['max_drawdown_pct'],2,'%')}</td>"
        f"<td>{display(r.get('exposure_pct'),1,'%')}</td>"
        f"<td>{display(r.get('buy_hold_return_pct'),2,'%')}</td>"
        "</tr>"
        for r in rows
    )
    dca_details = (
        '<div class="table-wrap"><table>'
        '<thead><tr><th>定期定額版本</th><th>累計投入</th><th>期末持股市值</th>'
        '<th>期末現金（備註）</th><th>期末總資產（備註）</th><th>淨投資損益</th><th>投入報酬率</th></tr></thead>'
        '<tbody><tr><td>同資金：起始10萬元，每月扣3,000</td>'
        f'<td>NT$ {display(dca["total_invested"],0)}</td>'
        f'<td>NT$ {display(dca["ending_market_value"],0)}</td>'
        f'<td>NT$ {display(dca["remaining_cash"],0)}</td>'
        f'<td>NT$ {display(dca["ending_equity"],0)}</td>'
        f'<td>NT$ {display(dca["net_profit"],0)}</td>'
        f'<td>{display(dca["invested_return_pct"],2,"%")}</td></tr>'
        '<tr><td>每月外部新存3,000</td>'
        f'<td>NT$ {display(dca["external_contributions"],0)}</td>'
        f'<td>NT$ {display(dca["external_market_value"],0)}</td>'
        '<td>NT$ 0</td>'
        f'<td>NT$ {display(dca["external_market_value"],0)}</td>'
        f'<td>NT$ {display(dca["external_profit"],0)}</td>'
        f'<td>{display(dca["external_return_on_contributions_pct"],2,"%")}</td></tr>'
        '</tbody></table></div>'
        f'<p>外部逐月投入的年化資金加權報酬（XIRR）：'
        f'<strong>{display(dca["external_xirr_pct"],2,"%")}</strong>。'
        '外部定期定額投入與反覆買賣訊號策略的投入時點不同；建議另外比較XIRR。'
        '兩種版本都包含買進手續費；股息透過調整後價格近似再投入，允許小數股。</p>'
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
<h2>七組策略＋0050 定期定額基準</h2>
{strategy_desc}
</section>
<section class="panel">
<h2>策略績效比較</h2>
<div class="table-wrap"><table>
<thead><tr><th>策略</th><th>買進次數</th><th>賣出次數</th><th>賣出獲利率</th><th>累計買進本金</th><th>淨投資損益</th><th>投入報酬率</th><th>最大回撤</th><th>持倉比例</th><th>0050 一次買入持有報酬*</th></tr></thead>
<tbody>{body_rows}</tbody></table></div>
<p class="muted">* 七組策略與定期定額使用相同期間的 0050 一次買入持有基準，因此這一欄每列相同是正常的。投入報酬率＝（累計賣出淨所得＋期末持股市值－累計買進成本）／累計買進成本，完全不計閒置現金。若賣出所得再次買進，累計買進成本會重複計入投入本金，因此這是投入週轉報酬，不是資金加權年化報酬 XIRR。持倉比例指有部位的交易日占比；獲利率按每次賣出50%所實現的盈虧計算，不是完整往返交易勝率；剩餘持股市值計入總報酬。起始可用資金100,000元（僅作現金限制，不直接計入投入報酬），七組訊號策略每次買入10,000元、每次賣出50%現有持股；定期定額每月買入3,000元。新增 B3 與其他策略屬探索性研究假設，並非最適化結果。資料從目前來源最早日期開始；費波那契須先累積120個已完成交易日才有訊號。</p>
</section>
<section class="panel">
<h2>0050 每月 1 日定期定額：兩種資金條件</h2>
{dca_details}
</section>
<section class="panel">
<h2>0050 與 00631L 正二同期間實際價格比較</h2>
{leveraged_details}
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
