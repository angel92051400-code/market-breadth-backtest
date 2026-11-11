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
        ]
    }
    (source/"summary.json").write_text(json.dumps(meta),encoding="utf-8")
    for name in ("report.html","summary.csv","signal_diagnostics.csv",
                 "trades_A.csv","trades_B.csv","trades_C.csv","equity_A.csv","equity_B.csv","equity_C.csv"):
        (source/name).write_text("fixture",encoding="utf-8")
    generate(source,dest)
    page = (dest/"index.html").read_text(encoding="utf-8")
    assert "12.35%" in page
    assert "策略 B" in page
    assert "策略 C" in page
    assert (dest/"trades_C.csv").exists()
    assert "report.html" in page
    assert "signal_diagnostics.csv" in page
    assert (dest/".nojekyll").exists()
    assert (dest/"report.html").exists()
