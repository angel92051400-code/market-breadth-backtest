import pandas as pd
import pytest
from backtest import Config
from buy_hold_baseline import evaluate_buy_hold

def test_first_open_one_time_buy_and_last_close_valuation():
    dates=pd.to_datetime(["2024-11-11","2024-11-12","2024-11-13"])
    p=pd.DataFrame({"Open":[50.,70.,80.],"Close":[51.,71.,100.]},index=dates)
    ledger,curve,s=evaluate_buy_hold(p,Config(),10000)
    quantity=10000/(50*(1+0.001425))
    assert len(ledger)==1
    assert ledger.iloc[0].date=="2024-11-11"
    assert ledger.iloc[0].amount==10000
    assert ledger.iloc[0].shares==pytest.approx(quantity)
    assert curve.iloc[-1].market_value==pytest.approx(quantity*100)
    assert s["external_capital"]==10000
    assert s["trading_profit"]==pytest.approx(quantity*100-10000)
    assert s["invested_return_pct"]==pytest.approx((quantity*100/10000-1)*100)
    assert s["sell_orders"]==0
    assert s["exposure_pct"]==100.
    assert s["max_drawdown_pct"]<=0

def test_lower_final_price_can_produce_negative_return():
    p=pd.DataFrame({"Open":[100,90],"Close":[100,80]},
                   index=pd.to_datetime(["2025-02-03","2025-02-04"]))
    _,_,s=evaluate_buy_hold(p,Config(),10000)
    assert s["trading_profit"]<0
    assert s["invested_return_pct"]<0
    assert s["max_drawdown_pct"]<0

def test_invalid_first_open_fails():
    p=pd.DataFrame({"Open":[0,20],"Close":[20,21]},
                   index=pd.to_datetime(["2025-02-03","2025-02-04"]))
    with pytest.raises(ValueError):
        evaluate_buy_hold(p,Config())
