import numpy as np
import pandas as pd
from backtest import Config,build_signals
from strategy_v3 import add_v3_signals, ACTIVE_STRATEGIES
from portfolio_engine import evaluate_portfolio

def scenario():
    d=pd.bdate_range("2025-01-01",periods=160)
    px=np.full(160,100.0)
    px[125:129]=[104,101,99,101]
    px[140:145]=[103,104,105,106,108]
    px[150:155]=[112,113,114,115,116]
    breadth=np.full(160,20.0)
    breadth[125:]=[25,29,31,35,39]+[45.0]*30
    breadth[148:]=[55.0]*12
    breadth[156:]=[42.0]*4
    df=pd.DataFrame({
      "breadth":breadth,
      "taiex_close":px,
      "taiex_high":px+0.6,
      "taiex_low":px-0.6
    },index=d)
    cfg=Config()
    return add_v3_signals(build_signals(df,cfg))

def test_four_new_signal_columns_and_no_future():
    a=scenario()
    assert set(ACTIVE_STRATEGIES)=={"A","A3","B4","C3","D"}
    for col in ["entry_A3","entry_B4","entry_C3","entry_D",
                "exit_A3_breadth","exit_A3_trend",
                "exit_C3_weak","exit_D","b4_support","c3_support",
                "high60","sma20"]:
        assert col in a
    assert a["entry_A3"].any()
    assert a["entry_D"].any()
    # No signal at day t can change if only later observations are edited.
    original=a.iloc[:145]
    changed=scenario()
    raw=changed[["breadth","taiex_close","taiex_high","taiex_low"]].copy()
    raw.loc[raw.index[145]:,"taiex_close"]=200
    raw.loc[raw.index[145]:,"taiex_high"]=201
    raw.loc[raw.index[145]:,"taiex_low"]=199
    raw.loc[raw.index[145]:,"breadth"]=1
    revised=add_v3_signals(build_signals(raw,Config()))
    for col in ["entry_A3","entry_B4","entry_C3","entry_D",
                "exit_A3_trend","exit_C3_weak","exit_D"]:
        pd.testing.assert_series_equal(original[col],revised[col].iloc[:145])

def test_b4_rearms_only_after_separate_support_episode():
    s=scenario()
    # State-machine B4 can never fire on adjacent trading sessions.
    buy=np.flatnonzero(s["entry_B4"].to_numpy())
    assert all(j-i>1 for i,j in zip(buy,buy[1:]))
    assert s.loc[s["entry_B4"],"b4_support"].notna().all()

def test_v3_trades_use_next_open_and_no_cap():
    s=scenario()
    prices=pd.DataFrame({"Open":s.taiex_close+1,"Close":s.taiex_close},index=s.index)
    for strategy in ("A3","B4","C3","D"):
        ledger,curve,stats=evaluate_portfolio(s,prices,Config(initial_cash=1),strategy)
        assert stats["skipped_buys_insufficient_cash"]==0
        assert stats["external_capital"]>=0
        assert (curve.cash>=-1e-7).all()
        assert (curve.external_capital>=0).all()
        assert (ledger.loc[ledger.action=="BUY","gross_value"]==10000).all()
        if len(ledger):
            for _,x in ledger.iterrows():
                i=s.index.get_loc(pd.Timestamp(x["signal_date"]))
                assert x["date"]==s.index[i+1].date().isoformat()

def test_C3_only_once_per_breadth_recovery():
    s=scenario()
    # One candidate per discrete crossing of the 30% breadth threshold.
    crossings=((s.breadth.shift(1)<=30)&(s.breadth>30)).sum()
    assert s.entry_C3.sum()<=crossings
