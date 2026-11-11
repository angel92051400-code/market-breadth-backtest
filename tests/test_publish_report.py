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
    (source/"summary.json").write_text(json.dumps(meta),encoding="utf-8")
    for name in ("report.html","summary.csv","signal_diagnostics.csv",
                 "trades_A.csv","trades_B.csv","trades_C.csv",
                 "trades_A2.csv","trades_B2.csv","trades_C2.csv","trades_DCA.csv",
                 "equity_A.csv","equity_B.csv","equity_C.csv",
                 "equity_A2.csv","equity_B2.csv","equity_C2.csv","equity_DCA.csv"):
        (source/name).write_text("fixture",encoding="utf-8")
    generate(source,dest)
    page = (dest/"index.html").read_text(encoding="utf-8")
    assert "12.35%" in page
    assert "策略 B" in page
    assert "策略 C" in page
    assert "策略 A2" in page
    assert "策略 B2" in page
    assert "策略 C2" in page
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
