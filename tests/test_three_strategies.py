import numpy as np
import pandas as pd
from backtest import Config, build_signals, evaluate

def prices_with_reclaim():
    dates=pd.bdate_range("2026-04-01",periods=10)
    # Prior two sessions' high=120 and low=80 -> fib_618 around 95.28.
    closes=[90,93,94,96,98,107,111,110,109,106]
    highs=[120]*10
    lows=[80]*10
    return pd.DataFrame({"breadth":[np.nan]*10,"taiex_high":highs,
        "taiex_low":lows,"taiex_close":closes},index=dates)

def test_fibonacci_only_enters_without_breadth():
    df=prices_with_reclaim()
    signals=build_signals(df,Config(lookback=2,fib_tolerance=.03))
    assert signals["entry_B"].any()
    assert not signals["entry_A"].any()
    assert not signals["entry_C"].any()

def test_fibonacci_exit_ignores_breadth_and_next_open():
    df=prices_with_reclaim()
    cfg=Config(lookback=2,fib_tolerance=.03)
    signals=build_signals(df,cfg)
    prices=pd.DataFrame({"Open":[100+i for i in range(len(df))],
        "Close":[100+i for i in range(len(df))]},index=df.index)
    trades,curve,summary=evaluate(signals,prices,cfg,"B")
    assert len(trades)==1
    assert trades.iloc[0]["exit_reason"]=="fib_target"
    assert summary["completed_trades"]==1

def test_combined_old_b_logic_is_now_C():
    df=prices_with_reclaim()
    df["breadth"]=[30,19,21,22,23,25,30,45,70,65]
    cfg=Config(lookback=2)
    sig=build_signals(df,cfg)
    assert bool(sig["entry_A"].iloc[2])
    assert bool(sig["entry_C"].iloc[2])
    assert bool(sig["exit_breadth"].iloc[8])

def test_all_3_strategies_accepted():
    df=prices_with_reclaim()
    sig=build_signals(df,Config(lookback=2))
    etf=pd.DataFrame({"Open":[100]*10,"Close":[100]*10},index=df.index)
    for name in ("A","B","C"):
        _,curve,stats=evaluate(sig,etf,Config(lookback=2),name)
        assert not curve.empty and stats["strategy"]==name
