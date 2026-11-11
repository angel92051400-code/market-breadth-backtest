"""Predeclared v3 signals. All references through the signal-day close only.

Keep historical strategy code archived, but the active daily comparison contains
A, A3, B4, C3, D and monthly DCA. No optimization on historical outcomes.
"""
import numpy as np
import pandas as pd

ACTIVE_STRATEGIES = ("A","A3","B4","C3","D")
DESCRIPTIONS = {
"A":"市場寬度原版：從20%以下回升買10,000元，過熱50%/60%各賣現有股票一半",
"A3":"寬度趨勢：上穿30%買進，跌回50%或指數跌破20日均線減碼50%",
"B4":"費波那契波段：回撤區下跌後止跌反彈、同一波段只買一次；失守支撐或回撤6%減碼",
"C3":"寬度加費波那契：30%回升後5日內在回撤位附近止跌買進，寬度與指數同時轉弱或支撐失守減碼",
"D":"趨勢追蹤：加權指數突破前60交易日高點買進，跌破20日均線減碼",
}

def add_v3_signals(s:pd.DataFrame)->pd.DataFrame:
    out=s.copy()
    px=out["taiex_close"]
    b=out["breadth"]
    out["sma20"] = px.shift(1).rolling(20,min_periods=20).mean()
    out["high60"] = out["taiex_high"].shift(1).rolling(60,min_periods=60).max()
    out["entry_A3"] = ((b.shift(1)<=30)&(b>30)&b.shift(1).notna()).fillna(False)
    out["exit_A3_breadth"]=((b.shift(1)>=50)&(b<50)).fillna(False)
    out["exit_A3_trend"]=((px.shift(1)>=out.sma20.shift(1))&(px<out.sma20)).fillna(False)
    # A support is derived only from 120 *completed* trading sessions.
    high, low=out["rolling_high"],out["rolling_low"]
    span=high-low
    levels=pd.DataFrame({str(f):high-span*f for f in (.236,.382,.5,.618,.786)},index=out.index)
    gap=levels.sub(px,axis=0).abs().div(levels.replace(0,np.nan))
    closest=gap.idxmin(axis=1).fillna("")
    out["b4_support"]=pd.Series([
       float(levels.at[day,key]) if key in levels.columns else np.nan
       for day,key in zip(out.index,closest)
    ],index=out.index)
    # The support zone is +/-6%. A down session arms a zone; an ensuing up
    # session within the next 3 sessions confirms. After buying, rearm only
    # after 3 consecutive sessions outside +/-8% of the *locked* support.
    within=gap.min(axis=1).le(.06)&span.gt(0)
    rising=px.gt(px.shift(1))
    falling=px.lt(px.shift(1))
    b4_buy=[]
    armed_until=-1
    disarmed_support=None
    outside_streak=0
    for i in range(len(out)):
        if disarmed_support is not None:
            p=px.iat[i]
            if pd.notna(p) and (p>disarmed_support*1.08 or p<disarmed_support*.92):
                outside_streak+=1
            else:
                outside_streak=0
            if outside_streak>=3:
                disarmed_support=None
                outside_streak=0
        if disarmed_support is None and bool(within.iat[i]) and bool(falling.iat[i]):
            armed_until=i+3
        buy=bool(disarmed_support is None and i<=armed_until
                 and within.iat[i] and rising.iat[i]
                 and pd.notna(out["b4_support"].iat[i]))
        if buy:
            disarmed_support=float(out["b4_support"].iat[i])
            armed_until=-1
        b4_buy.append(buy)
    out["entry_B4"]=b4_buy
    # Breadth recovery within preceding 5 sessions + Fib rebound; no
    # lookahead and no demand that both events fall on the same date.
    recovery=((b.shift(1)<=30)&(b>30)&b.shift(1).notna()).fillna(False)
    out["entry_C3"]=(
        recovery.astype(int).rolling(5,min_periods=1).max().astype(bool)
        & b.gt(30) & b.notna() & within & rising
    ).fillna(False)
    # Only one C3 entry per breadth recovery event even if the rolling
    # five-day confirmation window stays true for several sessions.
    candidate=out["entry_C3"].copy()
    segment=recovery.cumsum()
    out["entry_C3"]=candidate & candidate.groupby(segment).cumsum().eq(1)
    out["c3_support"]=out["b4_support"]
    out["exit_C3_weak"]=(
        b.lt(50)&px.lt(out["sma20"]) &
        ~(b.shift(1).lt(50)&px.shift(1).lt(out["sma20"].shift(1)))
    ).fillna(False)
    out["entry_D"]=(
        px.gt(out["high60"]) &
        px.shift(1).le(out["high60"].shift(1)) &
        out["high60"].notna()
    ).fillna(False)
    out["exit_D"]=((px.shift(1)>=out["sma20"].shift(1))&(px<out["sma20"])).fillna(False)
    return out
