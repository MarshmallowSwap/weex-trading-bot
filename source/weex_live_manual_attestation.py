"""Immutable, user-attested classification of two existing WEEX manual positions.

This is NOT a bot-ownership proof or an API authorization. Each record is
bound to exact observed position fields; modifications/closures invalidate it.
Never changes exchange orders or suppresses shared-cross-margin risk.
"""
import json,os
from datetime import datetime,timezone
from pathlib import Path
from weex_manual_position_ack import identity,key
NAME='weex_live_manual_positions_attested.json'
EXPECTED={'TRUTHUSDT':'SHORT','UAIUSDT':'SHORT'}
def establish(root,positions,*,user_attested=False):
 if user_attested is not True:raise PermissionError('USER_ATTESTATION_REQUIRED')
 if not isinstance(positions,list) or len(positions)!=2:raise ValueError('EXPECTED_EXACTLY_TWO_MANUAL_POSITIONS')
 by={}
 for p in positions:
  if not isinstance(p,dict) or p.get('symbol') not in EXPECTED or p.get('side')!=EXPECTED[p['symbol']]:
   raise ValueError('UNKNOWN_OR_CHANGED_MANUAL_POSITION')
  sym=p['symbol']
  if sym in by:raise ValueError('DUPLICATE_SYMBOL')
  obj=identity(p)
  by[sym]={'positionFingerprint':key(p),'positionId':str(obj['id']),
           'side':obj['side'],'classification':'USER_ATTESTED_MANUAL',
           'botOwnership':False,'autoProtect':False,'autoClose':False}
 if set(by)!=set(EXPECTED):raise ValueError('MISSING_ATTESTED_POSITION')
 path=Path(root)/NAME
 doc={'source':'USER_ATTESTATION_IN_CHAT','checkedAt':datetime.now(timezone.utc).isoformat(),
      'records':by,'allowsEntryWhileCrossExposure':False,
      'automaticExchangeWrites':False}
 if path.exists():
  previous=json.loads(path.read_text(encoding='utf-8'))
  if previous.get('records')!=by:raise ValueError('IMMUTABLE_ATTESTATION_CHANGED_REVIEW_REQUIRED')
  return {'state':'ALREADY_ATTESTED','positionCount':2,'exchangeWrites':0}
 tmp=path.with_suffix('.tmp')
 tmp.write_text(json.dumps(doc,indent=2),encoding='utf-8')
 os.replace(tmp,path)
 return {'state':'ATTESTED_MANUAL_ONLY','positionCount':2,'exchangeWrites':0}
def classify(root,positions):
 try:
  data=json.loads((Path(root)/NAME).read_text(encoding='utf-8'))
  records=data['records']
  if data.get('source')!='USER_ATTESTATION_IN_CHAT' or data.get('automaticExchangeWrites') is not False:
   raise ValueError()
  result=[]
  for p in positions:
   v=records.get(p.get('symbol'))
   verified=(v is not None and v.get('side')==p.get('side')
      and v.get('positionId')==str(p.get('id'))
      and v.get('positionFingerprint')==key(p))
   result.append({'symbol':p.get('symbol'),
      'manualAttestationMatchesCurrentIdentity':bool(verified),
      'botOwnershipVerified':False,'canAutoProtect':False,'canAutoClose':False})
  complete=(len(result)==2 and all(x['manualAttestationMatchesCurrentIdentity'] for x in result)
            and {x['symbol'] for x in result}==set(EXPECTED))
  return {'state':'MANUAL_ATTESTATION_MATCHED' if complete else 'ATTESTATION_STALE_OR_POSITION_CHANGED',
          'allPositionsUserAttested':complete,'positions':result,'liveWrites':0,
          'allowsNewCrossEntries':False}
 except (OSError,KeyError,TypeError,ValueError):
  return {'state':'ATTESTATION_UNAVAILABLE','allPositionsUserAttested':False,
          'liveWrites':0,'allowsNewCrossEntries':False}
