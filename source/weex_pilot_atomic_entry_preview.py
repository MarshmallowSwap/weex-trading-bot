"""WEEX V3 protected entry preview, isolated from protected bot modules.

Does not create or send any exchange order. The official SDK serializes the
entry with native slTriggerPrice and SlWorkingType using no-network interception.
"""
from decimal import Decimal,InvalidOperation
from weex_isolated_pilot_offline_journal import proposals
from weex_http_guard import prepare_sdk_request

def build(side,quantity,reference_price,stop_price):
    if side not in ('LONG','SHORT'):raise ValueError('INVALID_SIDE')
    ref=Decimal(str(reference_price));sl=Decimal(str(stop_price))
    if not all(v.is_finite() and v>0 for v in (ref,sl)):raise ValueError('INVALID_PRICE')
    if not ((side=='LONG' and sl<ref) or (side=='SHORT' and sl>ref)):
        raise ValueError('STOP_WRONG_SIDE_OF_ENTRY')
    base=proposals(side,quantity,stop_price)['entry']
    payload={**base,'slTriggerPrice':str(sl),'SlWorkingType':'MARK_PRICE'}
    proof=prepare_sdk_request('post_capi_v3_order',payload)
    if proof['networkRequests']!=0 or not proof['sdkSerializationVerified']:
        raise PermissionError('STOP_ENTRY_SDK_UNVERIFIED')
    return {'payload':payload,'preview':proof,'exchangeAccepted':False,
            'ordersSent':0,'readyForLive':False}
