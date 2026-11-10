"""Read-only check of missing TP on journal-attributed bot positions."""
import json,sqlite3
from pathlib import Path
from contextlib import closing
from weex_live_worker import Reader
from weex_capacity import full_closing_tp
ROOT=Path(__file__).resolve().parent
def inspect(root=ROOT,reader=None):
    root=Path(root)
    positions,regular,algos=(reader or Reader(root)).account()
    with closing(sqlite3.connect(f"file:{(root/'weex_user_live_lifecycle.sqlite3').as_posix()}?mode=ro",uri=True)) as db:
        db.row_factory=sqlite3.Row
        trades=db.execute("SELECT id,symbol,state,owned,plan FROM trades_v1 WHERE state NOT IN ('CLOSED','REJECTED','SUPERSEDED')").fetchall()
        result=[]
        for t in trades:
            owned=json.loads(t['owned']) if t['owned'] else {}
            plan=json.loads(t['plan']) if t['plan'] else {}
            if owned.get('entrySource',plan.get('entrySource','automatic'))=='manual_telegram':
                continue
            pid=owned.get('positionId')
            if not pid:continue
            matches=[p for p in positions if str(p.get('id'))==str(pid) and p.get('symbol')==t['symbol']]
            if len(matches)!=1:
                result.append({'tradeId':t['id'],'symbol':t['symbol'],'status':'REVIEW_POSITION_MISMATCH'})
                continue
            p=matches[0]
            symalgos=[a for a in algos if a.get('symbol')==t['symbol']]
            symregular=[o for o in regular if o.get('symbol')==t['symbol']]
            full=[a for a in symalgos if full_closing_tp(a,[p])]
            if len(full)==1 and len(symalgos)==1 and not symregular:
                status='TP_PRESENT'
            elif not symalgos and not symregular and t['state'] in ('ENTRY_FILLED','REVIEW_REQUIRED','TP_PENDING','PROTECTED'):
                # A previous dispatch may have triggered, been cancelled, or had
                # an uncertain network outcome. Never interpret this as approval
                # to send another closing order without historical reconciliation.
                tp_writes=db.execute("SELECT state,response FROM writes_v1 WHERE trade_id=? AND kind='TP'",(t['id'],)).fetchall()
                entry=db.execute("SELECT response FROM writes_v1 WHERE trade_id=? AND kind='ENTRY'",(t['id'],)).fetchone()
                proof_ok=False
                try:
                    ack=json.loads(entry['response']) if entry and entry['response'] else {}
                    proof_ok=(ack.get('success') is True and str(ack.get('orderId'))==str(owned.get('entryOrderId')))
                except (ValueError,TypeError,AttributeError):pass
                if not proof_ok:
                    status='REVIEW_ENTRY_OWNERSHIP_UNVERIFIED'
                elif tp_writes:
                    status='REVIEW_PRIOR_TP_DISPATCH_RECONCILE_HISTORY'
                else:
                    status='TP_MISSING_RECONCILE_REQUIRED'
            else:
                status='REVIEW_AMBIGUOUS_ORDERS'
            result.append({'tradeId':t['id'],'symbol':t['symbol'],'state':t['state'],'status':status})
        return result
if __name__=='__main__':
    print(json.dumps(inspect(),indent=2))
