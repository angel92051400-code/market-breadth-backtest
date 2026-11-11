"""Run independent reproducible breadth/Fibonacci research backtests."""
import argparse
import json
from datetime import timedelta
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from data_sources import download_dashboard,download_etf
from backtest import Config,build_signals,evaluate
from experimental_strategies import VARIANTS,add_variant_signals
from portfolio_engine import evaluate_portfolio, NAMES
from strategy_v3 import ACTIVE_STRATEGIES, DESCRIPTIONS, add_v3_signals
from dca_baseline import evaluate_monthly_dca

def run(args):
    output,cache = Path(args.output),Path(args.cache)
    output.mkdir(parents=True,exist_ok=True)
    breadth,meta=download_dashboard(cache,refresh=args.refresh_data)
    start=(breadth.index.min()-timedelta(days=7)).date().isoformat()
    end=(breadth.index.max()+timedelta(days=7)).date().isoformat()
    prices=download_etf(cache,start,end,ticker=args.ticker,refresh=args.refresh_data)
    leveraged_prices=download_etf(cache,start,end,ticker="00631L.TW",refresh=args.refresh_data)
    # Exact matched dates for both assets so all timing comparisons are fair.
    common=signals_dates = breadth.index.intersection(prices.index).intersection(leveraged_prices.index)
    if len(common) < 120:
        raise RuntimeError("0050 / 00631L common trading history shorter than 120 sessions")
    prices=prices.loc[common]
    leveraged_prices=leveraged_prices.loc[common]
    cfg=Config(buy=args.buy,sell=args.sell,buy_amount=args.buy_amount,lookback=args.lookback,
        fib_tolerance=args.tolerance,confirm_window=args.confirm_window,
        buy_fee=args.buy_fee,sell_fee=args.sell_fee,sell_tax=args.sell_tax)
    signals=add_v3_signals(add_variant_signals(build_signals(breadth,cfg)))
    signals.to_csv(output/'signal_diagnostics.csv',index_label='date')
    fig=make_subplots(rows=3,cols=1,shared_xaxes=True,row_heights=[.32,.32,.36],
        vertical_spacing=.07,subplot_titles=['市場寬度與門檻','加權指數與動態費波那契參考線','實際外部本金報酬率（無固定資金上限）'])
    fig.add_trace(go.Scatter(x=signals.index,y=signals.breadth,name='Market breadth',connectgaps=False),row=1,col=1)
    for level,label in [(args.buy,'Buy / recovery'),(args.sell,'Sell 50%'),(cfg.very_hot,'Very hot sell 50%')]:
        fig.add_hline(y=level,line_dash='dot',annotation_text=label,row=1,col=1)
    fig.add_trace(go.Scatter(x=signals.index,y=signals.taiex_close,name='TAIEX',line=dict(color='#d6dce9')),row=2,col=1)
    for key,name,color in [('fib_382','Fib 38.2%','#f1cb62'),('fib_500','Fib 50%','#e09d58'),('fib_618','Fib 61.8%','#a784ef')]:
        fig.add_trace(go.Scatter(x=signals.index,y=signals[key],name=name,line=dict(color=color,width=1,dash='dot'),connectgaps=False),row=2,col=1)
    for strategy,symbol,color in [('A','triangle-up','#ef7070'),('A3','triangle-up-open','#fbbf77'),
                                  ('B4','diamond','#49beee'),('C3','star','#69d5a7'),('D','square-open','#a784ef')]:
        entries=signals[signals['entry_'+strategy]]
        if len(entries):
            fig.add_trace(go.Scatter(x=entries.index,y=entries.taiex_close,mode='markers',
                marker=dict(symbol=symbol,size=9,color=color),name=f'{strategy} entry signal'),row=2,col=1)
    summaries=[]
    for strategy in ACTIVE_STRATEGIES:
        trades,curve,summary=evaluate_portfolio(signals,prices,cfg,strategy)
        trades.to_csv(output/f'trades_{strategy}.csv',index=False)
        curve.to_csv(output/f'equity_{strategy}.csv',index_label='date')
        summaries.append(summary)
        fig.add_trace(go.Scatter(x=curve.index,y=curve.capital_roi_pct,name=f'Strategy {strategy}'),row=3,col=1)
    # Run identical signal dates, cash, costs and tranches on true 00631L
    # adjusted prices (never approximate it as twice 0050's accumulated return).
    leveraged_summaries=[]
    for strategy in ACTIVE_STRATEGIES:
        lev_ledger,lev_curve,lev_summary=evaluate_portfolio(signals,leveraged_prices,cfg,strategy)
        lev_ledger.to_csv(output/f'trades_00631L_{strategy}.csv',index=False)
        lev_curve.to_csv(output/f'equity_00631L_{strategy}.csv',index_label='date')
        leveraged_summaries.append(lev_summary)
    lev_dca_ledger,lev_dca_curve,lev_dca=evaluate_monthly_dca(leveraged_prices,cfg,monthly_amount=args.dca_amount)
    lev_dca_ledger.to_csv(output/'trades_00631L_DCA.csv',index=False)
    lev_dca_curve.to_csv(output/'equity_00631L_DCA.csv',index_label='date')
    leveraged_summaries.append(lev_dca)
    # Re-use same matched day horizon for fair paired comparison.
    (output/'comparison_00631L.json').write_text(json.dumps({
        'ticker':'00631L.TW',
        'risk_note':'Daily 2x Taiwan 50 index target; path-dependent, not twice multi-day 0050 return.',
        'first_date':common.min().strftime('%Y-%m-%d'),
        'last_date':common.max().strftime('%Y-%m-%d'),
        'sample_days':len(common),
        'results':leveraged_summaries,
    },ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    # Fair comparison: DCA is funded by the SAME initial NT$100,000 cash
    # as every timed strategy. Its monthly purchases are not extra deposits.
    aligned_etf = prices.loc[prices.index.intersection(signals.index)].sort_index()
    dca_ledger,dca_curve,dca_summary=evaluate_monthly_dca(
        aligned_etf,cfg,monthly_amount=args.dca_amount)
    # Common buy/hold is intentionally the same reference across all rows.
    lev_dca['buy_hold_return_pct']=leveraged_summaries[0]['buy_hold_return_pct']
    dca_summary['buy_hold_return_pct'] = summaries[0]['buy_hold_return_pct']
    dca_ledger.to_csv(output/'trades_DCA.csv',index=False)
    dca_curve.to_csv(output/'equity_DCA.csv',index_label='date')
    summaries.append(dca_summary)
    fig.add_trace(go.Scatter(
        x=dca_curve.index,y=dca_curve.invested_roi_pct,name='0050 月初定期定額 3000（實際投入報酬）'
    ),row=3,col=1)
    fig.update_yaxes(title_text='外部本金報酬率 (%)',row=3,col=1)
    fig.update_layout(title=f'市場寬度策略回測 | {args.ticker} | 資料日 {meta["snapshot_date"]}',
        template='plotly_dark',height=1080,hovermode='x unified')
    fig.write_html(output/'report.html',include_plotlyjs='cdn')
    pd.DataFrame([{k:v for k,v in s.items() if k!='open_trade'} for s in summaries]).to_csv(output/'summary.csv',index=False)
    metadata={'source':meta,'ticker':args.ticker,'config':vars(cfg),
        'limitations':[
            'Historical top-640 universe uses present-day constituent list (survivorship and look-ahead bias).',
            'Below 95% quote coverage breadth is missing; signals must not use interpolation.',
            'Adjusted Yahoo OHLC is a total-return proxy, not an executable raw price.',
            'Fibonacci levels use only prior completed sessions; next-open trade.',
            'B4 is breadth-independent Fibonacci. C3 combines breadth confirmation and Fibonacci support. D is independent trend-following.',
            'Exploratory analysis, not a verified profitable strategy.',
            'A3/B4/C3/D are exploratory alternatives proposed after inspecting the old backtest; they are not independent out-of-sample results.',
            'Signal history begins with the oldest available dashboard day; Fibonacci requires a 120-session warmup.',
            'Orders: T+1 next ETF open, buy 10000 TWD on every signal, inject external shortfall without cap, sell 50% on each distinct exit event.',
            'Completed trades and win rate count partial SELL events; strategy capital ROI excludes unused cash and counts only actually deposited funds.',
            '0050 buy/hold return is the SAME common market benchmark for all strategies; equal values are intentional.',
            'DCA prefunded benchmark uses initial 100000 in cash and invests 3000 once per calendar month on first ETF trading day. Costs and cash included.',
            'Contributions-only DCA assumes NEW 3000 monthly external funds; contribution return/XIRR are not directly comparable with 100000 initial capital strategy returns.',
            '00631L targets 2x Taiwan 50 DAILY, subject to daily compounding, leverage and trading qualification; do not infer long-run return as twice 0050.',
            '0050 and 00631L are compared over their exact shared trading-session intersection.',
            'Strategy ROI uses only actual external deposits to fund buys: (realized plus unrealized profit) / deposits. No initial 100000 cap.',
            'Gross buy totals count recycled sale proceeds; external deposits do not. Always buy 10000 per valid signal, injecting shortfalls and separately reporting XIRR.'],
        'strategies':{**DESCRIPTIONS,'DCA':'每月第一個交易日投入3000元0050；另列外部逐月投入及XIRR'},
        'leveraged_comparison':{
            'ticker':'00631L.TW',
            'matched_dates':len(common),
            'first_date':common.min().strftime('%Y-%m-%d'),
            'last_date':common.max().strftime('%Y-%m-%d'),
            'results':leveraged_summaries},
        'results':summaries,
        'comparison_note':'日常啟用 A/A3/B4/C3/D 加月初3000定期定額。舊版 B/C/A2/B2/C2/B3 已封存，不進入日常績效排名。策略本金採買進時現金不足的外部補款累計，不設10萬上限；已實現與未實現獲利除以實際外部補款。'}
    (output/'summary.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print('===== Backtest results =====')
    for s in summaries:
        print(f"Strategy {s['strategy']} | buys={s['buy_orders']} sells={s['sell_orders']} | win_rate={s['win_rate_pct']} | return={s['strategy_return_pct']} | maxDD={s['max_drawdown_pct']} | exposure={s['exposure_pct']:.1f}%")
    print(f"Monthly DCA: initial cash={cfg.initial_cash:.0f}, monthly buy={args.dca_amount:.0f}, "
          f"invested={dca_summary['total_invested']:.0f}, "
          f"ending value={dca_summary['ending_equity']:.2f}, "
          f"external XIRR={dca_summary['external_xirr_pct']}")
    return summaries

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--ticker',default='0050.TW')
    p.add_argument('--buy',type=float,default=20)
    p.add_argument('--sell',type=float,default=50)
    p.add_argument('--buy-amount',type=float,default=10000)
    p.add_argument('--dca-amount',type=float,default=3000)
    p.add_argument('--lookback',type=int,default=120)
    p.add_argument('--tolerance',type=float,default=.03)
    p.add_argument('--confirm-window',type=int,default=5)
    p.add_argument('--buy-fee',type=float,default=.001425)
    p.add_argument('--sell-fee',type=float,default=.001425)
    p.add_argument('--sell-tax',type=float,default=.001)
    p.add_argument('--refresh-data',action='store_true')
    p.add_argument('--cache',default='cache')
    p.add_argument('--output',default='output')
    run(p.parse_args())
