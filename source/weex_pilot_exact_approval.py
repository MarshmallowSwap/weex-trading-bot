"""One immutable exact-order approval object, reused for all SDK callbacks."""
from weex_pilot_entry_sdk_adapter import validate_entry
from weex_pilot_protected_entry_sdk import validate_protected
from decimal import Decimal

def exact_approval(pilot_id,payload,ask):
    if not isinstance(pilot_id,str) or not pilot_id or len(pilot_id)>90:
        raise ValueError('INVALID_PILOT_ID')
    if 'slTriggerPrice' in payload:
        validate_protected(payload,ask)
    else:
        validate_entry(payload,ask)
    return {'pilotId':pilot_id,'operation':'post_capi_v3_order',
            'payload':dict(payload),'ask':str(ask),'maximumNotionalUSDT':'5'}

def approved(authorization,approval,operation,payload):
    return (callable(authorization) and operation==approval['operation']
            and payload==approval['payload'] and authorization(approval) is True)
