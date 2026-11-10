"""Fail-closed proof for ONE TP resend when the first attempt never hit network.

Only a durable localNotSent marker from the guarded gateway qualifies.
Absence from WEEX history alone is not evidence of a non-submission.
No network or exchange write performed by this module.
"""
def marker(resp):
 if isinstance(resp,list):
  if len(resp)!=1:return False
  resp=resp[0]
 return (isinstance(resp,dict) and resp.get('success') is False
         and resp.get('localNotSent') is True
         and resp.get('reason')=='BLOCKED_BEFORE_NETWORK')

def eligible(writes,owned):
 if not isinstance(writes,dict) or not isinstance(owned,dict):return False
 original=writes.get('TP')
 if not isinstance(original,dict) or 'TP_REPAIR' in writes:return False
 if original.get('state')!='RESPONSE_RECEIVED' or not marker(original.get('response')):return False
 return (original.get('payload')==owned.get('tpRequest')
         and original.get('operation')==owned.get('tpOperation','post_capi_v3_placeTpSlOrder'))
