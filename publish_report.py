"""Publish one unified ETF × strategy table, with no duplicate DCA panel."""
from __future__ import annotations
import html
import json
import shutil
from pathlib import Path

STRATEGY_ORDER=("A","A3","B4","C3","D","DCA","BH")
ETF_ORDER=(("0050","results"),("00631L","leveraged_comparison"))

def display(value,digits=2,suffix=""):
    if value is None:
        return "—"
    return f"{float(value):,.{digits}f}{suffix}"

def generate(source=Path("output"),dest=Path("docs")):
    source,dest=Path(source),Path(dest)
    payload=json.loads((source/"summary.json").read_text(encoding="utf-8"))
    leverage=payload["leveraged_comparison"]
    if leverage.get("ticker")!="00631L.TW":
        raise ValueError("00631L actual ETF price comparison required")
    by_ticker={
        "0050":{r["strategy"]:r for r in payload["results"]},
        "00631L":{r["strategy"]:r for r in leverage["results"]},
    }
    for ticker,strategies in by_ticker.items():
        if set(STRATEGY_ORDER)!=set(strategies):
            raise ValueError(f"{ticker} strategy mismatch: {set(STRATEGY_ORDER)^set(strategies)}")
    dest.mkdir(parents=True,exist_ok=True)
    files=["report.html","summary.json","summary.csv","signal_diagnostics.csv","comparison_00631L.json"]
    for strategy in STRATEGY_ORDER:
        for prefix in ("","00631L_"):
            files.extend((f"trades_{prefix}{strategy}.csv",f"equity_{prefix}{strategy}.csv"))
    for name in files:
        file=source/name
        if not file.is_file():
            raise FileNotFoundError(f"Missing report export: {file}")
        shutil.copyfile(file,dest/name)
    (dest/".nojekyll").write_text("",encoding="utf-8")
    labels={
        "A":"A 市場寬度基準",
        "A3":"A3 寬度趨勢",
        "B4":"B4 費波那契波段",
        "C3":"C3 寬度＋費波那契",
        "D":"D 趨勢追蹤",
        "DCA":"月初定期定額（每月 NT$3,000）",
        "BH":"一次買入持有（NT$10,000）",
    }
    table_rows=[]
    for ticker in ("0050","00631L"):
        for strategy in STRATEGY_ORDER:
            r=by_ticker[ticker][strategy]
            invested=r.get("external_capital")
            if invested is None:
                invested=r.get("external_contributions",r.get("total_invested"))
            net=r.get("trading_profit")
            if net is None:
                net=r.get("external_profit")
            xirr=r.get("capital_xirr_pct")
            if strategy=="DCA":
                xirr=r.get("external_xirr_pct")
            table_rows.append(
                "<tr class='"+("bench" if strategy in ("DCA","BH") else "")+"'>"
                f"<td><strong>{ticker}</strong></td>"
                f"<td>{html.escape(labels[strategy])}</td>"
                f"<td>{int(r.get('buy_orders',0))}</td>"
                f"<td>{int(r.get('sell_orders',0))}</td>"
                f"<td>{display(r.get('win_rate_pct'),1,'%') if strategy not in ('DCA','BH') else '—'}</td>"
                f"<td>NT$ {display(invested,0)}</td>"
                f"<td>NT$ {display(net,0)}</td>"
                f"<td>{display(r.get('invested_return_pct'),2,'%')}</td>"
                f"<td>{display(r.get('max_drawdown_pct'),2,'%')}</td>"
                f"<td>{display(r.get('exposure_pct'),1,'%')}</td>"
                f"<td>{display(xirr,2,'%')}</td>"
                "</tr>"
            )
    described="".join(
        "<p><strong>"+html.escape(name)+"</strong>："+html.escape(desc)+"</p>"
        for name,desc in payload["strategies"].items() if name not in ("DCA","BH")
    )
    snapshot=html.escape(str(payload["source"].get("snapshot_date","—")))
    first=html.escape(str(leverage["first_date"]))
    last=html.escape(str(leverage["last_date"]))
    downloads="".join(
        f'<a href="{html.escape(name)}" download>{html.escape(name)}</a>'
        for name in files if name!="report.html"
    )
    page=f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>0050／00631L 策略績效比較</title>
