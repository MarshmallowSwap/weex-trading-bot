"""Read-only view of existing Telegram manual TP acknowledgement mechanism.

Never creates confirmations or ignores shared-cross-margin risk. The
acknowledgement is an exception to the missing-TP capacity block only,
not authority to trade, protect, cancel or close manual positions.
"""
import json
from pathlib import Path
from weex_manual_position_ack import key,ACKS,PENDING,REQUESTS

def assess(root,positions):
    base={'source':'EXISTING_TELEGRAM_MANUAL_ACK','readOnly':True,
          'newEntriesAuthorized':False,'manualOrderModificationAuthorized':False,
          'crossMarginIsolation':False}
    if not isinstance(positions,list) or any(not isinstance(x,dict) for x in positions):
        return {**base,'status':'INVALID_POSITIONS','positions':[]}
    try:
        acknowledgements=json.loads((Path(root)/ACKS).read_text(encoding='utf-8'))
        if not isinstance(acknowledgements,dict):raise ValueError()
    except (OSError,ValueError,TypeError):
        acknowledgements={}
    try:
        pending=json.loads((Path(root)/PENDING).read_text(encoding='utf-8'))
        if not isinstance(pending,dict):pending={}
    except (OSError,ValueError,TypeError):pending={}
    result=[]
    for position in positions:
        try:
            fingerprint=key(position)
            saved=acknowledgements.get(fingerprint)
            valid=(isinstance(saved,dict) and
                   saved.get('identity',{}).get('id')==position.get('id') and
                   saved.get('identity',{}).get('symbol')==position.get('symbol'))
            result.append({'symbol':position.get('symbol'),
             'telegramAckConfirmed':valid,
             'telegramRequestPending':fingerprint in pending and not valid,
             'positionIdentityMatched':bool(valid),
             'botOwned':False,'mayTradeOnThisAcknowledgement':False})
        except (ValueError,TypeError,KeyError,AttributeError):
            result.append({'symbol':position.get('symbol'),'telegramAckConfirmed':False,
             'positionIdentityMatched':False,'botOwned':False,
             'mayTradeOnThisAcknowledgement':False})
    return {**base,'status':'READ_ONLY_ACK_OBSERVATION',
            'confirmedPositions':sum(x['telegramAckConfirmed'] for x in result),
            'positions':result}
