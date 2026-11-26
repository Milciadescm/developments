"""V1 contra V2 de Prop24 con las reglas exactas de GFT Instant Premium $100K (0.9 %, 1 % flotante, 5 dias rentables por pago,
6 % trailing, 80 %).  python -m fibfvg.gft_v2 -> results/gft_v2.json"""
import pandas as pd, numpy as np, json
from fibfvg import fractal24, gft
from fibfvg.prop24 import build
NOW=gft.NOW; y1=NOW-pd.Timedelta(days=365)
out={}
for name,win in (("V1 (corre en la demo)",None),("V2 08-18 NY",(8,18))):
    fractal24.ENTRY_HOURS_NY=win
    a,b=build(); P=sorted([t for t in a+b if t.symbol in("BTCUSD","US500","NAS100")],key=lambda t:t.entry_time)
    days,sk,tk=gft.daily_pnl(P,0.009,0.01)
    full=gft.account(days,0.8,5,None,0.06,True); last=gft.account(days,0.8,5,None,0.06,True,start=y1,end=NOW)
    # inicio cada mes, 12 meses
    st=pd.date_range("2024-08-01","2025-11-01",freq="MS",tz="UTC"); w=[gft.account(days,0.8,5,None,0.06,True,start=s,end=s+pd.Timedelta(days=365)) for s in st]
    eq=days.cumsum(); dd=float((eq.cummax()-eq).max()/1000)
    out[name]=dict(operaciones=tk,saltadas_1pct=sk,dias_rentables=int((days>=500).sum()),cobrado_total=full["paid"],pagos=full["payouts"],quemada=full["breach"],
                   ultimos_12m=last["paid"],pagos_12m=last["payouts"],mediana_12m=int(np.median([x["paid"] for x in w])),peor_12m=min(x["paid"] for x in w),
                   quemadas=sum(bool(x["breach"]) for x in w),peor_caida_pct=round(dd,2),lista=full["list"])
    print(name,{k:v for k,v in out[name].items() if k!="lista"})
fractal24.ENTRY_HOURS_NY=None
json.dump(out,open("results/gft_v2.json","w"),indent=1,ensure_ascii=False)
