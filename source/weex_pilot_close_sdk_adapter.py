"""WEEX SDK adapter for the *pilot close only*.

Live network is deliberately gated by all pilot flags, exact payload binding,
an external per-order authorization, and main strategy STOPPED. It cannot
open positions. Imported/constructed adapters do not submit orders.
"""
import hashlib,json
from pathlib import Path
from urllib.parse import urlsplit
from weex_pilot_one_shot_exit import validated_close_payload
from weex_http_guard import prepare_sdk_request,sdk_types
import live_control

HOST='https://api-contract.weex.com'
class PilotCloseSDKAdapter:
    pilot_live_close_only=True
    def __init__(self,root,authorization=None,session_factory=None):
        self.root=Path(root)
        self.authorization=authorization
        self.session_factory=session_factory

    def send_close_only(self,operation,payload):
        if operation!='post_capi_v3_order':
            raise PermissionError('CLOSE_OPERATION_ONLY')
        payload=validated_close_payload(payload)
        pilot=json.loads((self.root/'weex_live_1x_pilot_config.json').read_text())
        if (pilot.get('exchange')!='WEEX' or pilot.get('marginMode')!='ISOLATED'
            or pilot.get('leverage')!=1 or pilot.get('maxNewOrders')!=1
            or pilot.get('executionEnabled') is not True
            or pilot.get('liveOrderSubmissionAllowed') is not True
            or pilot.get('requireExplicitTestOrderApproval') is not True
            or pilot.get('reduceOnlyCloseVerified') is not True):
            raise PermissionError('PILOT_LIVE_CLOSE_NOT_APPROVED')
        if live_control.state(self.root)['mode']!='STOPPED':
            raise PermissionError('MAIN_BOT_MUST_BE_STOPPED')
        if live_control.build_errors(self.root):
            raise PermissionError('PRODUCTION_INTEGRITY_FAILED')
        if self.authorization is None or self.authorization(operation,payload) is not True:
            raise PermissionError('EXACT_CLOSE_AUTHORIZATION_REQUIRED')
        proof=prepare_sdk_request(operation,payload)
        if proof.get('state')!='STOPPED_BEFORE_NETWORK' or proof.get('networkRequests')!=0:
            raise PermissionError('SDK_SERIALIZATION_FAILED')
        config,contract,ops=sdk_types()
        spec=ops[operation]
        if spec['method']!='POST' or spec['path']!='/capi/v3/order':
            raise PermissionError('SDK_OPERATION_CHANGED')
        adapter=self
        class Transport:
            used=False
            def request(self,method,url,**kw):
                if self.used:raise PermissionError('ONE_SHOT_ONLY')
                if method!='POST' or url!=HOST+'/capi/v3/order' or kw.get('params') or kw.get('json') is not None:
                    raise PermissionError('WRONG_NETWORK_DESTINATION')
                try:
                    sent=json.loads(kw.get('data') or b'{}')
                except (ValueError,TypeError):
                    raise PermissionError('NON_JSON_SDK_PAYLOAD')
                if sent!=payload or adapter.authorization(operation,payload) is not True:
                    raise PermissionError('PAYLOAD_OR_AUTHORIZATION_CHANGED')
                # The SDK's signed headers are preserved. No redirects, no retries.
                if adapter.session_factory is None:
                    import requests
                    session=requests.Session()
                    owned=True
                else:
                    session=adapter.session_factory()
                    owned=False
                self.used=True
                try:
                    kw['allow_redirects']=False
                    response=session.request(method,url,**kw)
                    if response.status_code!=200 or 300<=response.status_code<400:
                        raise RuntimeError('WEEX_RESPONSE_UNCERTAIN_RECONCILE_REQUIRED')
                    return response
                finally:
                    if owned:session.close()
            def close(self):pass
        credentials=json.loads((self.root/'weex_credentials.json').read_text())
        client=contract(config_rest_api=config(base_path=HOST,api_key=credentials['api_key'],
               api_secret=credentials['secret_key'],passphrase=credentials['passphrase'],
               session=Transport(),max_retries=0,timeout=10))
        response=client.rest_api.execute_operation(operation,payload)
        if response.status_code!=200 or not isinstance(response.data,dict):
            raise RuntimeError('WEEX_RESPONSE_UNCERTAIN_RECONCILE_REQUIRED')
        return response.data
