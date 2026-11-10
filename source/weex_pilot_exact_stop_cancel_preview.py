"""Scoped stop cancellation PREVIEW and authenticated readback assessment.

No network writes and no authority to cancel. A pilot-owned exact stop may
be proposed only by its immutable identity. Absence from the open list alone
never proves cancellation: a terminal order-status readback is required.
"""
from decimal import Decimal,InvalidOperation
from weex_http_guard import sdk_types,StoppedBeforeNetwork
from weex_pilot_exit_stop_lifecycle import ACTIVE

HOST='https://api-contract.weex.com'
OP='delete_capi_v3_algoOrder'
def valid_id(x):
    return isinstance(x,str) and x.isdecimal() and 0<int(x)<2**63 and len(x)<=20
def exact_plan(*,pilot_stop,observed,position,approved_id):
    deny=lambda why:{'prepared':False,'canSend':False,'reason':why,'exchangeWrites':0}
    if not isinstance(pilot_stop,dict) or not isinstance(observed,dict):
        return deny('STOP_JOURNAL_OR_READBACK_MISSING')
    a=str(pilot_stop.get('algoId',''));b=str(observed.get('algoId',''))
    if not valid_id(a) or a!=b or approved_id!=a:return deny('EXACT_STOP_ID_APPROVAL_MISSING')
    if (pilot_stop.get('symbol')!='ETHUSDT' or observed.get('symbol')!='ETHUSDT'
        or pilot_stop.get('positionSide')!=observed.get('positionSide')
        or pilot_stop.get('triggerPrice') is None or observed.get('triggerPrice') is None):
        return deny('STOP_IDENTITY_MISMATCH')
    try:
        price=Decimal(str(pilot_stop['triggerPrice']))
        actual=Decimal(str(observed['triggerPrice']))
        if not price.is_finite() or price<=0 or price!=actual:
            return deny('STOP_PRICE_MISMATCH')
    except (InvalidOperation,ValueError,TypeError):
        return deny('STOP_PRICE_INVALID')
    if (observed.get('orderType') not in ('STOP_MARKET','STOP_LOSS_MARKET')
        or observed.get('reduceOnly') is not True
        or observed.get('algoStatus') not in ACTIVE):
        return deny('NOT_ACTIVE_PROTECTIVE_STOP')
    if position is not None:
        if (not isinstance(position,dict) or position.get('symbol')!='ETHUSDT'
            or position.get('side')!=observed.get('positionSide')
            or position.get('marginType') not in ('ISOLATED','ISOLATE')):
            return deny('POSITION_NOT_PILOT_EXCLUSIVE')
    return {'prepared':True,'canSend':False,'exchangeWrites':0,'orderId':a,
            'method':'DELETE','path':'/capi/v3/algoOrder',
            'reason':'PREVIEW_ONLY_NEEDS_EXPLICIT_CANCEL_APPROVAL_AND_LIVE_GATE',
            'positionMayBecomeUnprotected':position is not None}

def preview_sdk(order_id):
    if not valid_id(order_id):raise ValueError('INVALID_EXACT_ALGO_ID')
    config,contract,ops=sdk_types()
    op=ops[OP]
    if (op['method']!='DELETE' or op['path']!='/capi/v3/algoOrder'
        or op.get('query_fields')!=['orderId']):
        raise PermissionError('SDK_CANCEL_OPERATION_CHANGED')
    class Capture:
        calls=0
        def request(self,method,url,**kwargs):
            self.calls+=1
            from urllib.parse import parse_qs,urlparse
            parsed=urlparse(url)
            if (method!='DELETE' or parsed.scheme!='https'
                or parsed.netloc!='api-contract.weex.com'
                or parsed.path!='/capi/v3/algoOrder' or parsed.fragment):
                raise PermissionError('CANCEL_PATH_UNSAFE')
            # The vendored SDK encodes orderId into the signed URL query.
            parsed_query=parse_qs(parsed.query,keep_blank_values=True)
            if parsed_query!={'orderId':[order_id]} or kwargs.get('params') is not None:
                raise PermissionError('EXTRA_OR_MISSING_QUERY_FIELDS')
            data=kwargs.get('data')
            if data not in (None,'',b''):raise PermissionError('CANCEL_BODY_UNEXPECTED')
            self.verified_query=parsed_query
            raise StoppedBeforeNetwork()
        def close(self):pass
    capture=Capture()
    client=contract(config_rest_api=config(base_path=HOST,api_key='FAKE',
        api_secret='FAKE',passphrase='FAKE',session=capture,max_retries=0))
    try:client.rest_api.execute_operation(OP,{'query':{'orderId':order_id}})
    except StoppedBeforeNetwork:pass
    if capture.calls!=1 or capture.verified_query is None:
        raise PermissionError('CANCEL_SDK_ID_NOT_CAPTURED')
    return {'sdkPreviewVerified':True,'networkRequests':0,'exchangeWrites':0}

def verify_cancel(*,order_id,history_order,open_orders,positions):
    deny=lambda why:{'verified':False,'canClose':False,'reason':why,'exchangeWrites':0}
    if not valid_id(order_id) or not isinstance(open_orders,list) or not isinstance(positions,list):
        return deny('INCOMPLETE_READBACK')
    if not isinstance(history_order,dict) or str(history_order.get('algoId'))!=order_id:
        return deny('TERMINAL_ORDER_READBACK_MISSING')
    if history_order.get('algoStatus') not in ('CANCELED','CANCELLED'):
        return deny('CANCEL_NOT_TERMINAL_VERIFIED')
    if any(not isinstance(x,dict) or str(x.get('algoId'))==order_id for x in open_orders):
        return deny('CANCELED_STOP_STILL_VISIBLE')
    if len(open_orders)!=0:return deny('OTHER_OPEN_CONDITIONAL_ORDERS')
    if len(positions)>1:return deny('EXTRANEOUS_POSITION')
    return {'verified':True,'canClose':False,'reason':'EXACT_CANCEL_READBACK_VERIFIED_RECHECK_POSITION_BEFORE_CLOSE',
            'exchangeWrites':0,'positionCount':len(positions)}
