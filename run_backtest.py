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

def run(args):
    output,cache = Path(args.output),Path(args.cache)
    output.mkdir(parents=True,exist_ok=True)
    breadth,meta=download_dashboard(cache,refresh=args.refresh_data)
    start=(breadth.index.min()-timedelta(days=7)).date().isoformat()
    end=(breadth.index.max()+timedelta(days=7)).date().isoformat()
    prices=download_etf(cache,start,end,ticker=args.ticker,refresh=args.refresh_data)
    cfg=Config(buy=args.buy,sell=args.sell,lookback=args.lookback,
        fib_tolerance=args.tolerance,confirm_window=args.confirm_window,
        buy_fee=args.buy_fee,sell_fee=args.sell_fee,sell_tax=args.sell_tax)
    signals=build_signals(breadth,cfg)
    signals.to_csv(output/'signal_diagnostics.csv',index_label='date')
    fig=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.55,.45],
        vertical_spacing=.1,subplot_titles=['市場寬度（有效樣本）與交易門檻','策略資金曲線'])
    fig.add_trace(go.Scatter(x=signals.index,y=signals.breadth,name='Market breadth',connectgaps=False),row=1,col=1)
    for level,label in [(args.buy,'Buy / recovery'),(args.sell,'Sell')]:
        fig.add_hline(y=level,line_dash='dot',annotation_text=label,row=1,col=1)
    summaries=[]
    for strategy in ('A','B'):
        trades,curve,summary=evaluate(signals,prices,cfg,strategy)
        trades.to_csv(output/f'trades_{strategy}.csv',index=False)
        curve.to_csv(output/f'equity_{strategy}.csv',index_label='date')
        summaries.append(summary)
        fig.add_trace(go.Scatter(x=curve.index,y=curve.equity,name=f'Strategy {strategy}'),row=2,col=1)
    fig.update_layout(title=f'市場寬度策略回測 | {args.ticker} | 資料日 {meta["snapshot_date"]}',
        template='plotly_dark',height=800,hovermode='x unified')
    fig.write_html(output/'report.html',include_plotlyjs='cdn')
    pd.DataFrame([{k:v for k,v in s.items() if k!='open_trade'} for s in summaries]).to_csv(output/'summary.csv',index=False)
    metadata={'source':meta,'ticker':args.ticker,'config':vars(cfg),
        'limitations':[
            'Historical top-640 universe uses present-day constituent list (survivorship and look-ahead bias).',
            'Below 95% quote coverage breadth is missing; signals must not use interpolation.',
            'Adjusted Yahoo OHLC is a total-return proxy, not an executable raw price.',
            'All Fibonacci levels use trailing highs/lows through signal close; next-open trade.',
            'Exploratory analysis, not a verified profitable strategy.'],
        'results':summaries}
    (output/'summary.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print('===== Backtest results =====')
    for s in summaries:
        print(f"Strategy {s['strategy']} | trades={s['completed_trades']} | wins={s['wins']} | win_rate={s['win_rate_pct']} | return={s['strategy_return_pct']} | maxDD={s['max_drawdown_pct']}")
    return summaries

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--ticker',default='0050.TW')
    p.add_argument('--buy',type=float,default=20)
    p.add_argument('--sell',type=float,default=70)
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
