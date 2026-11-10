"""Offline-only isolated 1x pilot planner and durable no-resend journal."""
import json,sqlite3,uuid
from contextlib import closing
from decimal import Decimal as D
from weex_http_guard import prepare_sdk_request
SCHEMA="""CREATE TABLE IF NOT EXISTS pilot_v1(
 pilot_id TEXT PRIMARY KEY, side TEXT NOT NULL, quantity TEXT NOT NULL,
 state TEXT NOT NULL, entry_id TEXT UNIQUE NOT NULL, stop_id TEXT UNIQUE NOT NULL,
 close_id TEXT UNIQUE NOT NULL, proposals TEXT NOT NULL)"""
def connect(path):
 c=sqlite3.connect(str(path),timeout=10)
 c.execute('PRAGMA synchronous=FULL')
 c.execute(SCHEMA)
 return c
def proposals(side,quantity,stop_price):
 if side not in ('LONG','SHORT'):raise ValueError('SIDE')
 qty=D(str(quantity));stop=D(str(stop_price))
 if not all(x.is_finite() and x>0 for x in (qty,stop)) or qty>D('0.01'):raise ValueError('SIZE')
 ids=['wxpilot_'+uuid.uuid4().hex[:24] for i in range(3)]
 entry={'symbol':'ETHUSDT','side':'BUY' if side=='LONG' else 'SELL',
        'positionSide':side,'type':'MARKET','quantity':str(qty),'newClientOrderId':ids[0]}
 close={'symbol':'ETHUSDT','side':'SELL' if side=='LONG' else 'BUY',
        'positionSide':side,'type':'MARKET','quantity':str(qty),'reduceOnly':True,
        'newClientOrderId':ids[2]}
 sl={'symbol':'ETHUSDT','clientAlgoId':ids[1],'planType':'STOP_LOSS',
     'triggerPrice':str(stop),'executePrice':'0','quantity':str(qty),
     'positionSide':side,'triggerPriceType':'MARK_PRICE','reduceOnly':True,'closePosition':False}
 for op,p in [('post_capi_v3_order',entry),('post_capi_v3_order',close),
              ('post_capi_v3_placeTpSlOrder',sl)]:
  proof=prepare_sdk_request(op,p)
  if proof['networkRequests']!=0 or proof['state']!='STOPPED_BEFORE_NETWORK':
   raise PermissionError('NOT_OFFLINE')
 return {'entry':entry,'stop':sl,'close':close}
def reserve(path,*,pilot_id,side,quantity,stop_price):
 if not pilot_id or len(pilot_id)>90:raise ValueError('PILOT_ID')
 with closing(connect(path)) as c:
  c.execute('BEGIN IMMEDIATE')
  row=c.execute('SELECT state FROM pilot_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
  if row:
   c.rollback()
   return {'state':row[0],'reservedPreviously':True,'maySend':False}
  p=proposals(side,quantity,stop_price)
  c.execute('INSERT INTO pilot_v1 VALUES(?,?,?,?,?,?,?,?)',(
   pilot_id,side,str(D(str(quantity))),'PREPARED_NO_SEND',
   p['entry']['newClientOrderId'],p['stop']['clientAlgoId'],
   p['close']['newClientOrderId'],json.dumps(p)))
  c.commit()
  return {'state':'PREPARED_NO_SEND','reservedPreviously':False,'maySend':False,
          'ordersSubmitted':0}
def review(path,pilot_id,*,position=None,entry_fills=None,stop_order=None):
 with closing(connect(path)) as c:
  row=c.execute('SELECT side,quantity,state,entry_id,stop_id FROM pilot_v1 WHERE pilot_id=?',(pilot_id,)).fetchone()
  if not row:raise ValueError('UNKNOWN_PILOT')
  side,qty,state,entry_id,stop_id=row
  if position is None or entry_fills is None or stop_order is None:
   return {'state':'RECONCILIATION_REQUIRED','maySend':False}
  try:
   ok=(position.get('symbol')=='ETHUSDT' and position.get('side')==side and
       D(str(position['size']))==D(qty) and isinstance(entry_fills,list) and bool(entry_fills) and
       all(f.get('clientOrderId')==entry_id for f in entry_fills) and
       sum((D(str(f['qty'])) for f in entry_fills),D(0))==D(qty) and
       stop_order.get('clientAlgoId')==stop_id and stop_order.get('reduceOnly') is True and
       stop_order.get('positionSide')==side and stop_order.get('symbol')=='ETHUSDT' and
       D(str(stop_order['quantity']))==D(qty) and
       stop_order.get('algoStatus') in ('NEW','UNTRIGGERED'))
  except (KeyError,TypeError,ValueError):ok=False
  return {'state':'OBSERVATION_MATCHED_NO_SEND' if ok else 'REVIEW_REQUIRED',
          'maySend':False,'ordersSubmitted':0}
