"""Read-only evidence for two unresolved, closed-appearing live lifecycles.

We do not infer a historical fill from absence of a current position.
Never send writes or change lifecycle state. Only bounded, exact exchange
order IDs and fills can support closing an unresolved record.
"""
import json,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def local_records(root=ROOT):
    db_path=Path(root)/'weex_user_live_lifecycle.sqlite3'
    conn=sqlite3.connect('file:'+db_path.resolve().as_posix()+'?mode=ro',uri=True)
    conn.row_factory=sqlite3.Row
    try:
        result=[]
        rows=conn.execute("SELECT id,symbol,state,plan,owned,detail FROM trades_v1 WHERE state='REVIEW_REQUIRED'").fetchall()
        for r in rows:
            plan=json.loads(r['plan'] or '{}')
            owned=json.loads(r['owned'] or '{}')
            detail=json.loads(r['detail'] or '{}')
            writes=[]
            for w in conn.execute("SELECT kind,operation,payload,state,response FROM writes_v1 WHERE trade_id=?",(r['id'],)):
                payload=json.loads(w['payload'] or '{}')
                response=json.loads(w['response'] or 'null')
                if isinstance(response,list):response=response[0] if len(response)==1 else {}
                if not isinstance(response,dict):response={}
                writes.append({'kind':w['kind'],'state':w['state'],
                               'ackSuccess':response.get('success') is True,
                               'ackId':str(response.get('orderId') or ''),
                               'ackClient':str(response.get('clientOrderId') or ''),
                               'intentClient':str(payload.get('newClientOrderId') or payload.get('clientOrderId') or '')})
            result.append({'tradeId':r['id'],'symbol':r['symbol'],'state':r['state'],
                           'positionId':str(owned.get('positionId') or ''),
                           'entryOrderId':str(owned.get('entryOrderId') or ''),
                           'entryClient':str((plan.get('entry') or {}).get('newClientOrderId') or ''),
                           'tpClient':str((owned.get('tpRequest') or {}).get('clientAlgoId') or ''),
                           'tpId':str(detail.get('tpId') or ''),
                           'writes':writes})
        return result
    finally:conn.close()
if __name__=='__main__':
 print(json.dumps(local_records()))
