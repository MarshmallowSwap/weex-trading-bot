"""Fail-closed exit replacement coordinator for WEEX conditional TP+SL.

Offline-only state machine for partial fill. Never cancels original SL first.
No exchange HTTP. Commands are instructions requiring a separate,
sim-only, idempotent executor with mandatory exchange readback at each step.
"""
from decimal import Decimal
from weex_tp_limit_shadow import decimal

def inspect(*,position,algos,regular_orders,old_tp_client,old_sl_client,
            new_tp_client=None,new_sl_client=None,expected_position_id=None):
    base={'allowedToSend':False,'allowedToCancel':False,'liveEnabled':False,
          'status':'REVIEW_REQUIRED','stopCoverageCertified':False}
    try:
        if not isinstance(position,dict) or not isinstance(algos,list) or not isinstance(regular_orders,list):
            raise ValueError('INVALID_ACCOUNT_SNAPSHOT')
        if expected_position_id is None or str(position.get('id'))!=str(expected_position_id):
            raise ValueError('POSITION_ID_CHANGED')
        side=position['side'];symbol=position['symbol']
        if side not in ('LONG','SHORT') or not symbol:raise ValueError('BAD_POSITION_IDENTITY')
        remaining=decimal(position['size'])
        if remaining<=0:raise ValueError('NO_OPEN_POSITION')
        if any(not isinstance(x,dict) for x in algos+regular_orders):
            raise ValueError('BAD_ORDER_SNAPSHOT')
        if any(o.get('symbol')==symbol for o in regular_orders):
            raise ValueError('ACTIVE_REGULAR_ORDER_REQUIRES_RECONCILIATION')
        if not old_tp_client or not old_sl_client or old_tp_client==old_sl_client:
            raise ValueError('INVALID_ORIGINAL_PAIR')
        known_ids={x for x in (old_tp_client,old_sl_client,new_tp_client,new_sl_client) if x}
        if any(a.get('symbol')==symbol and a.get('clientAlgoId') not in known_ids for a in algos):
            raise ValueError('UNKNOWN_ALGO_FOR_POSITION_SYMBOL')
        by={}
        for name,cid in (('old_tp',old_tp_client),('old_sl',old_sl_client),
                         ('new_tp',new_tp_client),('new_sl',new_sl_client)):
            if cid is None:by[name]=None;continue
            found=[a for a in algos if a.get('clientAlgoId')==cid]
            if len(found)>1:raise ValueError('DUPLICATE_'+name.upper())
            if not found:by[name]=None;continue
            a=found[0]
            if (a.get('symbol')!=symbol or a.get('positionSide')!=side
                    or a.get('side')!=('SELL' if side=='LONG' else 'BUY')
                    or a.get('reduceOnly') is not True
                    or a.get('algoStatus') not in ('NEW','UNTRIGGERED')
                    or not a.get('algoId')):
                raise ValueError('INVALID_'+name.upper()+'_EVIDENCE')
            q=decimal(a.get('quantity'))
            if q<=0:raise ValueError('INVALID_EXIT_QUANTITY')
            types=('TAKE_PROFIT','TAKE_PROFIT_LIMIT') if name.endswith('tp') else (
                'STOP_LOSS','STOP_LOSS_MARKET','STOP_MARKET')
            if a.get('orderType') not in types:
                raise ValueError('INVALID_'+name.upper()+'_TYPE')
            by[name]=a
        oldsl=by['old_sl'];newsl=by['new_sl']
        # Fail-closed: canceled original protection without a verified
        # replacement must be escalated, not silently repaired with retry.
        if not oldsl and not newsl:
            raise ValueError('STOP_LOSS_MISSING')
        if newsl and decimal(newsl['quantity'])!=remaining:
            raise ValueError('NEW_STOP_QUANTITY_NOT_RESIDUAL')
        if by['new_tp'] and decimal(by['new_tp']['quantity'])!=remaining:
            raise ValueError('NEW_TP_QUANTITY_NOT_RESIDUAL')
        evidence={'remainingQuantity':str(remaining),
                  'oldStopPresent':bool(oldsl),'newStopPresent':bool(newsl),
                  'oldTpPresent':bool(by['old_tp']),'newTpPresent':bool(by['new_tp']),
                  'originalSlOversized':bool(oldsl and decimal(oldsl['quantity'])>remaining),
                  'stopCoverageCertified':False}
        if oldsl and not newsl:
            # Next action must be attempting new SL while old SL remains.
            return {**base,'status':'NEEDS_NEW_STOP_FIRST_OFFLINE',
                    'nextAction':'PLACE_RESIDUAL_STOP_SIM_ONLY_THEN_READBACK',
                    'reason':'OLD_SL_MUST_REMAIN_ACTIVE',**evidence}
        if oldsl and newsl:
            # Only AFTER a proven new SL can the old stop be considered
            # for cancellation, but the real executor must bind exact algoId.
            return {**base,'status':'DUPLICATE_STOPS_REVIEW',
                    'nextAction':'CANCEL_EXACT_OLD_STOP_SIM_ONLY_THEN_READBACK',
                    'reason':'TWO_ACTIVE_STOPS_REQUIRE_EXCHANGE_VERIFICATION',**evidence}
        if newsl and by['old_tp']:
            return {**base,'status':'NEW_STOP_ONLY_OLD_TP_REVIEW',
                    'nextAction':'RECONCILE_OR_CANCEL_EXACT_OLD_TP_SIM_ONLY',
                    'reason':'TP_MAY_BE_OVERSIZED',**evidence}
        if newsl and by['new_tp'] and not by['old_tp']:
            return {**base,'status':'PAIR_RESTORED_OFFLINE_ONLY',
                    'nextAction':'CONTINUE_GET_ONLY_MONITORING',
                    'reason':'EXCHANGE_EXECUTION_BEHAVIOR_NOT_CERTIFIED',**evidence}
        return {**base,'status':'NEW_STOP_PRESENT_TP_MISSING',
                'nextAction':'PLACE_RESIDUAL_TP_SIM_ONLY_THEN_READBACK',**evidence}
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
        return {**base,'reason':str(exc)}
