"""Read-only independently attested emergency-close proposal.

Requires baseline, journaled entry, exchange order and fills, exact position.
No caller-supplied ownership flag is ever accepted. No network writes.
"""
import json
from contextlib import closing
from pathlib import Path
from weex_isolated_pilot_offline_journal import connect
from weex_pilot_ownership_attestation import attest
from weex_pilot_emergency_close_sdk import exact_payload

def assess(db,pilot_id,*,baseline,positions,regular_orders,conditional_orders,entry_order,entry_fills):
    deny=lambda why:{'prepared':False,'canSend':False,'reason':why,'exchangeWrites':0}
    if not all(isinstance(v,list) for v in (positions,regular_orders,conditional_orders,entry_fills)):
        return deny('INCOMPLETE_ACCOUNT_DATA')
    if len(positions)!=1 or regular_orders or conditional_orders:
        return deny('NONEXCLUSIVE_POSITION_OR_OPEN_ORDERS')
    with closing(connect(db)) as c:
        row=c.execute('SELECT side,quantity,state,entry_id,close_id FROM pilot_v1 WHERE pilot_id=?',
                      (pilot_id,)).fetchone()
        if row is None:return deny('UNKNOWN_PILOT')
        side,quantity,state,entry_id,close_id=row
        if state!='ENTRY_RECONCILED_EXTERNALLY':return deny('ENTRY_NOT_RECONCILED')
        names={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'pilot_emergency_dispatch_v1' in names and c.execute(
                'SELECT 1 FROM pilot_emergency_dispatch_v1 WHERE pilot_id=?',(pilot_id,)).fetchone():
            return deny('EMERGENCY_ALREADY_SENT_OR_UNKNOWN')
        if 'pilot_close_dispatch_v1' in names and c.execute(
                'SELECT 1 FROM pilot_close_dispatch_v1 WHERE pilot_id=?',(pilot_id,)).fetchone():
            return deny('OTHER_CLOSE_ALREADY_SENT_OR_UNKNOWN')
    pilot={'side':side,'quantity':quantity,'entryId':entry_id}
    proof=attest(baseline=baseline,position=positions[0],entry=entry_order,
                 fill_rows=entry_fills,pilot=pilot)
    if proof.get('owned') is not True:return deny('OWNERSHIP_UNVERIFIED:'+proof.get('reason','UNKNOWN'))
    try:payload=exact_payload(proof['positionId'])
    except (ValueError,KeyError,TypeError):return deny('INVALID_ATTESTED_POSITION_ID')
    return {'prepared':True,'canSend':False,'exchangeWrites':0,
            'reason':'AUTHENTICATED_READBACK_REQUIRED_BEFORE_DISPATCH',
            'positionId':str(proof['positionId']),'payload':payload,
            'attestation':proof}
