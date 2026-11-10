"""Evidence-scoped WEEX candidate release audit, NEVER arms trading.

Explicitly distinguishes real CROSS 1x pilot from global 125x+ automatic
strategy and scopes bounded economic proof; no gate override permitted.
"""
import json,os
from pathlib import Path
from datetime import datetime,timezone
import live_control
from weex_trading_modes import get_mode
from weex_live_worker import Reader
ROOT=Path(__file__).resolve().parent

def grade(*,gate,config,mode,integrity,pilot,ledger,crash,account):
    check=lambda b:b is True
    auto=(mode=='STOPPED' and config.get('execution',{}).get('enabled') is False
      and config.get('execution',{}).get('mode')=='PRETRADE')
    pilot_ok=(check(pilot.get('livePilotCycleCertified'))
      and check(pilot.get('livePilotAttachedStopCertified'))
      and check(pilot.get('livePilotReduceOnlyExitCertified'))
      and check(pilot.get('positionsAndPendingOrdersZero')))
    ledger_ok=(check(ledger.get('boundedLedgerAccountingCertified'))
      and check(ledger.get('ledgerWindowComplete'))
      and ledger.get('balanceArithmetic',{}).get('gaps')==[]
      and ledger.get('balanceArithmetic',{}).get('transitionsChecked')==1334)
    crash_ok=(check(crash.get('allSimulatedWriteBoundaryChecksPassed'))
      and crash.get('newProductionWrites')==0)
    flat=(isinstance(account,tuple) and len(account)==3
       and all(type(rows) is list and not rows for rows in account))
    gate_ok=(gate.get('gate')=='GO' and gate.get('passed')==gate.get('total')
       and gate.get('total')==10 and
       all(v is True for v in gate.get('checks',{}).values()))
    blockers=[]
    if not auto:blockers.append('BOT_NOT_DISARMED')
    if integrity:blockers.append('CODE_INTEGRITY_FAILED')
    if not flat:blockers.append('ACCOUNT_NOT_FLAT')
    if not pilot_ok:blockers.append('REAL_PILOT_NOT_PROVEN')
    if not ledger_ok:blockers.append('BOUNDED_LEDGER_NOT_PROVEN')
    if not crash_ok:blockers.append('SIMULATED_CRASH_NOT_PROVEN')
    if not gate_ok:
       blockers.extend('GLOBAL_'+k for k,v in gate.get('checks',{}).items() if v is not True)
    if not check(ledger.get('entireAccountLifetimeCertified')):
       blockers.append('LIFETIME_ACCOUNTING_NOT_CERTIFIED')
    if check(crash.get('realExchangeWriteActuallyInterrupted')) is not True:
       blockers.append('REAL_EXCHANGE_WRITE_CRASH_NOT_PROVEN')
    full_auto=False if blockers else gate_ok
    return {'candidatePrepared':auto and not integrity and flat and pilot_ok and ledger_ok and crash_ok,
      'globalTradingAuthorized':full_auto,
      'releaseStatus':'READY_FOR_ADDITIONAL_PRODUCTION_CERTIFICATION' if auto and not integrity and flat and pilot_ok and ledger_ok and crash_ok
         else 'CANDIDATE_BLOCKED',
      'accountEmpty':flat,'priorRealPilotCertified':pilot_ok,
      'boundedIncomeLedgerCertified':ledger_ok,'simulatedCrashRecovered':crash_ok,
      'globalGatePass':gate_ok,'blocks':blockers,'requiresExplicitFreshOrderAuthorization':True,
      'executionWrites':0,'botStarted':False}

def main():
    def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))
    gate=read('live_release_gate_latest.json')
    cfg=read('weex_ai_risk_config.json')
    p=read('weex_cross_live_pilot_certification_20261109.json')
    ledger=read('weex_income_ledger_arithmetic_certification_20261109.json')
    crash=read('weex_cross_crash_write_boundary_test_20261109.json')
    account=Reader(ROOT).account()
    status=grade(gate=gate,config=cfg,mode=live_control.state(ROOT)['mode'],
       integrity=live_control.build_errors(ROOT),pilot=p,ledger=ledger,
       crash=crash,account=account)
    status.update(checkedAt=datetime.now(timezone.utc).isoformat(),
       tradingMode=get_mode(ROOT)['mode'],marginPreference=cfg['risk']['marginModePreference'],
       generalStrategyMinLeverage=cfg['risk']['minimumLeverage'],
       generalStrategyStopLossEnabled=cfg['risk']['stopLoss']['enabled'],
       globalGatePassed=gate.get('passed'),globalGateTotal=gate.get('total'),
       sourceEvidence=['weex_cross_live_pilot_certification_20261109.json',
        'weex_income_ledger_arithmetic_certification_20261109.json',
        'weex_cross_crash_write_boundary_test_20261109.json',
        'live_release_gate_latest.json'])
    target=ROOT/'weex_RELEASE_CANDIDATE_20261109.json'
    temp=target.with_suffix('.tmp');temp.write_text(json.dumps(status,indent=2,ensure_ascii=False)+'\n')
    os.replace(temp,target)
    print(json.dumps(status))
if __name__=='__main__':main()
