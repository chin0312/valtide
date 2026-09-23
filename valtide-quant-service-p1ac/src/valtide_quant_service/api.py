from __future__ import annotations
from fastapi import FastAPI,HTTPException
from threading import Lock
app=FastAPI(title='Valtide Quant API Adapter',version='0.2.0')
_lock=Lock(); _latest={}
def put_latest(asset:str,result:dict):
    with _lock:_latest[asset]=dict(result)
@app.get('/api/valuation/{asset}')
def valuation(asset:str):
    with _lock:r=_latest.get(asset)
    if r is None:raise HTTPException(503,'data_unavailable')
    return r
@app.get('/api/assets')
def assets():
    with _lock:return {'assets':sorted(_latest)}
