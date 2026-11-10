"""Authenticated GET-only emergency close eligibility, not an order sender."""
import json,os
from datetime import datetime,timezone
from pathlib import Path
from weex_pilot_unified_lifecycle_readonly import journals
from weex_pilot_baseline_load import load as load_baseline
from weex_pilot_emergency_attested_plan import assess
from weex_live_worker import Reader
from weex_order_pagination import history
from monitor import query
import live_control

ROOT=Path(__file__).resolve().parent

def run(root=ROOT):
    root=Path(root)
    if live_control.state(root)['mode']!='STOPPED' or live_control.build_errors(root):
        raise PermissionError('MAIN_NOT_STOPPED_OR_INTEGRITY')
    db=root/'weex_isolated_pilot.sqlite3'
    pilots=journals(db)
    result={'checkedAt':datetime.now(timezone.utc).isoformat(),
            'mode':'WEEX_AUTHENTICATED_GET_ONLY','pilots':len(pilots),
            'plans':[],'canSend':False,'exchangeWrites':0}
    if pilots:
        baseline=load_baseline(root/'weex_pilot_flat_baseline_latest.json')
        positions,regular,conditional=Reader(root).account()
        if any(not isinstance(x,list) for x in (positions,regular,conditional)):
            raise ValueError('ACCOUNT_READ_INCOMPLETE')
        hist=history(max_pages=5)
        if not hist.get('completeWithinRequestedBounds'):
            raise ValueError('ORDER_HISTORY_INCOMPLETE')
        for pilot in pilots:
            found=[o for o in hist['orders'] if o.get('clientOrderId')==pilot['entryId']]
            order=None;fills=[]
            if len(found)==1 and found[0].get('orderId'):
                oid=str(found[0]['orderId'])
                order=query('/capi/v3/order?orderId='+oid)
                if (not isinstance(order,dict) or str(order.get('orderId'))!=oid
                    or order.get('clientOrderId')!=pilot['entryId']):
                    raise ValueError('ENTRY_EXACT_ORDER_READBACK_MISMATCH')
                fills=query('/capi/v3/userTrades?symbol=ETHUSDT&orderId='+oid+'&limit=100')
                if not isinstance(fills,list) or len(fills)>=100:
                    raise ValueError('FILLS_NOT_COMPLETE')
            if not isinstance(order,dict):
                summary={'prepared':False,'reason':'EXACT_PILOT_ENTRY_NOT_FOUND'}
            else:
                summary=assess(db,pilot['pilotId'],baseline=baseline,
                        positions=positions,regular_orders=regular,
                        conditional_orders=conditional,entry_order=order,entry_fills=fills)
            result['plans'].append({'pilotId':pilot['pilotId'],
                                   'prepared':summary.get('prepared') is True,
                                   'positionId':summary.get('positionId'),
                                   'reason':summary.get('reason'),
                                   'canSend':False})
    outfile=root/'weex_pilot_emergency_attested_latest.json'
    tmp=outfile.with_suffix('.tmp')
    tmp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    os.replace(tmp,outfile)
    return result
if __name__=='__main__':
    print(json.dumps(run(),ensure_ascii=False))
