"""Read-only binding between persisted TP repair intents and the WEEX SDK gateway.

No write API is exposed. The actual live dispatcher must additionally reconcile
fresh position and order history, record UNKNOWN before network, and verify readback.
"""
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from weex_lifecycle import dump
from weex_http_guard import prepare_sdk_request

def validate(root, trade_id, operation, payload):
    path=Path(root)/'weex_user_tp_repair_proposals.sqlite3'
    with closing(sqlite3.connect(f'file:{path.resolve().as_posix()}?mode=ro',uri=True)) as db:
        row=db.execute("""SELECT operation,payload,payload_sha256,state
            FROM dispatch_intents_v1 WHERE trade_id=?""",(trade_id,)).fetchone()
    if row is None:
        raise PermissionError('REPAIR_INTENT_NOT_FOUND')
    op, saved, digest, state=row
    if state!='PREPARED_NOT_SENT':
        raise PermissionError('REPAIR_INTENT_NOT_FRESH')
    if operation!=op or dump(payload)!=saved:
        raise PermissionError('REPAIR_REQUEST_NOT_IMMUTABLE')
    computed=hashlib.sha256((op+'|'+saved).encode()).hexdigest()
    if computed!=digest:
        raise PermissionError('REPAIR_INTENT_HASH_MISMATCH')
    result=prepare_sdk_request(op,json.loads(saved))
    if result.get('networkRequests')!=0 or result.get('ordersSubmitted') is not False:
        raise PermissionError('SDK_PREVIEW_NOT_OFFLINE')
    return {'state':'VALIDATED_NOT_SUBMITTED','payloadSha256':digest,
            'sdkSerializationVerified':True,'dispatchAllowed':False}
