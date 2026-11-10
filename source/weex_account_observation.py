"""Shared account observation for diagnostics only; never an entry authorization.

The live entry capture still performs fresh account requests. Persisted source
timestamps are not refreshed when another diagnostic consumer reuses a snapshot.
"""
import json,os,tempfile,time
from pathlib import Path
from datetime import datetime,timezone

NAME='weex_account_observation_latest.json'
HOST='https://api-contract.weex.com'

def valid(data,max_age,now=None):
    try:
        age=(time.time() if now is None else now)-data['startedAtMs']/1000
        if data.get('host')!=HOST or data.get('complete') is not True or not 0<=age<=max_age:return False
        if not 0<=data['completedAtMs']-data['startedAtMs']<=5000:return False
        if abs(datetime.fromisoformat(data['observedAt']).timestamp()-data['startedAtMs']/1000)>.001:return False
        for field in ('positions','regularOrders','conditionalOrders','trailingOrders'):
            rows=data[field]
            if not isinstance(rows,list) or any(not isinstance(r,dict) or not isinstance(r.get('symbol'),str) or not r['symbol'] for r in rows):return False
        for field,key in (('positions','id'),('regularOrders','orderId'),('conditionalOrders','algoId'),('trailingOrders','orderId')):
            ids=[str(r[key]) for r in data[field]]
            if len(ids)!=len(set(ids)) or any(x in ('','None') for x in ids):return False
        return True
    except (ValueError,TypeError,KeyError,ArithmeticError):return False

def load(root,max_age=300,now=None):
    try:data=json.loads((Path(root)/NAME).read_text(encoding='utf-8'))
    except (OSError,ValueError):return None
    return data if valid(data,max_age,now) else None

def publish(root,started,positions,regular,conditional,trailing,*,completed=None):
    completed=int(time.time()*1000) if completed is None else completed
    data={'host':HOST,'startedAtMs':started,'completedAtMs':completed,'complete':True,
          'observedAt':datetime.fromtimestamp(started/1000,timezone.utc).isoformat(),
          'positions':positions,'regularOrders':regular,'conditionalOrders':conditional,'trailingOrders':trailing}
    if not valid(data,5,completed/1000):return False
    root=Path(root)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=root,prefix='account-observation-',suffix='.tmp',delete=False) as f:
        json.dump(data,f);path=Path(f.name)
    os.replace(path,root/NAME)
    return True

def observe(root,max_age=5):
    data=load(root,max_age)
    if data is None:
        from weex_live_worker import Reader
        Reader(root).account()  # fresh, GET-only; successful bounded reads publish
        data=load(root,max_age)
    if data is None:raise ValueError('COMPLETE_ACCOUNT_OBSERVATION_UNAVAILABLE')
    return data
