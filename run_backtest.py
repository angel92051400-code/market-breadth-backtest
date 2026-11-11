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

def run(args):
    output,cache = Path(args.output),Path(args.cache)
    output.mkdir(parents=True,exist_ok=True)
    breadth,meta=download_dashboard(cache,refresh=args.refresh_data)
    start=(breadth.index.min()-timedelta(days=7)).date().isoformat()
    end=(breadth.index.max()+timedelta(days=7)).date().isoformat()
    prices=download_etf(cache,start,end,ticker=args.ticker,refresh=args.refresh_data)
    cfg=Config(buy=args.buy,sell=args.sell,buy_amount=args.buy_amount,lookback=args.lookback,
        fib_tolerance=args.tolerance,confirm_window=args.confirm_window,
        buy_fee=args.buy_fee,sell_fee=args.sell_fee,sell_tax=args.sell_tax)
    signals=add_variant_signals(build_signals(breadth,cfg))
    signals.to_csv(output/'signal_diagnostics.csv',index_label='date')
    fig=make_subplots(rows=3,cols=1,shared_xaxes=True,row_heights=[.32,.32,.36],
        vertical_spacing=.07,subplot_titles=['市場寬度與門檻','加權指數與動態費波那契參考線','策略資金曲線'])
    fig.add_trace(go.Scatter(x=signals.index,y=signals.breadth,name='Market breadth',connectgaps=False),row=1,col=1)
    for level,label in [(args.buy,'Buy / recovery'),(args.sell,'Sell 50%'),(cfg.very_hot,'Very hot sell 50%')]:
        fig.add_hline(y=level,line_dash='dot',annotation_text=label,row=1,col=1)
    fig.add_trace(go.Scatter(x=signals.index,y=signals.taiex_close,name='TAIEX',line=dict(color='#d6dce9')),row=2,col=1)
    for key,name,color in [('fib_382','Fib 38.2%','#f1cb62'),('fib_500','Fib 50%','#e09d58'),('fib_618','Fib 61.8%','#a784ef')]:
        fig.add_trace(go.Scatter(x=signals.index,y=signals[key],name=name,line=dict(color=color,width=1,dash='dot'),connectgaps=False),row=2,col=1)
    for strategy,symbol,color in [('A','triangle-up','#ef7070'),('B','diamond','#49beee'),('C','star','#69d5a7'),
                                  ('A2','triangle-up-open','#e97e9e'),('B2','diamond-open','#74c6ef'),('C2','star-open','#82dfaf')]:
        entries=signals[signals['entry_'+strategy]]
        if len(entries):
            fig.add_trace(go.Scatter(x=entries.index,y=entries.taiex_close,mode='markers',
                marker=dict(symbol=symbol,size=9,color=color),name=f'{strategy} entry signal'),row=2,col=1)
    summaries=[]
    for strategy in ('A','B','C',*VARIANTS):
        trades,curve,summary=evaluate_portfolio(signals,prices,cfg,strategy)
        trades.to_csv(output/f'trades_{strategy}.csv',index=False)
        curve.to_csv(output/f'equity_{strategy}.csv',index_label='date')
        summaries.append(summary)
        fig.add_trace(go.Scatter(x=curve.index,y=curve.equity,name=f'Strategy {strategy}'),row=3,col=1)
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
            'B is pure Fibonacci and never uses market breadth. C combines breadth with Fibonacci and breadth-based exits.',
            'Exploratory analysis, not a verified profitable strategy.',
            'A2/B2/C2 are predeclared alternative hypotheses, not optimized on test data.',
            'Signal history begins with the oldest available dashboard day; Fibonacci requires a 120-session warmup.',
            'Orders: T+1 next ETF open, buy fixed 10000 TWD with available cash, sell 50% of then-held shares per exit event.',
            'Completed trades and win rate count partial SELL events, not full round trips. Portfolio return uses total equity and idle cash.'],
        'strategies':NAMES,
        'results':summaries}
    (output/'summary.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print('===== Backtest results =====')
    for s in summaries:
        print(f"Strategy {s['strategy']} | buys={s['buy_orders']} sells={s['sell_orders']} | win_rate={s['win_rate_pct']} | return={s['strategy_return_pct']} | maxDD={s['max_drawdown_pct']} | exposure={s['exposure_pct']:.1f}%")
    return summaries

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--ticker',default='0050.TW')
    p.add_argument('--buy',type=float,default=20)
    p.add_argument('--sell',type=float,default=50)
    p.add_argument('--buy-amount',type=float,default=10000)
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
