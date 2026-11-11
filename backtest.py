"""Causal end-of-day signals and next-day execution."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass
class Config:
    buy: float = 20.0
    sell: float = 70.0
    lookback: int = 120
    fib_tolerance: float = 0.03
    confirm_window: int = 5
    buy_fee: float = 0.001425
    sell_fee: float = 0.001425
    sell_tax: float = 0.001
    initial_cash: float = 100000.0

def fibonacci_support(taiex: pd.DataFrame, window=120) -> pd.DataFrame:
    """Reference extrema use only completed days before the signal close."""
    high = taiex['taiex_high'].shift(1).rolling(window, min_periods=window).max()
    low = taiex['taiex_low'].shift(1).rolling(window, min_periods=window).min()
    span = high - low
    out = pd.DataFrame(index=taiex.index)
    for f in (.382, .5, .618):
        out[f'fib_{int(round(f*1000))}'] = high - span*f
    out['rolling_high'] = high
    out['rolling_low'] = low
    return out

def build_signals(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    if not (0 < cfg.buy < cfg.sell < 100):
        raise ValueError('Require 0 < buy < sell < 100')
    if cfg.lookback < 2 or cfg.confirm_window < 1:
        raise ValueError('Invalid lookback / confirmation window')
    out = df.sort_index().copy().join(fibonacci_support(df.sort_index(), cfg.lookback))
    breadth, prev = out['breadth'], out['breadth'].shift(1)
    out['recovery'] = ((prev <= cfg.buy) & (breadth > cfg.buy)).fillna(False)
    out['exit_breadth'] = ((prev < cfg.sell) & (breadth >= cfg.sell)).fillna(False)
    price, levels = out['taiex_close'], out[['fib_382', 'fib_500', 'fib_618']]
    deviations = levels.sub(price, axis=0).abs().div(levels.replace(0, np.nan))
    out['near_fib'] = (deviations.min(axis=1) <= cfg.fib_tolerance).fillna(False)
    recent = out['recovery'].astype(int).rolling(cfg.confirm_window, min_periods=1).max().astype(bool)
    out['entry_A'] = out['recovery']
    # Pure Fibonacci: price retakes a known support level after closing at/below
    # the same level on the prior session. No breadth data enter strategy B.
    # Each candidate must be within tolerance ABOVE the reclaimed level.
    previous_price = price.shift(1)
    yesterday_levels = levels.shift(1)
    reclaimed = (previous_price.to_numpy()[:, None] <= yesterday_levels.to_numpy()) & (
        price.to_numpy()[:, None] >= levels.to_numpy()
    )
    within = (price.to_numpy()[:, None] <= levels.to_numpy()*(1+cfg.fib_tolerance))
    candidates = reclaimed & within & np.isfinite(levels.to_numpy())
    out['entry_B'] = candidates.any(axis=1)
    # Each B entry has an immutable price target and stop derived at signal
    # close; target is the next higher Fibonacci rung, stop is 3% below the
    # reclaimed rung. Trades are executed next session, not at signal close.
    sorted_levels = np.sort(levels.to_numpy(),axis=1)
    chosen_support, target = [], []
    for i in range(len(out)):
        indices = np.where(candidates[i])[0]
        if not len(indices):
            chosen_support.append(np.nan)
            target.append(np.nan)
            continue
        support = float(np.max(levels.iloc[i, indices]))
        higher = sorted_levels[i, sorted_levels[i] > support+1e-8]
        chosen_support.append(support)
        target.append(float(higher[0]) if len(higher) else float(out['rolling_high'].iloc[i]))
    out['fib_entry_support'] = chosen_support
    out['fib_entry_target'] = target
    out['entry_C'] = recent & out['near_fib'] & (breadth > cfg.buy) & breadth.notna()
    out['recovery_recent'] = recent
    return out

def evaluate(signals: pd.DataFrame, price: pd.DataFrame, cfg: Config, strategy: str):
    """One position. T close signal -> next common ETF trading-session open."""
    if strategy not in ('A', 'B', 'C'):
        raise ValueError('Unknown strategy')
    aligned = signals.join(price[['Open','Close']].rename(columns={'Open':'etf_open','Close':'etf_close'}), how='inner').sort_index()
    cash, shares, entry_date, entry_price, entry_cost, pending = cfg.initial_cash, 0.0, None, None, None, None
    fib_target = fib_stop = None
    trades, daily = [], []
    for i,(day,row) in enumerate(aligned.iterrows()):
        op, cl = row['etf_open'], row['etf_close']
        if pending:
            action, signal_day, pending_target, pending_stop = pending
            pending = None
            if pd.notna(op) and np.isfinite(op) and op > 0:
                if action == 'buy' and shares == 0:
                    shares = cash / (op*(1+cfg.buy_fee))
                    entry_cost = shares*op*(1+cfg.buy_fee)
                    cash = 0.0
                    entry_date, entry_price = day, float(op)
                    if strategy == 'B':
                        fib_target = float(pending_target)
                        fib_stop = float(pending_stop)
                elif action == 'sell' and shares > 0:
                    received = shares*op*(1-cfg.sell_fee-cfg.sell_tax)
                    cash = received
                    trades.append({
                        'entry_date':entry_date.date().isoformat(),
                        'exit_date':day.date().isoformat(),
                        'entry_price_adjusted':entry_price,
                        'exit_price_adjusted':float(op),
                        'holding_sessions':len(aligned.loc[entry_date:day])-1,
                        'net_return_pct':(received/entry_cost-1)*100,
                        'profit':received-entry_cost,
                        'exit_reason':exit_reason})
                    shares,entry_date,entry_price,entry_cost = 0.0,None,None,None
                    fib_target = fib_stop = None
        if i < len(aligned)-1 and pd.notna(cl) and np.isfinite(cl):
            if shares > 0:
                if strategy == 'B':
                    # Fixed TAIEX reference thresholds; no width condition.
                    close_index = row['taiex_close']
                    hit_target = pd.notna(close_index) and close_index >= fib_target
                    hit_stop = pd.notna(close_index) and close_index <= fib_stop
                    if hit_target or hit_stop:
                        exit_reason = 'fib_target' if hit_target else 'fib_stop'
                        pending = ('sell',day,None,None)
                elif bool(row['exit_breadth']):
                    exit_reason = 'breadth_70_cross'
                    pending = ('sell',day,None,None)
            elif bool(row['entry_'+strategy]):
                if strategy == 'B':
                    support = row['fib_entry_support']
                    target = row['fib_entry_target']
                    if pd.notna(support) and pd.notna(target):
                        pending = ('buy',day,target,support*(1-cfg.fib_tolerance))
                else:
                    pending = ('buy',day,None,None)
        equity = shares*cl if shares and pd.notna(cl) else (cash if shares==0 else np.nan)
        daily.append({'date':day,'equity':equity,'position':int(shares>0),
                      'breadth':row['breadth'],'etf_close':cl,
                      'pending_action':pending[0] if pending else ''})
    curve = pd.DataFrame(daily).set_index('date')
    trades_df = pd.DataFrame(trades)
    if not curve.empty:
        curve['drawdown_pct'] = (curve['equity']/curve['equity'].cummax()-1)*100
    open_trade = None
    if shares > 0 and not curve.empty:
        open_trade = {'entry_date':entry_date.date().isoformat(),
                      'unrealized_pct':(shares*curve['etf_close'].iloc[-1]/entry_cost-1)*100}
    n = len(trades_df)
    wins = int((trades_df['net_return_pct']>0).sum()) if n else 0
    first, last = (aligned['etf_close'].iloc[0],aligned['etf_close'].iloc[-1]) if len(aligned) else (np.nan,np.nan)
    summary = {
        'strategy':strategy,'completed_trades':n,'wins':wins,
        'win_rate_pct':float(wins/n*100) if n else None,
        'average_trade_return_pct':float(trades_df['net_return_pct'].mean()) if n else None,
        'median_trade_return_pct':float(trades_df['net_return_pct'].median()) if n else None,
        'strategy_return_pct':float((curve['equity'].iloc[-1]/cfg.initial_cash-1)*100) if len(curve) else None,
        'buy_hold_return_pct':float((last/first-1)*100) if pd.notna(first) and first>0 else None,
        'max_drawdown_pct':float(curve['drawdown_pct'].min()) if len(curve) else None,
        'open_trade':open_trade,
        'first_date':aligned.index[0].date().isoformat() if len(aligned) else None,
        'last_date':aligned.index[-1].date().isoformat() if len(aligned) else None}
    return trades_df,curve,summary
