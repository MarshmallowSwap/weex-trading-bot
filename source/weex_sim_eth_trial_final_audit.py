"""Independent GET-only proof for SIM close order and flat account."""
import json
from pathlib import Path
from decimal import Decimal as D
from weex_http_guard import sdk_types
from weex_sim_eth_trial_readback import DemoRead,HOST
import live_control
ROOT=Path(__file__).resolve().parent
def run():
 exit=json.loads((ROOT/'weex_sim_eth_trial_exit.json').read_text())
 trial=json.loads((ROOT/'weex_sim_eth_trial_one_shot.json').read_text())
 oid=exit.get('closeOrderId','')
 if exit.get('flatVerified') is not True or not oid:raise PermissionError('NO_CLOSE_READBACK_TARGET')
 cfg,contract,ops=sdk_types()
 opnames=('get_capi_v3_order','get_capi_v3_userTrades',
  'get_capi_v3_account_position_allPosition','get_capi_v3_openOrders',
  'get_capi_v3_openAlgoOrders','get_capi_v3_allAlgoOrders')
 creds=json.loads((ROOT/'weex_credentials.json').read_text())
 s=DemoRead({ops[n]['path'] for n in opnames},oid)
 out={'host':HOST,'closeOrderId':oid,'closeFillVerified':False,'accountFlatVerified':False,
  'productionMode':live_control.state(ROOT)['mode'],'productionIntegrity':live_control.build_errors(ROOT),
  'exchangeWrites':0}
 try:
  c=contract(config_rest_api=cfg(base_path=HOST,api_key=creds['api_key'],
    api_secret=creds['secret_key'],passphrase=creds['passphrase'],session=s,timeout=8,max_retries=0))
  def read(n,q=None):return c.rest_api.execute_operation(n,{'query':q or {}}).data
  order=read('get_capi_v3_order',{'orderId':oid})
  fills=read('get_capi_v3_userTrades',{'symbol':'ETHUSDT','orderId':oid,'limit':100})
  positions=read('get_capi_v3_account_position_allPosition')
  regular=read('get_capi_v3_openOrders')
  algos=read('get_capi_v3_openAlgoOrders')
  archive=read('get_capi_v3_allAlgoOrders',{'symbol':'ETHUSDT'})
  ids=[str(f.get('id')) for f in fills] if isinstance(fills,list) else []
  filled_qty=sum((D(str(f['qty'])) for f in fills),D(0)) if isinstance(fills,list) else D(0)
  out['closeFillVerified']=(isinstance(order,dict) and order.get('status')=='FILLED'
    and order.get('symbol')=='ETHUSDT' and order.get('side')=='SELL'
    and order.get('positionSide')=='LONG' and order.get('reduceOnly') is True
    and D(str(order.get('executedQty','0')))==D(str(trial['quantity']))==filled_qty
    and bool(fills) and len(ids)==len(set(ids))
    and all(str(f.get('orderId'))==oid and f.get('symbol')=='ETHUSDT' and
      f.get('side')=='SELL' for f in fills))
  out['fillCount']=len(fills) if isinstance(fills,list) else -1
  out['closeExecutedQty']=str(order.get('executedQty')) if isinstance(order,dict) else None
  out['reduceOnly']=order.get('reduceOnly') if isinstance(order,dict) else None
  out['accountFlatVerified']=positions==[] and regular==[] and algos==[]
  out['openPositions']=len(positions) if isinstance(positions,list) else None
  out['openOrders']=len(regular) if isinstance(regular,list) else None
  out['openAlgos']=len(algos) if isinstance(algos,list) else None
  out['stopHistoricalTerminalProof']=any(str(x.get('algoId'))==str(exit['stopAlgoId'])
     and x.get('algoStatus') in ('CANCELED','CANCELLED')
     for x in archive.get('orders',[]) if isinstance(x,dict)) if isinstance(archive,dict) else False
 except Exception as e:out['errorClass']=type(e).__name__
 finally:
  s.close()
  (ROOT/'weex_sim_eth_trial_final_audit.json').write_text(json.dumps(out,indent=2))
  print(json.dumps(out))
if __name__=='__main__':run()