<style>
:root{{color-scheme:dark}}
*{{box-sizing:border-box}}
body{{background:#10141d;color:#e5eaf3;font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:0}}
main{{max-width:1440px;margin:auto;padding:24px 18px 48px}}
h1{{font-size:26px;margin:4px 0 6px}}
h2{{font-size:19px;margin:4px 0 10px}}
p,.muted{{color:#a6b3c6}}
.panel{{background:#1a2030;border:1px solid #364154;border-radius:14px;padding:17px;margin:16px 0}}
.warn{{border-left:4px solid #f7b955}}
.table-wrap{{overflow-x:auto}}
table{{border-collapse:collapse;width:100%;min-width:1080px;font-variant-numeric:tabular-nums}}
th,td{{padding:12px 10px;text-align:right;border-bottom:1px solid #364154;white-space:nowrap}}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){{text-align:left}}
th{{color:#a6b3c6;font-weight:600}}
tr.bench{{background:rgba(128,150,185,.08)}}
iframe{{width:100%;min-height:1100px;border:0;border-radius:10px;background:#14171d}}
a{{color:#8ac4ff}}
.files{{display:flex;flex-wrap:wrap;gap:9px}}
.files a{{padding:5px 10px;border:1px solid #495b74;border-radius:8px;text-decoration:none}}
@media(max-width:640px){{iframe{{min-height:960px}}h1{{font-size:22px}}}}
</style>
</head>
<body><main>
<p class="muted">獨立研究專案 · 0050／00631L 相同交易日的真實 ETF 價格回測</p>
<h1>0050 與 00631L 正二｜策略績效整合比較</h1>
<p>市場資料截至 {snapshot}｜共同交易區間 {first}～{last}（{leverage['matched_dates']} 個交易日）</p>
<section class="panel warn">
<strong>研究用途，非投資建議</strong>
<p>策略依收盤後訊號、隔日 ETF 調整後開盤買賣，不是實際成交保證。調整後價格是配息總報酬近似值，兩檔 ETF 的報酬不可直接倍乘。正二追蹤單日兩倍且具路徑依賴風險。歷史市場寬度使用目前前640大股票回推，存在存活者與前視偏差；新策略仍需樣本外驗證。</p>
</section>
<section class="panel">
<h2>策略績效比較</h2>
<div class="table-wrap"><table>
<thead><tr><th>ETF</th><th>策略</th><th>買進次數</th><th>賣出次數</th><th>賣出獲利率</th>
<th>實際外部投入本金</th><th>淨投資損益</th><th>本金報酬率</th><th>最大回撤</th><th>持倉比例</th><th>年化 XIRR</th></tr></thead>
<tbody>{"".join(table_rows)}</tbody></table></div>
<p class="muted">訊號策略每次買進 NT$10,000、不設總投入上限；現金不足時才補入外部本金，賣出50%持股所得再投入不算新本金。定期定額每月 1 日（休市順延）買進 NT$3,000；一次買入則在共同區間首個交易日投入 NT$10,000 並持有至期末。所有報酬均為（已實現＋未實現淨損益）／外部實際投入本金，包含買入手續費；不將未投入現金計入本金。XIRR 為資金加權年化報酬，買入持有的 XIRR 未單獨列出。</p>
<p class="muted">最大回撤沿用各策略目前的每日資產曲線口徑，定期定額逐月投入與訊號策略的資金流不同，風險指標不宜直接排名。調整後價格可包含配息與分割調整，允許小數股。</p>
</section>
<section class="panel">
<h2>策略規則</h2>
{described}
<p><strong>定期定額</strong>：每月首個可交易日買 NT$3,000。</p>
<p><strong>一次買進持有</strong>：首個可交易日買 NT$10,000，期間不賣出。</p>
</section>
<section class="panel">
<p class="muted">舊 B、C、A2、B2、C2、B3 已移出日常主表。<a href="archive/legacy_summary_pre_v3.json" download>下載舊策略績效快照</a></p>
</section>
<section class="panel"><h2>互動圖表</h2>
<iframe src="report.html" title="策略回測互動圖表" loading="lazy"></iframe>
<p><a href="report.html" target="_blank" rel="noopener">另開完整互動圖表</a></p>
</section>
<section class="panel"><h2>下載資料與診斷</h2><div class="files">{downloads}</div></section>
</main></body></html>"""
    (dest/"index.html").write_text(page,encoding="utf-8")
    print(f"Unified ETF report prepared: {dest/'index.html'}, {len(files)} files")

if __name__=="__main__":
    generate()
