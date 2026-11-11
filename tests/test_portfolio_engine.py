import numpy as np
import pandas as pd
import pytest
from backtest import Config, build_signals
from experimental_strategies import add_variant_signals
from portfolio_engine import evaluate_portfolio


def data():
    idx = pd.bdate_range("2026-01-01",periods=18)
    # Three breadth oversold recoveries and hot crosses.
    breadth = [15,21,40,55,65,30,15,22,41,52,62,35,15,22,42,55,65,45]
    prices = pd.DataFrame({
        "Open": [100]*18, "Close": [100]*18,
    },index=idx)
    signals = pd.DataFrame({
        "breadth":breadth,
        "taiex_close":[100]*18,"fib_500":[95]*18,
        "fib_382":[110]*18,"fib_618":[90]*18,
    },index=idx)
    signals["entry_A"] = (signals.breadth.shift(1)<=20)&(signals.breadth>20)
    signals["entry_C"]=signals["entry_A"]
    signals["entry_B"]=False
    signals["entry_A2"]=False
    signals["entry_B2"]=False
    signals["entry_C2"]=False
    signals["exit_breadth"]=(signals.breadth.shift(1)<50)&(signals.breadth>=50)
    signals["exit_veryhot"]=(signals.breadth.shift(1)<60)&(signals.breadth>=60)
    signals["fib_entry_support"]=np.nan
    signals["fib_entry_target"]=np.nan
    signals["b2_support"]=np.nan
    return signals,prices


def test_fixed_amount_buys_and_half_sells_repeatedly():
    signals,prices=data()
    cfg=Config()
    ledger,curve,stats=evaluate_portfolio(signals,prices,cfg,"A")
    buys=ledger[ledger.action=="BUY"]
    sells=ledger[ledger.action=="SELL"]
    assert len(buys)==3
    assert len(sells)==6  # cross 50 and 60 on each of three cycles
    assert all(abs(buys.gross_value-10000)<1e-6)
    # On first sell (after 1 BUY) half shares, then 50% of remaining shares.
    q=buys.iloc[0].shares
    assert sells.iloc[0].shares==pytest.approx(q/2)
    assert sells.iloc[1].shares==pytest.approx(q/4)
    assert curve.iloc[-1].shares>0
    # Despite six sell executions, win rates are about realized sell lots, not six completed round trips.
    assert stats["buy_orders"]==3
    assert stats["sell_orders"]==6
    assert stats["completed_trades"]==6
    assert stats["exposure_pct"]>0


def test_50_and_60_hit_same_day_sell_sequential_halves():
    signals,prices=data()
    signals["breadth"]=[15,21,65]+[45]*15
    cfg=Config()
    l,c,st=evaluate_portfolio(signals,prices,cfg,"A")
    sells=l[l.action=="SELL"]
    assert len(sells)==2
    assert list(sells.reason)==["breadth_cross_50","breadth_cross_60"]
    assert sells.iloc[1].shares==pytest.approx(sells.iloc[0].shares/2)


def test_cash_limit_and_no_invented_capital():
    signals,prices=data()
    signals["entry_A"]=True
    signals["breadth"]=40
    cfg=Config(initial_cash=20000,buy_amount=10000)
    ledger,curve,stats=evaluate_portfolio(signals,prices,cfg,"A")
    assert stats["buy_orders"]==2
    assert stats["skipped_buys_insufficient_cash"]>0
    assert abs(curve.cash.min())<1e-8
    assert curve.equity.min()>0


def test_realized_profit_and_cash_ledger_reconciles():
    signals,prices=data()
    cfg=Config()
    ledger,curve,stats=evaluate_portfolio(signals,prices,cfg,"A")
    assert np.isfinite(curve.equity).all()
    assert np.isfinite(curve.cash).all()
    assert np.isfinite(curve.shares).all()
    assert (curve.equity>=curve.cash-1e-8).all()
    assert stats["strategy_return_pct"]==pytest.approx(
        (curve.equity.iloc[-1]/cfg.initial_cash-1)*100
    )


def test_fib_B_independent_of_breadth():
    signals,prices=data()
    signals["breadth"]=np.nan
    signals.loc[signals.index[1:],"entry_B"]=False
    signals.loc[signals.index[1],"entry_B"]=True
    signals.loc[signals.index[1],"fib_entry_support"]=95.
    signals.loc[signals.index[1],"fib_entry_target"]=104.
    signals.loc[signals.index[3],"taiex_close"]=105.
    signals.loc[signals.index[2],"taiex_close"]=103.
    ledger,_,stats=evaluate_portfolio(signals,prices,Config(),"B")
    assert stats["buy_orders"]==1
    assert stats["sell_orders"]==1


def test_no_buy_before_signal_next_open():
    signals,prices=data()
    ledger,curve,stats=evaluate_portfolio(signals,prices,Config(),"A")
    assert ledger.iloc[0].signal_date==signals.index[1].date().isoformat()
    assert ledger.iloc[0].date==signals.index[2].date().isoformat()
