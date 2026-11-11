import json
from publish_report import generate
from strategy_v3 import ACTIVE_STRATEGIES, DESCRIPTIONS


def test_published_site_has_new_five_strategies_and_dca(tmp_path):
    source=tmp_path/"output"
    dest=tmp_path/"docs"
    source.mkdir()
    results=[]
    for k in (*ACTIVE_STRATEGIES,"DCA"):
        results.append({
            "strategy":k,"buy_orders":3,"sell_orders":2,
            "win_rate_pct":50.,"invested_return_pct":12.345,
            "max_drawdown_pct":-4.1,"exposure_pct":30.0,
            "buy_hold_return_pct":15.6,"external_capital":20000,
            "trading_profit":2469.0,
        })
    dca=results[-1]
    dca.update({
        "total_invested":9000,"ending_market_value":11000,
        "remaining_cash":91000,"ending_equity":102000,"net_profit":2000,
        "external_contributions":9000,"external_market_value":11000,
        "external_profit":2000,"external_return_on_contributions_pct":22.222,
        "external_xirr_pct":12.34
    })
    meta={
        "ticker":"0050.TW","source":{"snapshot_date":"2026-11-11"},
        "config":{"buy":20,"sell":50},
        "strategies":{**DESCRIPTIONS,"DCA":"每月首個交易日投資3000元"},
        "leveraged_comparison":{
            "ticker":"00631L.TW","first_date":"2024-11-11",
            "last_date":"2026-11-10","matched_dates":486,
            "results":[{**r,"invested_return_pct":20.} for r in results],
        },
        "results":results
    }
    (source/"summary.json").write_text(json.dumps(meta),encoding="utf-8")
    names=["report.html","summary.csv","signal_diagnostics.csv","comparison_00631L.json"]
    for k in (*ACTIVE_STRATEGIES,"DCA"):
        names.extend([f"trades_{k}.csv",f"equity_{k}.csv",
                      f"trades_00631L_{k}.csv",f"equity_00631L_{k}.csv"])
    for n in names:
        (source/n).write_text("fixture",encoding="utf-8")
    generate(source,dest)
    page=(dest/"index.html").read_text(encoding="utf-8")
    assert "五種主要策略" in page
    for k in ACTIVE_STRATEGIES:
        assert f"策略 {k}" in page
    assert "策略 B2</td>" not in page
    assert "策略 B3</td>" not in page
    assert "策略 C2</td>" not in page
    assert "00631L" in page
    assert "定期定額" in page
    assert "實際外部投入本金" in page
    assert "12.35%" in page
    assert "XIRR" in page
    assert (dest/"trades_B4.csv").exists()
    assert (dest/"equity_00631L_C3.csv").exists()
    assert (dest/".nojekyll").exists()
