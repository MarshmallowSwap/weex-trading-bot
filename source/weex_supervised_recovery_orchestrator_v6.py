"""Independent GET-only recovery preview plus strictly approved one-shot exit.

The default CLI is read-only. The explicit dispatch_approved_close function
can send ONE real reduceOnly close, but only with an external exact-operation
approval after independently matched exchange observations. No entry, no
cancel/TP writes, no release gate changes, and no retries on uncertain outcome.
"""
from __future__ import annotations
import hashlib,json,os,time
from pathlib import Path
from weex_supervised_crash_executor_v2 import CLIENT_ID
from weex_supervised_crash_watchdog_v4 import has_unknown_entry
from weex_supervised_real_recovery_v3 import read_exchange
from weex_independent_incident_supervisor_v6 import independent_account_snapshot
from weex_supervised_reduce_only_close_plan_v4 import compose

ROOT=Path(__file__).resolve().parent

def prepare(root=ROOT,*,reader=None,proof_reader=None,account_reader=None,
            control_check=None,unknown_check=None,clock=None):
    root=Path(root)
    base={'entryDispatchAllowed':False,'closeDispatchAllowed':False,
          'entryRetryAllowed':False,'closeRetryAllowed':False,
          'productionGo':False,'networkWrites':0}
    try:
        import live_control
        mode,integrity=(control_check or (lambda:(
            live_control.state(root)['mode'],not live_control.build_errors(root))))()
        if mode!='STOPPED' or integrity is not True:
            return {**base,'status':'BLOCKED_CONTROL_OR_INTEGRITY'}
        unknown=(unknown_check or (lambda:has_unknown_entry(root,CLIENT_ID)))()
        if not unknown:
            return {**base,'status':'NO_SUPERVISED_UNKNOWN_ENTRY'}
        if reader is None:
            from weex_live_worker import Reader
            reader=Reader(root)
        proof=(proof_reader or (lambda:read_exchange(CLIENT_ID,root=root,reader=reader)))()
        if not isinstance(proof,dict) or proof.get('status')!='VERIFIED_PROTECTED_NEED_EXACT_CLOSE':
            return {**base,'status':'BLOCKED_UNVERIFIED_PROTECTION'}
        snapshot=(account_reader or (lambda:independent_account_snapshot(root,reader=reader)))()
        if not isinstance(snapshot,dict) or snapshot.get('fresh') is not True or any(
           snapshot.get(k) is not True for k in ('oneExactPosition','oneExactStop','noOtherOrders')):
            return {**base,'status':'BLOCKED_INDEPENDENT_SNAPSHOT'}
        if str(snapshot.get('positionId'))!=str(proof.get('positionId')) or str(snapshot.get('stopAlgoId'))!=str(proof.get('stopAlgoId')):
            return {**base,'status':'BLOCKED_ID_MISMATCH'}
        # Re-read all exchange state before preparing the exact no-write preview.
        positions,orders,algos=reader.account()
        config=reader.read('get_capi_v3_account_symbolConfig',symbol='ETHUSDT')
        preview=compose(proof=proof,positions=positions,regular_orders=orders,
                        conditional_orders=algos,settings=config)
        if preview.get('status')!='CLOSE_PREVIEW_ONLY' or preview.get('networkRequests')!=0:
            return {**base,'status':'BLOCKED_PREVIEW'}
        payload=preview['payload']
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return {**base,'status':'EXACT_CLOSE_PROPOSAL_REQUIRES_SEPARATE_AUTHORIZATION',
                'clientOrderId':CLIENT_ID,'positionId':str(proof['positionId']),
                'stopAlgoId':str(proof['stopAlgoId']),'payloadSha256':digest,
                'payload':payload,'proposalOnly':True}
    except Exception as exc:
        return {**base,'status':'BLOCKED_READBACK_ERROR','errorType':type(exc).__name__}

def dispatch_approved_close(root=ROOT,*,operator_approval=None,reader=None,
                            close_sender=None,proof_reader=None,account_reader=None,
                            control_check=None,unknown_check=None,close_verifier=None):
    """Integrate proposal and existing one-shot real-capable close transport.
    No default CLI access. An external callback must confirm the exact payload
    and independent incident IDs; no callback means zero exchange POSTs.
    """
    if not callable(operator_approval):
        return {'status':'BLOCKED_EXACT_OPERATOR_APPROVAL_MISSING',
                'closeDispatchAllowed':False,'networkWrites':0}
    proposal=prepare(root,reader=reader,proof_reader=proof_reader,
                     account_reader=account_reader,control_check=control_check,
                     unknown_check=unknown_check)
    if proposal.get('status')!='EXACT_CLOSE_PROPOSAL_REQUIRES_SEPARATE_AUTHORIZATION':
        return proposal
    from weex_supervised_reduceonly_close_transport_v4 import send_once
    sender=close_sender or send_once
    def exact_approval(operation,payload,proof):
        canonical=json.dumps(payload,sort_keys=True,separators=(',',':'))
        digest=hashlib.sha256(canonical.encode()).hexdigest()
        if (operation!='post_capi_v3_order' or digest!=proposal['payloadSha256']
            or str(proof.get('positionId'))!=proposal['positionId']
            or str(proof.get('stopAlgoId'))!=proposal['stopAlgoId']
            or proof.get('clientOrderId')!=CLIENT_ID):
            return False
        return operator_approval(operation,payload,proof) is True
    # The existing transport performs its own fresh exchange validation and
    # atomically reserves a durable UNKNOWN before its sole possible POST.
    result=sender(CLIENT_ID,root=Path(root),reader=reader,approval=exact_approval)
    if not isinstance(result,dict) or result.get('status')!='CLOSE_ACK_READBACK_REQUIRED':
        return result
    oid=str(result.get('closeOrderId') or '')
    if not oid.isdigit():
        return {'status':'CLOSE_ACK_ID_UNVERIFIED','safeToRetryClose':False,
                'verifiedFlat':False,'releaseCertified':False}
    if close_verifier is None:
        from weex_supervised_exact_close_readback_v6 import readback
        close_verifier=readback
    # Fresh authenticated verification after the exact one-shot POST.
    # An ACK alone must never be treated as final, and uncertainty never retries.
    try:
        proof=close_verifier(root=Path(root),client_id=CLIENT_ID,
                             close_order_id=oid,reader=reader)
    except Exception as exc:
        proof={'status':'CLOSE_READBACK_UNCERTAIN','errorType':type(exc).__name__,
               'verifiedFlat':False,'safeToRetryClose':False,'releaseCertified':False}
    if not isinstance(proof,dict):
        proof={'status':'CLOSE_READBACK_INVALID','verifiedFlat':False,
               'safeToRetryClose':False,'releaseCertified':False}
    return {'status':'CLOSE_VERIFIED_BY_INDEPENDENT_GET' if
             proof.get('status')=='EXACT_CLOSE_AND_FLAT_VERIFIED' and
             proof.get('verifiedFlat') is True else 'CLOSE_UNCERTAIN_NEEDS_READBACK',
            'closeOrderId':oid,'verifiedFlat':proof.get('verifiedFlat') is True,
            'safeToRetryClose':False,'releaseCertified':False,
            'readback':proof}

def run(root=ROOT):
    result=prepare(root)
    result['observedAtEpoch']=int(time.time())
    path=Path(root)/'weex_supervised_recovery_proposal_v6_latest.json'
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    os.replace(tmp,path)
    return result

if __name__=='__main__':
    print(json.dumps(run(),ensure_ascii=False))
