import numpy as np
import pandas as pd
from backtest import Config
from experimental_strategies import add_variant_signals, evaluate_variant


def frame():
    ix = pd.bdate_range("2025-01-02", periods=22)
    breadth = [25, 35, 42, 48, 68, 50, 39, 35, 43, 47, 66, 49, 36,
               31, 44, 47, 67, 38, 35, 45, 46, 44]
    closes = [94, 96, 97, 100, 102, 98, 97, 97, 99, 101, 102, 98,
              96, 94, 98, 101, 102, 96, 94, 99, 100, 98]
    df = pd.DataFrame({
        "breadth": breadth,
        "taiex_close": closes,
        "fib_382": [106.0]*22,
        "fib_500": [95.0]*22,
        "fib_618": [90.0]*22,
    }, index=ix)
    return df


def etf_prices(frame):
    ix = frame.index
    return pd.DataFrame({"Open": [50+i/3 for i in range(len(ix))],
                         "Close": [50+i/3 for i in range(len(ix))]}, index=ix)


def test_A2_can_complete_repeated_trades_with_next_open_execution():
    f = add_variant_signals(frame())
    assert f["entry_A2"].sum() >= 4
    trades, curve, stats = evaluate_variant(f, etf_prices(f), Config(), "A2")
    assert stats["completed_trades"] >= 2
    assert trades.iloc[0]["entry_date"] == f.index[3].date().isoformat()
    assert stats["exposure_pct"] > 0


def test_B2_is_price_only_even_if_breadth_missing():
    f = frame()
    f["breadth"] = np.nan
    derived = add_variant_signals(f)
    assert derived["entry_B2"].sum() > 0
    assert derived["entry_A2"].sum() == 0
    assert derived["entry_C2"].sum() == 0
    _, _, stats = evaluate_variant(derived, etf_prices(f), Config(), "B2")
    assert stats["strategy"] == "B2"


def test_no_future_signal_repainting():
    original = add_variant_signals(frame())
    changed = frame()
    changed.loc[changed.index[12]:,"taiex_close"] *= 2
    changed.loc[changed.index[12]:,"breadth"] = 2
    revised = add_variant_signals(changed)
    for name in ("entry_A2", "entry_B2", "entry_C2"):
        pd.testing.assert_series_equal(original[name].iloc[:12], revised[name].iloc[:12])


def test_empty_trades_are_reported_without_inventing_wins():
    f = add_variant_signals(frame())
    f["entry_C2"] = False
    trades, curve, stats = evaluate_variant(f, etf_prices(f), Config(), "C2")
    assert trades.empty
    assert stats["completed_trades"] == 0
    assert stats["win_rate_pct"] is None
    assert stats["strategy_return_pct"] == 0


def test_missing_breadth_does_not_make_signal():
    f = frame()
    f.loc[f.index[1], "breadth"] = np.nan
    out = add_variant_signals(f)
    assert not out["entry_A2"].iloc[2]
    assert not out["entry_C2"].iloc[2]
