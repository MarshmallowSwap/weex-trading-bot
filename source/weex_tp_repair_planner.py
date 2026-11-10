"""Read-only WEEX history reconciliation for candidate TP repair proposals."""
from pathlib import Path
from weex_bot_tp_audit import inspect
from weex_live_worker import Reader
from weex_lifecycle import Lifecycle
from weex_tp_repair_gate import evaluate
from weex_tp_repair_journal import record

class ReadOnlyGateway:
    def __init__(self,reader):
        self.reader=reader
    def read(self,operation,**args):
        return self.reader.read(operation,**args)
    def write(self,*args,**kwargs):
        raise PermissionError('TP_REPAIR_READ_ONLY')

def plan(root,reader=None,*,save_proposals=False):
    root=Path(root)
    reader=reader or Reader(root)
    scan=inspect(root,reader=reader)
    engine=Lifecycle(root/'weex_user_live_lifecycle.sqlite3',ReadOnlyGateway(reader),lambda:{'execution':{'enabled':False,'mode':'PRETRADE'}})
    output=[]
    for row in scan:
        tid=row['tradeId']
        result={'tradeId':tid,'symbol':row['symbol'],'auditStatus':row['status'],'dispatchAllowed':False}
        if row['status']!='REVIEW_PRIOR_TP_DISPATCH_RECONCILE_HISTORY':
            result['decision']='NO_RECOVERY_PROPOSAL'
            output.append(result)
            continue
        try:
            item=engine.get(tid)
            _,_,positions,history,opened=engine.observations(item)
            regular=reader.account()[1]
            decision=evaluate(item,engine.writes(tid),positions,regular,opened,history,complete_history=True)
            result['decision']=decision['reason']
            result['eligible']=decision['eligible']
            if decision['eligible']:
                from weex_tp_repair_request import build
                preview=build(decision,item)
                result['requestPreview']={'operation':preview['operation'],
                    'payloadSha256':preview['sdkPreview']['payloadSha256'],
                    'sdkSerializationVerified':preview['sdkPreview']['sdkSerializationVerified'],
                    'ordersSubmitted':False}
                if save_proposals:
                    result['journal']=record(root,decision)
                    if result['journal']['state'] in ('PROPOSED','ALREADY_PROPOSED'):
                        from weex_tp_repair_intent import prepare
                        result['intent']=prepare(root,decision,item)
                        from weex_live_worker import Gateway
                        result['gatewayPreview']=Gateway(root,reader).repair_preview(
                            item['id'],preview['operation'],preview['request'])
        except Exception as exc:
            # Never interpret a failed history read as permission to submit.
            result['decision']='REPAIR_PREFLIGHT_OR_JOURNAL_FAILED'
            result['errorType']=type(exc).__name__
            result['eligible']=False
        output.append(result)
    return output

if __name__=='__main__':
    import json
    print(json.dumps(plan(Path(__file__).resolve().parent),indent=2))
