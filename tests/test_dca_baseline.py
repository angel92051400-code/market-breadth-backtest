import numpy as np
import pandas as pd
import pytest

from backtest import Config
from dca_baseline import evaluate_monthly_dca, _xirr


def test_monthly_first_trading_day_and_holidays():
    dates = pd.to_datetime([
        "2025-01-02","2025-01-03",  # Jan 1 closed
        "2025-02-03","2025-02-04",  # Feb 1 weekend
        "2025-03-03","2025-03-04",  # Mar 1 weekend
    ])
    prices = pd.DataFrame({"Open":[100.]*6,"Close":[100.]*6},index=dates)
    ledger,curve,d = evaluate_monthly_dca(prices,Config(),3000.)
    assert list(ledger.date) == ["2025-01-02","2025-02-03","2025-03-03"]
    assert len(ledger)==3
    assert d["buy_orders"]==3
    assert d["total_invested"]==9000.
    assert d["remaining_cash"]==91000.
    assert d["external_contributions"]==9000.
    assert d["external_market_value"]==pytest.approx(9000/1.001425)
    assert d["external_return_on_contributions_pct"] < 0
    assert d["strategy_return_pct"]<0
    assert curve.iloc[-1].equity==pytest.approx(
        91000 + 9000/1.001425)
    assert (curve.equity>=curve.cash).all()


def test_first_partial_month_invests_once_from_first_available_data():
    dates=pd.to_datetime(["2024-11-11","2024-11-29","2024-12-02","2024-12-31"])
    prices=pd.DataFrame({"Open":[50]*4,"Close":[50]*4},index=dates)
    ledger,_,result=evaluate_monthly_dca(prices,Config(),3000)
    assert list(ledger.date)==["2024-11-11","2024-12-02"]
    assert result["total_invested"]==6000


def test_same_seed_100k_cash_vs_external_3000_contributions():
    dates=pd.date_range("2025-01-01",periods=12,freq="MS")
    prices=pd.DataFrame({"Open":[100]*12,"Close":[100]*12},index=dates)
    _, curve,r=evaluate_monthly_dca(prices,Config(initial_cash=100000),3000)
    assert r["total_invested"]==36000
    assert r["external_contributions"]==36000
    assert r["remaining_cash"]==64000
    assert r["external_market_value"]==pytest.approx(36000/1.001425)
    assert r["external_xirr_pct"] is not None
    assert r["ending_equity"]==pytest.approx(
        64000 + r["external_market_value"])


def test_insufficient_cash_limits_prefunded_not_external_contributions():
    dates=pd.date_range("2025-01-01",periods=4,freq="MS")
    prices=pd.DataFrame({"Open":[100]*4,"Close":[100]*4},index=dates)
    trades,curve,r=evaluate_monthly_dca(prices,Config(initial_cash=5000),3000)
    assert r["buy_orders"]==1
    assert r["skipped_insufficient_cash"]==3
    assert r["total_invested"]==3000
    assert r["external_contributions"]==12000
    assert (curve.cash>=0).all()


def test_xirr_evenly_compounded_full_year():
    r=_xirr([
        (pd.Timestamp("2025-01-01").date(),-1000.),
        (pd.Timestamp("2026-01-01").date(),1100.),
    ])
    assert r==pytest.approx(10,abs=.05)


def test_dca_daily_values_do_not_change_with_future_prices():
    dates=pd.date_range("2025-01-01",periods=70,freq="B")
    prices=pd.DataFrame({"Open":[100.]*len(dates),
                         "Close":[100.]*len(dates)},index=dates)
    _,first,_=evaluate_monthly_dca(prices,Config(),3000.)
    prices.loc[prices.index[40]:,"Open"]=155
    prices.loc[prices.index[40]:,"Close"]=156
    _,later,_=evaluate_monthly_dca(prices,Config(),3000.)
    pd.testing.assert_series_equal(first.equity.iloc[:40],later.equity.iloc[:40])
