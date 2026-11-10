"""Collect simulation-domain evidence only. Always stop before any submission."""
import json
from decimal import Decimal
from pathlib import Path
from datetime import datetime,timezone
from weex_simulation_domain import SIM,SimulationSession,SimulationGateway,validate_contract,create_runtime
from weex_execution_readonly import pages
from weex_simulation_depth import assess

def run(root=None):
    root=Path(root or Path(__file__).parent)
    cfg_bytes=(root/'weex_ai_risk_config.json').read_bytes()
    cfg=json.loads(cfg_bytes)
    if cfg['execution']['enabled'] is not False or cfg['execution']['mode']!='PRETRADE':
        raise PermissionError('PRODUCTION_MUST_REMAIN_DISABLED')
    gateway=SimulationGateway(root/'weex_credentials.json')
    runtime=create_runtime(root,gateway,cfg)
    public_session=SimulationSession()
    report={'checkedAt':datetime.now(timezone.utc).isoformat(),'host':SIM,'symbol':'BTCUSDT',
            'mode':'SIMULATION_READ_ONLY','ordersSubmitted':False,'httpWritesEnabled':False,
            'checks':{},'blockers':[],'executablePlan':None}
    data={}
    for name,path,params in [('metadata','/capi/v3/market/exchangeInfo',{'symbol':'BTCUSDT'}),
        ('tiers','/capi/v3/market/riskLimits',{'symbol':'BTCUSDT'}),
        ('apiSymbols','/capi/v3/market/apiTradingSymbols',{}),
        ('depth','/capi/v3/market/depth',{'symbol':'BTCUSDT','limit':15}),
        ('book','/capi/v3/market/ticker/bookTicker',{'symbol':'BTCUSDT'})]:
        try:
            response=public_session.request('GET',SIM+path,params=params,timeout=10)
            if response.status_code!=200:raise RuntimeError('PUBLIC_HTTP_ERROR')
            data[name]=response.json();report['checks'][name]={'ok':True}
        except Exception as exc:
            report['checks'][name]={'ok':False,'errorType':type(exc).__name__}
            report['blockers'].append(name.upper()+'_UNAVAILABLE')
    public_session.close()
    calls=[('account','get_capi_v3_account_accountConfig',{}),
           ('balance','get_capi_v3_account_balance',{}),
           ('positions','get_capi_v3_account_position_allPosition',{}),
           ('settings','get_capi_v3_account_symbolConfig',{'symbol':'BTCUSDT'}),
           ('fees','get_capi_v3_account_commissionRate',{'symbol':'BTCUSDT'})]
    for name,operation,query in calls:
        try:
            data[name]=gateway.read(operation,**query);report['checks'][name]={'ok':True}
        except Exception as exc:
            report['checks'][name]={'ok':False,'errorType':type(exc).__name__}
            report['blockers'].append(name.upper()+'_UNAVAILABLE')
    for name,op,identity,start in [('openOrders','get_capi_v3_openOrders','orderId',0),
                                  ('tpOrders','get_capi_v3_openAlgoOrders','algoId',1)]:
        try:
            data[name]=pages(gateway.read,op,identity=identity,start=start)
            report['checks'][name]={'ok':True,'count':len(data[name])}
        except Exception as exc:
            report['checks'][name]={'ok':False,'errorType':type(exc).__name__}
            report['blockers'].append(name.upper()+'_UNAVAILABLE')
    meta=None
    try:
        meta=next(r for r in data['metadata']['symbols'] if r['symbol']=='BTCUSDT')
        report['contract']={k:meta.get(k) for k in ('symbol','quoteAsset','marginAsset','forwardContractFlag','quantityPrecision','maxLeverage')}
        evidence_path=root/'simulation_domain'/'settlement_calibration.json'
        evidence=json.loads(evidence_path.read_text(encoding='utf-8')) if evidence_path.exists() else None
        rules=validate_contract(meta,source_host=SIM,evidence=evidence)
        report['contractValidationScope']={k:str(v) for k,v in rules.items()}
        if rules.get('strategySizeValidated') is False:
            report['blockers'].append('EMPIRICAL_EVIDENCE_MINIMUM_SIZE_ONLY')
        report['contractRulesValidated']=True
    except Exception as exc:
        report['contractRulesValidated']=False
        report['blockers'].append('CONTRACT_METADATA_NOT_VALIDATED')
        report['contractValidationError']=type(exc).__name__
    if 'apiSymbols' in data and 'BTCUSDT' not in data['apiSymbols']:report['blockers'].append('SYMBOL_NOT_API_ENABLED')
    if isinstance(data.get('account'),dict):
        report['accountCanTrade']=data['account'].get('canTrade')
        report['hedgeMode']=data['account'].get('dualSidePosition')
        if report['accountCanTrade'] is not True or report['hedgeMode'] is not True:report['blockers'].append('ACCOUNT_MODE_UNCONFIRMED')
    if isinstance(data.get('positions'),list):
        report['positionCount']=len(data['positions'])
        if data['positions']:report['blockers'].append('PREEXISTING_SIMULATION_POSITION')
    elif 'positions' in data:report['blockers'].append('INVALID_POSITIONS_SCHEMA')
    if isinstance(data.get('balance'),list):
        report['balanceAssetLabels']=[r.get('asset') for r in data['balance']]
        report['fiveSimulatedUnitsAvailable']=any(r.get('asset')=='USDT' and Decimal(str(r.get('availableBalance','0')))>=5 for r in data['balance'])
        if not report['fiveSimulatedUnitsAvailable']:report['blockers'].append('SIMULATION_BALANCE_INSUFFICIENT')
    for name in ('openOrders','tpOrders'):
        if data.get(name):report['blockers'].append('PREEXISTING_'+name.upper())
    if isinstance(data.get('settings'),list):
        report['symbolSettings']=[{k:r.get(k) for k in ('symbol','marginType','crossLeverage')} for r in data['settings'] if r.get('symbol')=='BTCUSDT']
    try:
        evidence=json.loads((root/'simulation_domain'/'depth_unit_evidence.json').read_text(encoding='utf-8'))
        report['book']=assess('BTCUSDT',meta,data['depth'],evidence,source_host=SIM)
        report['simulationDepthUnitsValidated']=report['book']['depthUnitVerified']
    except Exception as exc:
        report['simulationDepthUnitsValidated']=False
        report['depthValidationError']=type(exc).__name__
    if not report['simulationDepthUnitsValidated']:
        report['blockers'].append('SIMULATION_DEPTH_UNIT_EVIDENCE_REQUIRED')
    report['blockers']+=['FRESH_EXECUTION_PREFLIGHT_REQUIRED',
                         'CONTINUOUS_SIMULATION_TRADING_DISABLED']
    report['state']='BLOCKED_BEFORE_ORDER_PREPARATION'
    report['journalSeparateFromProduction']=runtime.path.parent.name=='simulation_domain'
    report['journalTradeCount']=len(runtime.states())
    assert (root/'weex_ai_risk_config.json').read_bytes()==cfg_bytes
    report['productionConfigurationUnchanged']=True
    path=root/'simulation_domain'/'preflight_latest.json'
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    r=run()
    print(json.dumps({k:r[k] for k in ('host','state','blockers','journalSeparateFromProduction','ordersSubmitted')}))
