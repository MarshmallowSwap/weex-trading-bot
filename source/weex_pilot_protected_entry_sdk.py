"""Pilot-only native WEEX V3 protected entry transport.

The order includes exchange-side slTriggerPrice and SlWorkingType. The SDK
signature is preserved; only one exact POST can leave this adapter. No order is
sent when imported; production remains STOPPED. Tests inject fake HTTP.
"""
import json
from pathlib import Path
from decimal import Decimal,InvalidOperation
from weex_http_guard import prepare_sdk_request,sdk_types
import live_control

HOST='https://api-contract.weex.com'
OP='post_capi_v3_order'
FIELDS={'symbol','side','positionSide','type','quantity','newClientOrderId','slTriggerPrice','SlWorkingType'}

def validate_protected(payload,ask):
    if not isinstance(payload,dict) or set(payload)!=FIELDS:raise ValueError('ATOMIC_STOP_FIELDS_REQUIRED')
    if (payload['symbol']!='ETHUSDT' or payload['type']!='MARKET'
        or payload['positionSide'] not in ('LONG','SHORT')
        or payload['side']!=('BUY' if payload['positionSide']=='LONG' else 'SELL')
        or not isinstance(payload['newClientOrderId'],str)
        or not payload['newClientOrderId'].startswith('wxpilot_')
        or payload['SlWorkingType']!='MARK_PRICE'):
        raise ValueError('ATOMIC_ENTRY_SCOPE_INVALID')
    try:
        ask=Decimal(str(ask));qty=Decimal(str(payload['quantity']))
        stop=Decimal(str(payload['slTriggerPrice']))
        if (not all(x.is_finite() and x>0 for x in (ask,qty,stop))
            or qty>Decimal('0.01') or ask*qty>Decimal('5')
            or (payload['positionSide']=='LONG' and stop>=ask)
            or (payload['positionSide']=='SHORT' and stop<=ask)):
            raise ValueError('ATOMIC_ENTRY_PRICE_OR_SIZE_INVALID')
    except (InvalidOperation,TypeError,ArithmeticError):
        raise ValueError('ATOMIC_ENTRY_PRICE_OR_SIZE_INVALID') from None
    return payload

class ProtectedEntryTransport:
    pilot_live_entry_only=True
    def __init__(self,root,authorization=None,session_factory=None):
        self.root=Path(root);self.authorization=authorization
        self.session_factory=session_factory

    def preflight_entry(self,operation,payload,*,ask,account):
        if operation!=OP:raise PermissionError('OPERATION_DENIED')
        validate_protected(payload,ask)
        cfg=json.loads((self.root/'weex_live_1x_pilot_config.json').read_text())
        if (cfg.get('exchange')!='WEEX' or cfg.get('marginMode')!='ISOLATED'
            or cfg.get('leverage')!=1 or cfg.get('maxNewOrders')!=1
            or Decimal(str(cfg.get('maxAdditionalNotionalUSDT','0')))>5
            or cfg.get('executionEnabled') is not True
            or cfg.get('liveOrderSubmissionAllowed') is not True
            or cfg.get('stopLossVerified') is not True
            or cfg.get('reduceOnlyCloseVerified') is not True
            or cfg.get('requireExplicitTestOrderApproval') is not True):
            raise PermissionError('PILOT_STOP_EXIT_OR_APPROVAL_UNVERIFIED')
        if live_control.state(self.root)['mode']!='STOPPED' or live_control.build_errors(self.root):
            raise PermissionError('MAIN_NOT_STOPPED_OR_INTEGRITY_ERROR')
        if (not isinstance(account,dict) or account.get('fresh') is not True
            or account.get('isolatedLeverage')!=1 or account.get('marginMode')!='ISOLATED'
            or any(not isinstance(account.get(x),list) or account[x]
                   for x in ('positions','regularOrders','conditionalOrders'))):
            raise PermissionError('ACCOUNT_NOT_VERIFIED_FLAT')
        if not callable(self.authorization) or self.authorization(OP,payload) is not True:
            raise PermissionError('EXACT_PROTECTED_ENTRY_APPROVAL_REQUIRED')
        preview=prepare_sdk_request(OP,payload)
        if preview.get('networkRequests')!=0 or preview.get('state')!='STOPPED_BEFORE_NETWORK':
            raise PermissionError('SDK_SERIALIZATION_FAILED')
        return True

    def send_entry_only(self,operation,payload,*,ask,account):
        self.preflight_entry(operation,payload,ask=ask,account=account)
        cfg,contract,ops=sdk_types()
        if ops[OP]['method']!='POST' or ops[OP]['path']!='/capi/v3/order':
            raise PermissionError('ENTRY_ENDPOINT_CHANGED')
        adapter=self
        class OneShot:
            used=False
            def request(self,method,url,**kwargs):
                if (self.used or method!='POST' or url!=HOST+'/capi/v3/order'
                    or kwargs.get('json') is not None or kwargs.get('params')):
                    raise PermissionError('UNEXPECTED_HTTP_DISPATCH')
                if json.loads(kwargs.get('data') or b'{}')!=payload:
                    raise PermissionError('PROTECTED_PAYLOAD_CHANGED')
                adapter.preflight_entry(OP,payload,ask=ask,account=account)
                self.used=True
                if adapter.session_factory is None:
                    import requests
                    session=requests.Session();owned=True
                else:session=adapter.session_factory();owned=False
                try:
                    kwargs['allow_redirects']=False
                    response=session.request(method,url,**kwargs)
                    if response.status_code!=200:raise RuntimeError('WEEX_ENTRY_OUTCOME_UNKNOWN')
                    return response
                finally:
                    if owned:session.close()
            def close(self):pass
        creds=json.loads((self.root/'weex_credentials.json').read_text())
        client=contract(config_rest_api=cfg(base_path=HOST,api_key=creds['api_key'],
            api_secret=creds['secret_key'],passphrase=creds['passphrase'],
            session=OneShot(),max_retries=0,timeout=10))
        result=client.rest_api.execute_operation(OP,payload)
        if result.status_code!=200 or not isinstance(result.data,dict):
            raise RuntimeError('PROTECTED_ENTRY_RESPONSE_UNVERIFIED')
        return result.data
