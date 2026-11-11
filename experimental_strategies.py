"""Experimental repeatable trading variants; original A/B/C remain unchanged.

All parameters are declared before running. These variants are hypotheses, not
an optimized strategy. Decisions use signal-day close; execution uses next
common 0050 trading-day adjusted open. No future values enter signals.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


VARIANTS = {
    "A2": "市場寬度波段：寬度由下上穿40%買進；跌回40%、達65%或持有30日賣出",
    "B2": "費波那契反彈：回撤位上方3%內止跌回升買進；6%追蹤回撤或45日出場",
    "C2": "混合波段：寬度由下上穿40%且指數高於Fib50%買進；寬度失守40%、Fib50%失守或45日出場",
}


def add_variant_signals(signals: pd.DataFrame) -> pd.DataFrame:
    s = signals.copy()
    breadth = s["breadth"]
    price = s["taiex_close"]
    recent_levels = s[["fib_382", "fib_500", "fib_618"]]
    s["entry_A2"] = (
        (breadth.shift(1) <= 40) & (breadth > 40)
        & breadth.shift(1).notna() & breadth.notna()
    ).fillna(False)
    # B2 looks for the first up day after a down day, near and above one
    # dynamically computed Fibonacci support. No market-breadth dependency.
    close_to_support = recent_levels.le(price, axis=0) & recent_levels.mul(1.03).ge(price, axis=0)
    s["entry_B2"] = (
        (price > price.shift(1))
        & (price.shift(1) < price.shift(2))
        & close_to_support.any(axis=1)
    ).fillna(False)
    # Choose nearest support below current index close; fixed on entry signal.
    support = recent_levels.where(close_to_support).max(axis=1)
    s["b2_support"] = support
    s["entry_C2"] = (
        (breadth.shift(1) <= 40) & (breadth > 40)
        & breadth.shift(1).notna() & breadth.notna()
        & s["fib_500"].notna() & (price > s["fib_500"])
    ).fillna(False)
    return s


def evaluate_variant(signals: pd.DataFrame, prices: pd.DataFrame, cfg, strategy: str):
    """One fully invested position, next-open fill; costs and open trade included."""
    if strategy not in VARIANTS:
        raise ValueError(f"Unknown experimental strategy: {strategy}")
    aligned = signals.join(
        prices[["Open", "Close"]].rename(columns={"Open": "etf_open", "Close": "etf_close"}),
        how="inner",
    ).sort_index()
    if aligned.empty:
        raise ValueError("No overlapping ETF and signal history")
    cash = float(cfg.initial_cash)
    shares = 0.0
    pending = None
    entry_date = None
    entry_cost = entry_price = None
    entry_support = None
    entry_index = None
    highest_index = None
    age = 0
    trade_rows, curve_rows = [], []
    for i, (day, row) in enumerate(aligned.iterrows()):
        op, cl = row["etf_open"], row["etf_close"]
        # Execute only a signal generated on a prior session.
        if pending is not None:
            action, reason, signal_support = pending
            pending = None
            if pd.notna(op) and np.isfinite(op) and float(op) > 0:
                if action == "buy" and shares == 0:
                    shares = cash / (float(op) * (1 + cfg.buy_fee))
                    entry_cost = cash
                    cash = 0.0
                    entry_date, entry_price = day, float(op)
                    entry_support = signal_support
                    entry_index = i
                    highest_index = float(row["taiex_close"]) if pd.notna(row["taiex_close"]) else np.nan
                elif action == "sell" and shares > 0:
                    received = shares * float(op) * (1 - cfg.sell_fee - cfg.sell_tax)
                    cash = received
                    trade_rows.append({
                        "entry_date": entry_date.date().isoformat(),
                        "exit_date": day.date().isoformat(),
                        "entry_price_adjusted": entry_price,
                        "exit_price_adjusted": float(op),
                        "holding_sessions": i - entry_index,
                        "net_return_pct": (received / entry_cost - 1) * 100,
                        "profit": received - entry_cost,
                        "exit_reason": reason,
                    })
                    shares = 0.0
                    entry_date = entry_price = entry_cost = entry_support = entry_index = highest_index = None
        if shares > 0:
            age = i - entry_index
            index_close = row["taiex_close"]
            if pd.notna(index_close):
                highest_index = max(highest_index, float(index_close)) if pd.notna(highest_index) else float(index_close)
        else:
            age = 0

        if i < len(aligned) - 1 and pd.notna(cl) and np.isfinite(cl):
            if shares == 0 and bool(row["entry_" + strategy]):
                support = float(row["b2_support"]) if strategy == "B2" else None
                if strategy != "B2" or np.isfinite(support):
                    pending = ("buy", "signal", support)
            elif shares > 0:
                b, index_close = row["breadth"], row["taiex_close"]
                reason = None
                if strategy == "A2":
                    if pd.notna(b) and b >= 65:
                        reason = "breadth_65_take_profit"
                    elif pd.notna(b) and b < 40:
                        reason = "breadth_below_40"
                    elif age >= 30:
                        reason = "max_hold_30"
                elif strategy == "B2":
                    if pd.notna(index_close) and pd.notna(highest_index) and index_close <= highest_index * .94:
                        reason = "index_trailing_6pct"
                    elif pd.notna(index_close) and index_close < entry_support * .97:
                        reason = "support_failure_3pct"
                    elif age >= 45:
                        reason = "max_hold_45"
                elif strategy == "C2":
                    if pd.notna(b) and b < 40:
                        reason = "breadth_below_40"
                    elif pd.notna(index_close) and pd.notna(row["fib_500"]) and index_close < row["fib_500"]:
                        reason = "fib_50_failure"
                    elif age >= 45:
                        reason = "max_hold_45"
                if reason:
                    pending = ("sell", reason, None)

        equity = shares * float(cl) if shares > 0 and pd.notna(cl) else (cash if shares == 0 else np.nan)
        curve_rows.append({
            "date": day, "equity": equity, "position": int(shares > 0),
            "breadth": row["breadth"], "etf_close": cl,
            "pending_action": pending[0] if pending else "",
        })
    curve = pd.DataFrame(curve_rows).set_index("date")
    curve["drawdown_pct"] = (curve["equity"] / curve["equity"].cummax() - 1) * 100
    trades = pd.DataFrame(trade_rows, columns=[
        "entry_date", "exit_date", "entry_price_adjusted", "exit_price_adjusted",
        "holding_sessions", "net_return_pct", "profit", "exit_reason"
    ])
    n = len(trades)
    wins = int((trades["net_return_pct"] > 0).sum()) if n else 0
    first, last = aligned["etf_close"].iloc[0], aligned["etf_close"].iloc[-1]
    open_trade = None
    if shares > 0:
        open_trade = {
            "entry_date": entry_date.date().isoformat(),
            "unrealized_pct": float((curve["equity"].iloc[-1] / entry_cost - 1) * 100),
        }
    summary = {
        "strategy": strategy,
        "completed_trades": n,
        "wins": wins,
        "win_rate_pct": float(wins / n * 100) if n else None,
        "average_trade_return_pct": float(trades["net_return_pct"].mean()) if n else None,
        "median_trade_return_pct": float(trades["net_return_pct"].median()) if n else None,
        "strategy_return_pct": float((curve["equity"].iloc[-1] / cfg.initial_cash - 1) * 100),
        "buy_hold_return_pct": float((last / first - 1) * 100) if pd.notna(first) and first > 0 else None,
        "max_drawdown_pct": float(curve["drawdown_pct"].min()),
        "exposure_pct": float(curve["position"].mean() * 100),
        "open_trade": open_trade,
        "first_date": aligned.index[0].date().isoformat(),
        "last_date": aligned.index[-1].date().isoformat(),
    }
    return trades, curve, summary
