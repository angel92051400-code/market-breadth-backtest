"""Monthly NT$3,000 0050 dollar-cost averaging, using first available trading day.

Two clearly separated interpretations:
1) DCA: hold initial NT$100,000 CASH account, move NT$3,000 from cash to 0050
   monthly. Its total portfolio return is directly comparable with A/B/C/A2/B2/C2.
2) Contributions-only: add NT$3,000 externally monthly and buy 0050; report
   total contributions, market value, invested-capital return, and XIRR.
   Contributions-only is NOT compared by naive profit percentage to an account
   seeded with NT$100,000 on the first day.

Uses fractional shares and adjusted open/close, includes the same buy fee as
the six strategies, and never draws on future prices.
"""
from __future__ import annotations
from datetime import date
import math
import numpy as np
import pandas as pd

DCA_AMOUNT = 3000.0


def _xirr(flows: list[tuple[date, float]]) -> float | None:
    """Annual effective money-weighted IRR (percent), bracketed bisection.

    Cash outflows are negative, closing market value is a positive inflow.
    Rate lower bound is -99.99%, upper expands as needed; no NumPy/scipy IRR.
    """
    if not flows or len(flows) < 2:
        return None
    d0 = flows[0][0]
    if not any(amount < 0 for _, amount in flows) or not any(amount > 0 for _, amount in flows):
        return None
    times = [(d - d0).days / 365.25 for d, _ in flows]
    if max(times) <= 0:
        return None
    def npv(r):
        return sum(amount / math.exp(t * math.log1p(r)) for t, (_, amount) in zip(times, flows))
    lo, hi = -0.9999, 1.0
    flo, fhi = npv(lo), npv(hi)
    while fhi > 0 and hi < 1e7:
        hi = 2 * hi + 1
        fhi = npv(hi)
    if flo * fhi > 0:
        return None
    for _ in range(130):
        mid = (lo + hi) / 2
        fm = npv(mid)
        if fm > 0:
            lo = mid
        else:
            hi = mid
    return ((lo + hi) / 2) * 100


def evaluate_monthly_dca(prices: pd.DataFrame, cfg, monthly_amount=DCA_AMOUNT):
    """Return prefunded summary, daily equity, order ledger, contribution metrics.

    For the first partial calendar month, invest on first sample trading day,
    even if the calendar first is before sample start. Each later month uses
    its first available ETF trading day on/after day 1 (holidays roll forward).
    """
    if monthly_amount <= 0 or cfg.initial_cash <= 0:
        raise ValueError("monthly amount and initial cash must be positive")
    prices = prices[["Open", "Close"]].sort_index().copy()
    if prices.empty or prices.index.has_duplicates:
        raise ValueError("Need dated, nonduplicated 0050 prices")
    if not prices.index.is_monotonic_increasing:
        raise ValueError("Unsorted dates")
    cash, shares, cost = float(cfg.initial_cash), 0.0, 0.0
    external_shares, external_contributions = 0.0, 0.0
    last_month = None
    ledger, daily, flows = [], [], []
    n_purchases, skipped = 0, 0
    for day, row in prices.iterrows():
        op, close = row["Open"], row["Close"]
        month_key = (day.year, day.month)
        is_first_session = month_key != last_month
        last_month = month_key
        if is_first_session:
            if pd.isna(op) or not np.isfinite(op) or op <= 0:
                # Don't invent a fill. Defer to next valid session this month.
                last_month = None
            else:
                # Real-money external contributions strategy (separate funding).
                external_contributions += monthly_amount
                eqty = monthly_amount / (float(op) * (1 + cfg.buy_fee))
                external_shares += eqty
                flows.append((day.date(), -monthly_amount))
                if cash + 1e-8 >= monthly_amount:
                    cash -= monthly_amount
                    shares += eqty
                    cost += monthly_amount
                    n_purchases += 1
                    ledger.append({
                        "date":day.date().isoformat(), "action":"BUY",
                        "price_adjusted":float(op), "amount":monthly_amount,
                        "shares":eqty, "cash_after":cash,
                        "shares_after":shares,
                    })
                else:
                    skipped += 1
        mkt = shares * close if pd.notna(close) else np.nan
        equity = cash + mkt if pd.notna(mkt) else np.nan
        daily.append({
            "date":day, "equity":equity, "cash":cash, "shares":shares,
            "market_value":mkt, "position":int(shares > 0),
            "invested_roi_pct":(mkt/cost-1)*100 if cost>0 and pd.notna(mkt) else np.nan,
            "etf_close":close, "external_contributions":external_contributions,
            "external_equity":external_shares * close if pd.notna(close) else np.nan,
        })
    curve = pd.DataFrame(daily).set_index("date")
    curve["drawdown_pct"] = (curve.equity / curve.equity.cummax() - 1) * 100
    ledger = pd.DataFrame(ledger, columns=[
        "date", "action", "price_adjusted", "amount", "shares",
        "cash_after", "shares_after",
    ])
    end_value = float(curve.equity.iloc[-1])
    evalue = float(curve.external_equity.iloc[-1])
    last_day = curve.index[-1].date()
    annual_irr = _xirr(flows + [(last_day, evalue)])
    result = {
        "strategy": "DCA",
        "buy_orders": n_purchases, "sell_orders": 0,
        "completed_trades": 0, "wins": 0, "win_rate_pct": None,
        "initial_cash":float(cfg.initial_cash),
        "monthly_amount": monthly_amount,
        "total_invested": cost,
        "remaining_cash":cash,
        "ending_market_value":float(curve.market_value.iloc[-1]),
        "ending_equity":end_value,
        "net_profit":end_value-float(cfg.initial_cash),
        # The primary comparison uses investment-only returns, no idle cash.
        "invested_return_pct":(float(curve.market_value.iloc[-1])/cost-1)*100 if cost else None,
        "trading_profit":float(curve.market_value.iloc[-1])-cost,
        "total_sale_proceeds":0.0,
        "strategy_return_pct":(end_value/float(cfg.initial_cash)-1)*100,
        "max_drawdown_pct":float(curve.drawdown_pct.min()),
        "exposure_pct":float(curve.position.mean()*100),
        "skipped_insufficient_cash":skipped,
        "first_date":curve.index[0].date().isoformat(),
        "last_date":curve.index[-1].date().isoformat(),
        "external_contributions": external_contributions,
        "external_market_value":evalue,
        "external_profit": evalue-external_contributions,
        "external_return_on_contributions_pct": (
            (evalue/external_contributions - 1)*100 if external_contributions else None
        ),
        "external_xirr_pct": annual_irr,
        "open_trade": {
            "remaining_shares":float(shares),
            "remaining_cost":cost,
        } if shares>0 else None,
    }
    # The DCA account and strategy accounts must cover the exact same dates.
    return ledger, curve, result
