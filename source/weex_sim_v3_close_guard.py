"""Strict WEEX V3 simulation emergency-close request, no network.

Must bind both position ID and symbol. Never submit a symbol-only or
account-wide close. Never auto-repeat ambiguous exchanges writes.
"""
import json
from weex_tp_limit_shadow import decimal

def plan_close(*,symbol,position_id,observed_positions,observed_orders,
               account_environment='WEEX_SIM_V3',verified_sim_host='api-sim.weex.com'):
    base={'status':'BLOCKED','networkRequests':0,'ordersSubmitted':False,
          'dispatchAllowed':False,'requestMethod':'POST',
          'path':'/capi/v3/closePositions','host':'api-sim.weex.com'}
    if account_environment!='WEEX_SIM_V3' or verified_sim_host!='api-sim.weex.com':
        return {**base,'reason':'NOT_ISOLATED_SIMULATION'}
    if not isinstance(observed_positions,list) or not isinstance(observed_orders,list):
        return {**base,'reason':'ACCOUNT_SNAPSHOT_MISSING'}
    if not isinstance(symbol,str) or not symbol or not isinstance(position_id,(int,str)):
        return {**base,'reason':'POSITION_BINDING_INVALID'}
    try:
        ident=str(int(position_id))
        if ident=='0' or str(position_id)!=ident:
            raise ValueError('POSITION_ID_MUST_BE_EXACT_POSITIVE_INTEGER')
        matches=[x for x in observed_positions if isinstance(x,dict) and
                 str(x.get('id'))==ident and x.get('symbol')==symbol]
        if len(matches)!=1:
            raise ValueError('POSITION_ID_AND_SYMBOL_NOT_UNIQUELY_OBSERVED')
        if decimal(matches[0].get('size'))<=0:
            raise ValueError('NOT_AN_OPEN_POSITION')
        if any(not isinstance(o,dict) for o in observed_orders):
            raise ValueError('INVALID_ORDER_SNAPSHOT')
        # Order conflicts must be reconciled before close, not silently ignored.
        pending=[o for o in observed_orders if o.get('symbol')==symbol]
        if pending:
            raise ValueError('SYMBOL_HAS_PENDING_ORDERS_RECONCILE_FIRST')
        body={'symbol':symbol,'positionId':int(ident)}
        # Exact canonical serialized JSON for later signing, no API call.
        payload=json.dumps(body,separators=(',',':'))
        if set(json.loads(payload))!={'symbol','positionId'}:
            raise ValueError('UNSCOPED_CLOSE')
        return {**base,'status':'PREPARED_OFFLINE_ONLY','requestBody':body,
                'canonicalBody':payload,'reason':'WRITE_REQUIRES_SEPARATE_SIM_ONLY_EXECUTOR',
                'proof':{'positionId':ident,'symbol':symbol,
                         'observedSize':str(matches[0]['size'])}}
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
        return {**base,'reason':str(exc)}

def verify_close_result(request,result,positions_after):
    """Never trust success without independent GET that exact position vanished."""
    if not isinstance(request,dict) or not isinstance(result,list) or not isinstance(positions_after,list):
        return {'state':'REVIEW_REQUIRED','retryAllowed':False,'reason':'INCOMPLETE_CLOSE_EVIDENCE'}
    try:
        ident=request['requestBody']['positionId']
        symbol=request['requestBody']['symbol']
        matches=[r for r in result if isinstance(r,dict) and r.get('positionId')==ident]
        if len(result)!=1 or len(matches)!=1 or matches[0].get('success') is not True:
            raise ValueError('CLOSE_ACK_NOT_EXACT_SUCCESS')
        if not matches[0].get('successOrderId'):
            raise ValueError('CLOSE_ORDER_ID_MISSING')
        if any(str(p.get('id'))==str(ident) or p.get('symbol')==symbol
               for p in positions_after if isinstance(p,dict)):
            raise ValueError('POSITION_STILL_PRESENT_OR_REOPENED')
        return {'state':'CLOSED_VERIFIED_BY_READBACK','retryAllowed':False,
                'closeOrderId':str(matches[0]['successOrderId'])}
    except (KeyError,TypeError,ValueError) as exc:
        return {'state':'REVIEW_REQUIRED','retryAllowed':False,'reason':str(exc)}
