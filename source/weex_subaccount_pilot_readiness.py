"""One-shot WEEX dedicated-subaccount pilot readiness. GET-only; no trading writes.

A futures wallet can be empty and still share collateral with the main account.
The SDK accountConfig has no auditable subaccount identity, so the tool always
fails closed until an independently reviewed subaccount API identity attestation.
No file or environment flag in this module can enable the live worker.
"""
from datetime import datetime,timezone
from pathlib import Path
from decimal import Decimal
import json,os
import live_control
from weex_live_worker import Reader
from weex_live_new_entry_guard import evaluate as new_entry_guard
ROOT=Path(__file__).resolve().parent

def inspect(root=ROOT, *, get_account=None, read_identity=None):
 root=Path(root)
 mode=live_control.state(root)['mode']
 if mode!='STOPPED':raise PermissionError('PILOT_INSPECTION_REQUIRES_STOPPED_MODE')
 cfg,_=live_control.configuration(root)
 if get_account is None:get_account=lambda:Reader(root).account()
 positions,regular,conditional=get_account()
 if any(not isinstance(x,list) for x in (positions,regular,conditional)):
  raise ValueError('ACCOUNT_SNAPSHOT_INCOMPLETE')
 g=json.loads((root/'live_release_gate_latest.json').read_text(encoding='utf-8'))
 checks={
   'liveStopped':mode=='STOPPED',
   'configurationIntegrity':not live_control.build_errors(root),
   'noExistingPositions':not positions,
   'noPendingRegularOrders':not regular,
   'noPendingConditionalOrders':not conditional,
   'singlePilotOrderMax':True,
   'exchangeSubaccountSeparated':False, # Must be proven independently.
   'subaccountCollateralLimitVerified':False, # Wallet balance is not a loss ceiling.
   'liveCrashRecoveryVerified':g.get('checks',{}).get('crash_restart_recovery_live_tested') is True,
   'independentReleaseGateGo':g.get('gate')=='GO',
 }
 blockers=[name for name,value in checks.items() if not value]
 risk=new_entry_guard(cfg,positions,regular,conditional)
 blockers.extend(risk['issues'])
 result={'checkedAt':datetime.now(timezone.utc).isoformat(),
  'scope':'READ_ONLY_WEEX_SUBACCOUNT_PILOT_PREFLIGHT',
  'mode':mode,'pilotOrderMax':1,'liveTradingAuthorized':False,
  'proposedUse':'separate verified subaccount, tightly limited USDT collateral, single pilot',
  'subaccountIdentityProof':'NOT_OBTAINED_FROM_CURRENT_ACCOUNT_CONFIG_API',
  'checks':checks,'blockers':sorted(set(blockers)),
  'currentInventory':{'positions':len(positions),'regularOrders':len(regular),
                       'conditionalOrders':len(conditional)},
  'noExchangeWrites':True,'noTelegramMessages':True,
  'riskExplanation':'Cross margin uses the futures wallet collateral; stop loss OFF and high leverage do not bound the loss by order initial margin.',
  'requiredBeforeLive':['Verify independently that API credentials belong to dedicated WEEX subaccount (not main account).',
                        'Verify no collateral is shared with main account and confirm exact dedicated futures collateral budget.',
                        'Agree a bounded single-order pilot with explicit order size/side/leverage and single-use dispatch approval.',
                        'Certify crash/restart behavior against real WEEX exchange evidence after explicitly approved test.',
                        'Keep automated strategy and unrelated positions disabled until review.']}
 return result

def main():
 result=inspect()
 target=ROOT/'weex_subaccount_pilot_readiness_latest.json'
 temp=target.with_suffix('.tmp')
 temp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 os.replace(temp,target)
 print(json.dumps({'scope':result['scope'],'pilotAuthorized':result['liveTradingAuthorized'],
                   'inventory':result['currentInventory'],'blockers':result['blockers'],
                   'mode':result['mode'],'exchangeWrites':0},ensure_ascii=False))
if __name__=='__main__':main()
