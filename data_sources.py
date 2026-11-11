"""Frozen dashboard snapshot and adjusted ETF prices.

Current top-640 historical breadth is NOT a point-in-time constituent universe.
"""
from __future__ import annotations
import json
import hashlib
import re
from pathlib import Path
import numpy as np
import pandas as pd
import requests

SOURCE_URL = 'https://raw.githubusercontent.com/angel92051400-code/my-market-breadth/main/index.html'

def read_dashboard(html: str, universe: str='640') -> tuple[pd.DataFrame,dict]:
    match = re.search(r'<script\s+id=["\']market-data["\']\s+type=["\']application/json["\']>(.*?)</script>',html,re.S)
    if not match:
        raise ValueError('No market-data JSON found in dashboard HTML')
    d = json.loads(match.group(1))
    u = d['universes'][universe]
    idx = pd.to_datetime(d['dates']).normalize()
    frame = pd.DataFrame({
      'breadth':np.asarray(pd.to_numeric(u['values'],errors='coerce'),dtype=float),
      'valid':np.asarray(pd.to_numeric(u['valid'],errors='coerce'),dtype=float),
      'count':np.asarray(pd.to_numeric(u['counts'],errors='coerce'),dtype=float),
      'taiex_open':np.asarray(pd.to_numeric(d['candles']['open'],errors='coerce'),dtype=float),
      'taiex_high':np.asarray(pd.to_numeric(d['candles']['high'],errors='coerce'),dtype=float),
      'taiex_low':np.asarray(pd.to_numeric(d['candles']['low'],errors='coerce'),dtype=float),
      'taiex_close':np.asarray(pd.to_numeric(d['candles']['close'],errors='coerce'),dtype=float)}, index=idx)
    frame.index.name = 'date'
    frame.loc[frame['valid'] < np.ceil(int(u['total'])*.95), 'breadth'] = np.nan
    if frame.index.has_duplicates:
        raise ValueError('Dashboard includes duplicate dates')
    return frame.sort_index(),{'snapshot_date':d.get('snapshotDate'),'universe':universe,
        'total':int(u['total']),'sample_days':len(frame),'source':SOURCE_URL}

def download_dashboard(cache_dir:Path, *, url=SOURCE_URL, refresh=False):
    cache_dir.mkdir(parents=True,exist_ok=True)
    path = cache_dir/'dashboard_snapshot.html'
    if refresh or not path.exists():
        response = requests.get(url,timeout=60,headers={'User-Agent':'market-breadth-backtest/1.0'})
        response.raise_for_status()
        if 'market-data' not in response.text:
            raise ValueError('Dashboard data not found')
        path.write_text(response.text,encoding='utf-8')
    html = path.read_text(encoding='utf-8')
    data,meta = read_dashboard(html)
    meta['source']=url
    meta['source_sha256']=hashlib.sha256(html.encode('utf-8')).hexdigest()
    return data,meta

def _columns_for_symbol(df,ticker):
    if isinstance(df.columns,pd.MultiIndex):
        for level in range(df.columns.nlevels):
            if ticker in df.columns.get_level_values(level):
                return df.xs(ticker,axis=1,level=level)
    return df

def download_etf(cache_dir:Path,start:str,end:str,ticker='0050.TW',refresh=False):
    import yfinance as yf
    cache_dir.mkdir(parents=True,exist_ok=True)
    path=cache_dir/f"prices_{ticker.replace('.','_').replace('^','_')}.csv"
    if refresh or not path.exists():
        p = yf.download(ticker,start=start,end=end,auto_adjust=True,progress=False,threads=False)
        p = _columns_for_symbol(p,ticker)
        if p.empty:
            raise RuntimeError(f'No ETF price for {ticker}')
        p.index=pd.to_datetime(p.index).tz_localize(None).normalize()
        fields=['Open','High','Low','Close']
        if any(c not in p.columns for c in fields):
            raise ValueError('ETF OHLC fields missing')
        p[fields].dropna().to_csv(path,index_label='date')
    out=pd.read_csv(path,parse_dates=['date']).set_index('date').sort_index()
    for c in ('Open','High','Low','Close'):
        out[c]=pd.to_numeric(out[c],errors='coerce')
    return out
