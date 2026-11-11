import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from backtest import Config, build_signals, evaluate
from data_sources import read_dashboard

def make_frame():
    dates=pd.bdate_range('2026-01-01',periods=12)
    b=[30,25,19,21,30,40,65,71,60,19,21,30]
    return pd.DataFrame({'breadth':b,'taiex_high':[110]*12,
        'taiex_low':[90]*12,'taiex_close':[100]*12},index=dates)

def test_next_day_execution_and_win_rate():
    df=make_frame()
    signals=build_signals(df,Config(lookback=2,sell=70,very_hot=80))
    prices=pd.DataFrame({'Open':[100,100,100,100,105,107,110,120,123,100,100,100],
        'Close':[100,100,100,102,105,107,110,120,123,100,100,100]},index=df.index)
    trades,curve,stats=evaluate(signals,prices,Config(lookback=2,sell=70,very_hot=80),'A')
    assert len(trades)==1
    assert trades.iloc[0].entry_date == df.index[4].date().isoformat()
    assert trades.iloc[0].exit_date == df.index[8].date().isoformat()
    assert stats['completed_trades']==1
    assert stats['win_rate_pct']==100.0
    assert stats['open_trade'] is not None

def test_no_future_fibonacci_repaint():
    df=make_frame()
    early=build_signals(df.iloc[:8],Config(lookback=3))
    modified=df.copy()
    modified.loc[modified.index[9]:,'taiex_high']=9999
    later=build_signals(modified,Config(lookback=3))
    pd.testing.assert_series_equal(early['fib_618'],later['fib_618'].iloc[:8])

def test_missing_breadth_no_signal():
    df=make_frame()
    df.loc[df.index[2],'breadth']=np.nan
    signals=build_signals(df,Config(lookback=3))
    assert not bool(signals['entry_A'].iloc[3])

def test_report_source_coverage():
    import json
    payload={'dates':['2026-01-01','2026-01-02'],'snapshotDate':'2026-01-02',
        'candles':{x:[100,101] for x in ('open','high','low','close')},
        'universes':{'640':{'total':640,'values':[100,20],'valid':[1,640],'counts':[1,128]}}}
    html='<script id="market-data" type="application/json">'+json.dumps(payload)+'</script>'
    d,meta=read_dashboard(html)
    assert pd.isna(d.breadth.iloc[0])
    assert d.breadth.iloc[1]==20
