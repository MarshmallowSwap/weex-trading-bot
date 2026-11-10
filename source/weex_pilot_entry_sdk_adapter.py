"""Pilota ETHUSDT Isolated 1x: one-shot entry adapter through the official WEEX SDK.

No submission at import time. Independently checks pilot authorization, current
flat account, signed SDK POST identity, bounded entry notional, exact journal id,
and main STOPPED. All real calls are disabled in existing config.
"""
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from weex_http_guard import prepare_sdk_request,sdk_types
import live_control

HOST='https://api-contract.weex.com'

def validate_entry(payload,ask):
    if not isinstance(payload,dict) or set(payload)!={'symbol','side','positionSide','type','quantity','newClientOrderId'}:
        raise ValueError('INVALID_ENTRY_FIELDS')
    if (payload['symbol']!='ETHUSDT' or payload['type']!='MARKET'
        or payload['positionSide'] not in ('LONG','SHORT')
        or payload['side']!=('BUY' if payload['positionSide']=='LONG' else 'SELL')
        or not isinstance(payload['newClientOrderId'],str)
        or not payload['newClientOrderId'].startswith('wxpilot_')):
        raise ValueError('ENTRY_SCOPE_INVALID')
    try:
        q=Decimal(str(payload['quantity']));price=Decimal(str(ask))
        if not q.is_finite() or not price.is_finite() or q<=0 or price<=0 or q>Decimal('.01'):
            raise ValueError('ENTRY_SIZE_INVALID')
        if q*price>Decimal('5'):
            raise ValueError('ENTRY_NOTIONAL_ABOVE_5_USDT')
    except (InvalidOperation,TypeError,ArithmeticError):
        raise ValueError('ENTRY_NOTIONAL_INVALID') from None
    return payload

class PilotEntrySDKAdapter:
    pilot_live_entry_only=True
    def __init__(self,root,authorization=None,session_factory=None):
        self.root=Path(root);self.authorization=authorization;self.session_factory=session_factory

    def preflight_entry(self,operation,payload,*,ask,account):
        if operation!='post_capi_v3_order':
            raise PermissionError('ENTRY_OPERATION_ONLY')
        validate_entry(payload,ask)
        cfg=json.loads((self.root/'weex_live_1x_pilot_config.json').read_text())
        if (cfg.get('executionEnabled') is not True
            or cfg.get('liveOrderSubmissionAllowed') is not True
            or cfg.get('reduceOnlyCloseVerified') is not True):
            raise PermissionError('PILOT_ENTRY_NOT_APPROVED')
        if self.authorization is None or self.authorization(operation,payload) is not True:
            raise PermissionError('EXACT_ENTRY_AUTHORIZATION_REQUIRED')
        if live_control.state(self.root)['mode']!='STOPPED' or live_control.build_errors(self.root):
            raise PermissionError('MAIN_NOT_STOPPED_OR_INTEGRITY_ERROR')
        if (not isinstance(account,dict) or account.get('fresh') is not True
            or account.get('isolatedLeverage')!=1 or account.get('marginMode')!='ISOLATED'
            or any(not isinstance(account.get(k),list) or account[k]
                for k in ('positions','regularOrders','conditionalOrders'))):
            raise PermissionError('ACCOUNT_NOT_FLAT_VERIFIED_1X')
        return True

    def send_entry_only(self,operation,payload,*,ask,account):
        if operation!='post_capi_v3_order':
            raise PermissionError('ENTRY_OPERATION_ONLY')
        validate_entry(payload,ask)
        if not isinstance(account,dict) or not (
            account.get('fresh') is True
            and account.get('isolatedLeverage')==1
            and account.get('marginMode')=='ISOLATED'
            and all(isinstance(account.get(k),list) and not account[k]
                for k in ('positions','regularOrders','conditionalOrders'))):
            raise PermissionError('ACCOUNT_NOT_FLAT_VERIFIED_1X')
        cfg=json.loads((self.root/'weex_live_1x_pilot_config.json').read_text())
        if (cfg.get('exchange')!='WEEX' or cfg.get('marginMode')!='ISOLATED'
            or cfg.get('leverage')!=1 or cfg.get('maxNewOrders')!=1
            or Decimal(str(cfg.get('maxAdditionalNotionalUSDT','0')))>Decimal('5')
            or cfg.get('executionEnabled') is not True
            or cfg.get('liveOrderSubmissionAllowed') is not True
            or cfg.get('requireExplicitTestOrderApproval') is not True
            or cfg.get('reduceOnlyCloseVerified') is not True):
            raise PermissionError('PILOT_ENTRY_NOT_APPROVED')
        if live_control.state(self.root)['mode']!='STOPPED' or live_control.build_errors(self.root):
            raise PermissionError('MAIN_NOT_STOPPED_OR_INTEGRITY_ERROR')
        if self.authorization is None or self.authorization(operation,payload) is not True:
            raise PermissionError('EXACT_ENTRY_AUTHORIZATION_REQUIRED')
        proof=prepare_sdk_request(operation,payload)
        if proof.get('state')!='STOPPED_BEFORE_NETWORK' or proof.get('networkRequests')!=0:
            raise PermissionError('SDK_ENTRY_PREVIEW_FAILED')
        config,contract,ops=sdk_types()
        spec=ops[operation]
        if spec['method']!='POST' or spec['path']!='/capi/v3/order':
            raise PermissionError('UNEXPECTED_SDK_ENDPOINT')
        adapter=self
        class OneShotTransport:
            used=False
            def request(self,method,url,**kwargs):
                if self.used or method!='POST' or url!=HOST+'/capi/v3/order' or kwargs.get('params') or kwargs.get('json') is not None:
                    raise PermissionError('ENTRY_NETWORK_DESTINATION_DENIED')
                if json.loads(kwargs.get('data') or b'{}')!=payload:
                    raise PermissionError('ENTRY_PAYLOAD_CHANGED')
                if adapter.authorization(operation,payload) is not True:
                    raise PermissionError('ENTRY_AUTHORIZATION_REVOKED')
                self.used=True
                if adapter.session_factory is None:
                    import requests
                    session=requests.Session();owned=True
                else:session=adapter.session_factory();owned=False
                try:
                    kwargs['allow_redirects']=False
                    response=session.request(method,url,**kwargs)
                    if response.status_code!=200:
                        raise RuntimeError('ENTRY_SUBMISSION_OUTCOME_UNKNOWN')
                    return response
                finally:
                    if owned:session.close()
            def close(self):pass
        credentials=json.loads((self.root/'weex_credentials.json').read_text())
        client=contract(config_rest_api=config(base_path=HOST,api_key=credentials['api_key'],
                        api_secret=credentials['secret_key'],passphrase=credentials['passphrase'],
                        session=OneShotTransport(),max_retries=0,timeout=10))
        response=client.rest_api.execute_operation(operation,payload)
        if response.status_code!=200 or not isinstance(response.data,dict):
            raise RuntimeError('ENTRY_ACK_UNCERTAIN')
        return response.data
