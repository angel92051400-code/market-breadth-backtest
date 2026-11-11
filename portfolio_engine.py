"""Tranche-based 0050 backtesting for baseline and exploratory strategies.

Buy $10,000 per new entry signal, independent of whether already holding.
Each distinct exit event sells 50% of the *then-current* share position.
A session crossing both hot thresholds 50/60 creates two events, hence
sequentially sells 50% then 50% of remaining shares (75% total).

All signal decisions use data at day t close and fill at the next common
trading session's ETF adjusted open. Trades require cash, use weighted-average
cost accounting for realized P/L, and value remaining shares at last close.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

STRATEGIES = ("A", "B", "C", "A2", "B2", "C2", "B3")
NAMES = {
    "A": "原版：寬度20%反彈買進，50/60%分兩階段減碼",
    "B": "原版：費波那契收復支撐買進，達固定目標或跌破支撐減碼",
    "C": "原版：寬度過冷反彈＋費波那契，50/60%減碼",
    "A2": "寬度40%波段買進，50/60%減碼，失守40%或30日風控",
    "B2": "費波那契反彈買進，6%追蹤回撤、失守支撐或45日減碼",
    "C2": "寬度40%＋Fib50%買進，50/60%減碼，跌破條件或45日風控",
    "B3": "寬鬆費波那契回升（距回撤位±6%），1.414倍延伸目標或風控半數賣出",
}


def _cross_up(current, previous, threshold):
    return pd.notna(current) and pd.notna(previous) and previous < threshold <= current


def _cross_down(current, previous, threshold, old_threshold=None):
    old = threshold if old_threshold is None else old_threshold
    return (
        pd.notna(current) and pd.notna(previous)
        and pd.notna(threshold) and pd.notna(old)
        and previous >= old and current < threshold
    )


def _new_orders(s, i, strategy, cfg, lots_active, age, fib_state):
    row = s.iloc[i]
    prior = s.iloc[i-1] if i > 0 else None
    signal_date = s.index[i]
    breadth = row["breadth"]
    old_b = prior["breadth"] if prior is not None else np.nan
    index = row["taiex_close"]
    old_index = prior["taiex_close"] if prior is not None else np.nan
    exits = []
    if lots_active:
        if strategy in ("A", "C", "A2", "C2"):
            if _cross_up(breadth, old_b, cfg.sell):
                exits.append("breadth_cross_50")
            if _cross_up(breadth, old_b, cfg.very_hot):
                exits.append("breadth_cross_60")
            if strategy in ("A2", "C2"):
                if _cross_down(breadth, old_b, 40):
                    exits.insert(0, "breadth_below_40")
                if strategy == "C2" and prior is not None and _cross_down(
                    index, old_index, row["fib_500"], prior["fib_500"]
                ):
                    exits.insert(0, "fib_50_failure")
                hold_limit = 30 if strategy == "A2" else 45
                if age == hold_limit:
                    exits.append(f"max_hold_{hold_limit}")
            # Safety exit takes priority over independent hot-tier events.
            if exits and exits[0] in ("breadth_below_40", "fib_50_failure"):
                exits = exits[:1]
        elif strategy == "B":
            target, stop = fib_state["target"], fib_state["stop"]
            if target is not None and _cross_up(index, old_index, target):
                exits.append("fib_target")
            elif stop is not None and _cross_down(index, old_index, stop):
                exits.append("fib_stop")
        elif strategy == "B3":
            target, stop = fib_state["target"], fib_state["stop"]
            if target is not None and _cross_up(index, old_index, target):
                exits.append("fib_extension_1414")
            elif stop is not None and _cross_down(index, old_index, stop):
                exits.append("fib_support_failure_6pct")
            elif age == 60:
                exits.append("max_hold_60")
        elif strategy == "B2":
            stop = fib_state["support"]
            trail = fib_state["previous_high"]
            if stop is not None and _cross_down(index, old_index, stop * .97):
                exits.append("support_failure_3pct")
            elif trail is not None and _cross_down(index, old_index, trail * .94):
                exits.append("index_trailing_6pct")
            elif age == 45:
                exits.append("max_hold_45")
    if exits:
        return [("sell", reason, signal_date, None, None) for reason in exits]
    if bool(row["entry_" + strategy]):
        support = None
        target = None
        if strategy == "B":
            if pd.notna(row["fib_entry_support"]) and pd.notna(row["fib_entry_target"]):
                support = float(row["fib_entry_support"])
                target = float(row["fib_entry_target"])
            else:
                return []
        if strategy == "B3":
            if pd.notna(row["b3_support"]) and pd.notna(row["b3_target"]):
                support = float(row["b3_support"])
                target = float(row["b3_target"])
            else:
                return []
        if strategy == "B2":
            if pd.notna(row["b2_support"]):
                support = float(row["b2_support"])
            else:
                return []
        return [("buy", "entry_" + strategy, signal_date, support, target)]
    return []


def evaluate_portfolio(signals: pd.DataFrame, prices: pd.DataFrame, cfg, strategy: str):
    """One shared cash/share ledger for original A/B/C and alternative variants."""
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy {strategy}")
    if not (0 < cfg.buy < cfg.sell < cfg.very_hot <= 100):
        raise ValueError("Thresholds must increase: buy < hot < very hot")
    if not (0 < cfg.sell_fraction <= 1 and cfg.buy_amount > 0 and cfg.initial_cash > 0):
        raise ValueError("Invalid order size or sell fraction")
    aligned = signals.join(
        prices[["Open", "Close"]].rename(columns={"Open":"etf_open","Close":"etf_close"}),
        how="inner"
    ).sort_index()
    if aligned.empty:
        raise ValueError("No overlapping ETF and breadth history")
    cash, shares, cost_basis = float(cfg.initial_cash), 0.0, 0.0
    pending = []
    rows, curve_rows = [], []
    buys, sells, skipped_buys = 0, 0, 0
    first_entry_idx = None
    first_entry_date = None
    fib_state = {"target":None, "stop":None, "support":None, "previous_high":None}
    previous_index = np.nan
    for i, (day, row) in enumerate(aligned.iterrows()):
        op, cl = row["etf_open"], row["etf_close"]
        # Pending orders were created only after the prior session close.
        if pending and pd.notna(op) and np.isfinite(op) and op > 0:
            for action, reason, signal_day, support, target in pending:
                if action == "buy":
                    if cash + 1e-8 < cfg.buy_amount:
                        skipped_buys += 1
                        continue
                    amount = float(cfg.buy_amount)
                    qty = amount / (float(op) * (1 + cfg.buy_fee))
                    cash -= amount
                    shares += qty
                    cost_basis += amount
                    buys += 1
                    if first_entry_idx is None:
                        first_entry_idx = i
                        first_entry_date = day
                    if strategy == "B":
                        fib_state["target"] = target
                        fib_state["stop"] = support * (1-cfg.fib_tolerance)
                    if strategy == "B3":
                        fib_state["target"] = target
                        fib_state["stop"] = support * .94
                    if strategy == "B2":
                        fib_state["support"] = support
                        fib_state["previous_high"] = float(row["taiex_close"]) if pd.notna(row["taiex_close"]) else None
                    rows.append({
                        "signal_date":signal_day.date().isoformat(),
                        "date":day.date().isoformat(), "strategy":strategy,
                        "action":"BUY","reason":reason,"price_adjusted":float(op),
                        "shares":qty,"gross_value":amount,"realized_profit":np.nan,
                        "realized_return_pct":np.nan,"cash_after":cash,"shares_after":shares,
                    })
                elif action == "sell" and shares > 1e-12:
                    qty = shares * cfg.sell_fraction
                    proceeds = qty * float(op) * (1-cfg.sell_fee-cfg.sell_tax)
                    allocated_cost = cost_basis * (qty/shares)
                    profit = proceeds-allocated_cost
                    shares -= qty
                    cost_basis -= allocated_cost
                    cash += proceeds
                    sells += 1
                    rows.append({
                        "signal_date":signal_day.date().isoformat(),
                        "date":day.date().isoformat(), "strategy":strategy,
                        "action":"SELL","reason":reason,"price_adjusted":float(op),
                        "shares":qty,"gross_value":proceeds,
                        "realized_profit":profit,
                        "realized_return_pct":(proceeds/allocated_cost-1)*100 if allocated_cost>0 else np.nan,
                        "cash_after":cash,"shares_after":shares,
                    })
        pending = []
        # Index high is tracked after fills. For B2, use the last *completed*
        # session high for trail crossing, then include current close.
        index_now = row["taiex_close"]
        if shares > 0 and strategy == "B2" and pd.notna(index_now):
            hi = fib_state["previous_high"]
            if hi is None or not np.isfinite(hi):
                fib_state["previous_high"] = float(index_now)
            else:
                fib_state["previous_high"] = max(float(hi),float(index_now))
        age = i-first_entry_idx if first_entry_idx is not None and shares > 0 else 0
        if i < len(aligned)-1 and pd.notna(cl) and np.isfinite(cl):
            # The indicator frame is restricted to dates where 0050 trades.
            # Signals are generated only on this day's fully known close.
            pending = _new_orders(aligned,i,strategy,cfg,shares>0,age,fib_state)
        equity = cash+shares*float(cl) if pd.notna(cl) and np.isfinite(cl) else np.nan
        curve_rows.append({
            "date":day,"equity":equity,"cash":cash,"shares":shares,
            "market_value":shares*float(cl) if pd.notna(cl) else np.nan,
            "position":int(shares>0),"breadth":row["breadth"],
            "etf_close":cl,"pending_action":";".join(x[0] for x in pending)
        })
        previous_index = index_now
    ledger = pd.DataFrame(rows,columns=[
        "signal_date","date","strategy","action","reason","price_adjusted","shares",
        "gross_value","realized_profit","realized_return_pct","cash_after","shares_after",
    ])
    curve = pd.DataFrame(curve_rows).set_index("date")
    curve["drawdown_pct"] = (curve["equity"]/curve["equity"].cummax()-1)*100
    n = len(ledger.loc[ledger.action=="SELL"])
    win = int((ledger.loc[ledger.action=="SELL","realized_profit"]>0).sum())
    first,last = aligned["etf_close"].iloc[0],aligned["etf_close"].iloc[-1]
    open_trade = None
    if shares > 1e-12:
        open_trade = {
            "entry_date":first_entry_date.date().isoformat() if first_entry_date is not None else None,
            "remaining_shares":float(shares),
            "remaining_cost":float(cost_basis),
            "unrealized_pct":float((shares*float(last)/cost_basis-1)*100) if cost_basis>0 else None,
        }
    realized = ledger.loc[ledger.action=="SELL","realized_return_pct"]
    purchases = float(ledger.loc[ledger.action=="BUY","gross_value"].sum())
    sales = float(ledger.loc[ledger.action=="SELL","gross_value"].sum())
    remaining_value = float(shares*last)
    profit_on_trades = sales+remaining_value-purchases
    # User's primary view: investment profit divided by actually executed
    # purchases. Idle cash is explicitly excluded. A reused dollar is counted
    # again on each purchase; disclose this turnover-based denominator.
    traded_roi = (profit_on_trades/purchases*100) if purchases>0 else None
    stats = {
        "strategy":strategy,"completed_trades":n,"buy_orders":buys,"sell_orders":sells,
        "total_invested":purchases,
        "total_sale_proceeds":sales,
        "ending_market_value":remaining_value,
        "trading_profit":profit_on_trades,
        "invested_return_pct":traded_roi,
        "skipped_buys_insufficient_cash":skipped_buys,
        "wins":win,"win_rate_pct":float(win/n*100) if n else None,
        "average_trade_return_pct":float(realized.mean()) if n else None,
        "median_trade_return_pct":float(realized.median()) if n else None,
        "strategy_return_pct":float((curve["equity"].iloc[-1]/cfg.initial_cash-1)*100),
        "buy_hold_return_pct":float((last/first-1)*100) if pd.notna(first) and first>0 else None,
        "max_drawdown_pct":float(curve["drawdown_pct"].min()),
        "exposure_pct":float(curve["position"].mean()*100),
        "open_trade":open_trade,
        "first_date":aligned.index[0].date().isoformat(),
        "last_date":aligned.index[-1].date().isoformat(),
    }
    return ledger,curve,stats
