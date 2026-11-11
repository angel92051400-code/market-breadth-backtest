"""True-price one-time ETF buy-and-hold baseline.

Same first/last common session as signal strategies and monthly DCA.
A single NT$10,000 purchase at first session adjusted open; never sells.
Returns include buy fee and last-session adjusted close. This baseline is
a distinct row, not a repeated benchmark field on every strategy.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def evaluate_buy_hold(prices:pd.DataFrame,cfg,amount:float=10000.0):
    if amount<=0 or cfg.buy_fee<0:
        raise ValueError("Buy amount must be positive; fee nonnegative")
    p=prices[["Open","Close"]].sort_index()
    if p.empty or p.index.has_duplicates:
        raise ValueError("Need unique positive dated prices")
    first_open=float(p.Open.iloc[0])
    if not np.isfinite(first_open) or first_open<=0:
        raise ValueError("First adjusted open must be valid")
    if p.Close.isna().any() or (p.Close<=0).any():
        raise ValueError("Missing or nonpositive adjusted close")
    qty=amount/(first_open*(1+cfg.buy_fee))
    curve=pd.DataFrame(index=p.index)
    curve["market_value"]=qty*p.Close
    curve["shares"]=qty
    curve["cash"]=0.0
    curve["equity"]=curve["market_value"]
    curve["position"]=1
    curve["etf_close"]=p.Close
    curve["external_capital"]=amount
    curve["capital_profit"]=curve["market_value"]-amount
    curve["capital_roi_pct"]=curve["capital_profit"]/amount*100
    curve["drawdown_pct"]=(curve["market_value"]/curve["market_value"].cummax()-1)*100
    ledger=pd.DataFrame([{
        "date":p.index[0].date().isoformat(),"action":"BUY",
        "price_adjusted":first_open,"amount":amount,"shares":qty,
        "external_contribution":amount,"shares_after":qty,
        "cash_after":0.0
    }])
    last_value=float(curve.market_value.iloc[-1])
    summary={
        "strategy":"BH","buy_orders":1,"sell_orders":0,"completed_trades":0,
        "wins":0,"win_rate_pct":None,"external_capital":amount,
        "total_invested":amount,"trading_profit":last_value-amount,
        "invested_return_pct":(last_value/amount-1)*100,
        "ending_market_value":last_value,"total_sale_proceeds":0.0,
        "max_drawdown_pct":float(curve.drawdown_pct.min()),
        "exposure_pct":100.0,
        "first_date":p.index[0].date().isoformat(),
        "last_date":p.index[-1].date().isoformat(),
        "open_trade":{"remaining_shares":qty,"remaining_cost":amount},
    }
    return ledger,curve,summary
