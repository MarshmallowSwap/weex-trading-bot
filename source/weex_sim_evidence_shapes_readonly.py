"""GET-only WEEX simulation trade evidence shape inspection.
Print schema keys and counts only; no account identifiers or secrets.
"""
import json
from weex_sim_v3_auth_readonly import CREDENTIALS
from weex_sim_v3_one_shot_canary import request as restricted
from weex_sim_v3_pair_canary import guarded_request
# These dedicated demo history GET requests cannot use the write guards.
from weex_demo_inventory_readonly import probe
import base64,hashlib,hmac,time,urllib.request,urllib.error
HOST='https://api-sim.weex.com'
PATHS=('/capi/v3/userTrades?symbol=BTCUSDT&limit=20',
       '/capi/v3/order/history?symbol=BTCUSDT&limit=20',
       '/capi/v3/allAlgoOrders?symbol=BTCUSDT&limit=20')
c=json.loads(CREDENTIALS.read_text(encoding='utf-8-sig'))
for path in PATHS:
    ts=str(int(time.time()*1000))
    signature=base64.b64encode(hmac.new(c['secret_key'].encode(),
        (ts+'GET'+path).encode(),hashlib.sha256).digest()).decode()
    req=urllib.request.Request(HOST+path,method='GET',headers={
        'ACCESS-KEY':c['api_key'],'ACCESS-SIGN':signature,
        'ACCESS-PASSPHRASE':c['passphrase'],'ACCESS-TIMESTAMP':ts,
        'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=8) as response:
            status=response.status; data=json.load(response)
    except urllib.error.HTTPError as e:
        status=e.code
        try:data=json.loads(e.read(1024))
        except Exception:data=None
    except Exception as e:
        print(path.split('?')[0],type(e).__name__)
        continue
    rows=data if isinstance(data,list) else data.get('data') if isinstance(data,dict) else None
    print(path.split('?')[0],'HTTP',status,
          'rows',len(rows) if isinstance(rows,list) else 'N/A',
          'keys',sorted(rows[0].keys()) if isinstance(rows,list) and rows and isinstance(rows[0],dict) else [],
          'responseType',type(data).__name__)
