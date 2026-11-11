import json
from pathlib import Path
from publish_report import generate


def test_published_site_has_report_metrics_and_downloads(tmp_path):
    source = tmp_path / "output"
    dest = tmp_path / "docs"
    source.mkdir()
    meta = {
        "ticker": "0050.TW",
        "source": {"snapshot_date": "2026-11-11"},
        "config": {"buy":20.0,"sell":70.0},
        "results": [
            {"strategy":"A","completed_trades":1,"win_rate_pct":100.0,
             "strategy_return_pct":12.345,"max_drawdown_pct":-4.1,
             "buy_hold_return_pct":15.6},
            {"strategy":"B","completed_trades":0,"win_rate_pct":None,
             "strategy_return_pct":0,"max_drawdown_pct":0,
             "buy_hold_return_pct":15.6},
            {"strategy":"C","completed_trades":0,"win_rate_pct":None,
             "strategy_return_pct":0,"max_drawdown_pct":0,
             "buy_hold_return_pct":15.6},
            {"strategy":"A2","completed_trades":2,"win_rate_pct":50.0,
             "strategy_return_pct":6.0,"max_drawdown_pct":-8.0,
             "exposure_pct":30.0,"buy_hold_return_pct":15.6},
            {"strategy":"B2","completed_trades":1,"win_rate_pct":100.0,
             "strategy_return_pct":9.0,"max_drawdown_pct":-3.0,
             "exposure_pct":21.0,"buy_hold_return_pct":15.6},
            {"strategy":"C2","completed_trades":1,"win_rate_pct":0.0,
             "strategy_return_pct":-2.0,"max_drawdown_pct":-5.0,
             "exposure_pct":12.0,"buy_hold_return_pct":15.6},
            {"strategy":"DCA","completed_trades":0,"win_rate_pct":None,
             "buy_orders":3,"sell_orders":0,
             "strategy_return_pct":2.0,"max_drawdown_pct":-1.0,
             "exposure_pct":70.0,"buy_hold_return_pct":15.6,
             "total_invested":9000,"ending_market_value":11000,
             "remaining_cash":91000,"ending_equity":102000,"net_profit":2000,
             "external_contributions":9000,"external_market_value":11000,
             "external_profit":2000,
             "external_return_on_contributions_pct":22.222,
             "external_xirr_pct":12.34},
        ]
    }
    base = {"strategy":"B3","completed_trades":2,"win_rate_pct":50.0,
            "buy_orders":3,"sell_orders":2,"strategy_return_pct":5.0,
            "max_drawdown_pct":-2.0,"exposure_pct":32.0,"buy_hold_return_pct":15.6,
            "invested_return_pct":25.0,"total_invested":30000,"trading_profit":7500}
    meta["results"].insert(-1,base)
    for row in meta["results"]:
        row.setdefault("total_invested",9000)
        row.setdefault("trading_profit",2000)
        row.setdefault("invested_return_pct",22.222)
    meta["leveraged_comparison"]={
        "ticker":"00631L.TW","first_date":"2025-01-01",
        "last_date":"2025-12-31","matched_dates":250,
        "results":[{**row,"invested_return_pct":row["invested_return_pct"]*1.2} for row in meta["results"]]
    }
    (source/"summary.json").write_text(json.dumps(meta),encoding="utf-8")
    files = ["report.html","summary.csv","signal_diagnostics.csv","comparison_00631L.json"]
    for strategy in ("A","B","C","A2","B2","C2","B3","DCA"):
        files.extend([f"trades_{strategy}.csv",f"equity_{strategy}.csv",
                      f"trades_00631L_{strategy}.csv",f"equity_00631L_{strategy}.csv"])
    for name in files:
        (source/name).write_text("fixture",encoding="utf-8")
    generate(source,dest)
    page = (dest/"index.html").read_text(encoding="utf-8")
    assert "22.22%" in page
    assert "策略 B" in page
    assert "策略 C" in page
    assert "策略 A2" in page
    assert "策略 B2" in page
    assert "策略 C2" in page
    assert "策略 B3" in page
    assert "00631L" in page
    assert "投入報酬率" in page
    assert "累計買進本金" in page
    assert "25.00%" in page
    assert (dest/"comparison_00631L.json").exists()
    assert (dest/"trades_B2.csv").exists()
    assert "30.0%" in page
    assert (dest/"trades_C.csv").exists()
    assert (dest/"trades_DCA.csv").exists()
    assert "0050 月初定期定額" in page
    assert "外部逐月投入" in page
    assert "XIRR" in page
    assert "12.34%" in page
    assert "report.html" in page
    assert "signal_diagnostics.csv" in page
    assert (dest/".nojekyll").exists()
    assert (dest/"report.html").exists()
