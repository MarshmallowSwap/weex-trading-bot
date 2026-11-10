"""Exactly one scoped real WEEX ETHUSDT CROSS 50x account setting.
No entries, closes, cancels, other markets, auto-retries, or bot activation.
A durable reservation BEFORE network makes a crash/timeout no-retry.
"""
import json,os,requests
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from weex_http_guard import sdk_types,prepare_sdk_request
from weex_api_budget import request as budget_request
from weex_eth_50x_protected_preflight import live_preflight
from weex_live_worker import Reader
import live_control

ROOT=Path(__file__).resolve().parent
STATE=ROOT/'weex_eth_50x_leverage_setup_once.json'
BODY={'symbol':'ETHUSDT','marginType':'CROSSED','crossLeverage':'50'}
HOST='https://api-contract.weex.com'
OP='post_capi_v3_account_leverage'

def save(value):
    tmp=STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    os.replace(tmp,STATE)

def check_setup(root=ROOT):
    reader=Reader(root)
    state=reader.read('get_capi_v3_account_symbolConfig',symbol='ETHUSDT')
    return bool(isinstance(state,list) and len(state)==1 and
        state[0].get('symbol')=='ETHUSDT' and state[0].get('marginType') in ('CROSS','CROSSED') and
        state[0].get('separatedType')=='COMBINED' and
        str(state[0].get('crossLeverage'))=='50')

class OnlyLeverage:
    def __init__(self):
        self.session=requests.Session()
        self.attempts=0
    def request(self,method,url,**kw):
        uri=urlsplit(url)
        if (self.attempts!=0 or method!='POST' or uri.scheme!='https' or
            uri.netloc!='api-contract.weex.com' or uri.path!='/capi/v3/account/leverage' or
            uri.query or uri.fragment or kw.get('json') is not None or kw.get('params') or
            json.loads(kw.get('data') or '{}')!=BODY):
            raise PermissionError('UNSCOPED_OR_REPEATED_SETTING_WRITE')
        self.attempts+=1
        kw['allow_redirects']=False
        response=budget_request(self.session,method,url,**kw)
        if not 200<=response.status_code<300:
            raise RuntimeError('LEVERAGE_HTTP_OUTCOME_UNKNOWN')
        return response
    def close(self):self.session.close()

def run():
    result={'status':'BLOCKED','exchange':'WEEX_REAL','scope':'ETH_CROSS_50X_SETTING_ONLY','ordersSent':0}
    if live_control.state(ROOT)['mode']!='STOPPED' or live_control.build_errors(ROOT):
        result['reason']='BOT_NOT_STOPPED_OR_INTEGRITY';return result
    risk=json.loads((ROOT/'weex_ai_risk_config.json').read_text())
    if risk['risk']['minimumLeverage']!=50 or risk['execution']['enabled'] is not False:
        result['reason']='STRATEGY_CONFIG_CHANGED';return result
    if STATE.exists():
        saved=json.loads(STATE.read_text(encoding='utf-8'))
        if saved.get('status')=='VERIFIED':
            result.update(status='ALREADY_VERIFIED_NO_RESEND');return result
        # No repeat POST after an uncertain result. A GET may recover evidence.
        try:
            if check_setup(ROOT):
                saved['status']='VERIFIED';saved['source']='RECOVERED_BY_EXCHANGE_READBACK'
                save(saved)
                result.update(status='VERIFIED_FROM_READBACK_NO_RESEND')
            else:result.update(status='UNKNOWN_NO_RETRY',reason='PREVIOUS_REQUEST_RESERVED')
        except Exception as exc:result.update(status='UNKNOWN_NO_RETRY',reason=type(exc).__name__)
        return result
    pre=live_preflight(ROOT)
    if not (pre.get('status')=='AWAIT_50X_ACCOUNT_SETUP_AND_CRASH_EXECUTOR'
            and pre.get('accountFlatVerified') is True
            and pre.get('liveMarketReadback') is True
            and pre.get('quantity')=='0.001'
            and pre.get('leverageSetupRequired') is True
            and pre.get('symbol')=='ETHUSDT'):
        result.update(reason='PREFLIGHT_NOT_READY',preflight=pre.get('status'));return result
    prepare_sdk_request(OP,BODY)
    # State is durable before the exchange POST; all future runs reconcile only.
    state={'createdAt':datetime.now(timezone.utc).isoformat(),
       'status':'REQUEST_RESERVED','scope':'ETH_CROSS_50X_SETTING_ONLY',
       'exchangeWritesAuthorized':1,'orderWritesAuthorized':0,'body':BODY,
       'mainBotRemainsStopped':True}
    save(state)
    transport=OnlyLeverage()
    try:
        config,contract,ops=sdk_types()
        creds=json.loads((ROOT/'weex_credentials.json').read_text(encoding='utf-8'))
        client=contract(config_rest_api=config(base_path=HOST,
            api_key=creds['api_key'],api_secret=creds['secret_key'],
            passphrase=creds['passphrase'],session=transport,timeout=8,max_retries=0))
        response=client.rest_api.execute_operation(OP,{'body':BODY})
        state['status']='POST_RETURNED_READBACK_REQUIRED'
        state['httpStatus']=response.status_code
        save(state)
    except Exception as exc:
        state['status']='OUTCOME_UNKNOWN_NO_RETRY'
        state['errorType']=type(exc).__name__
        save(state)
    finally:transport.close()
    try:
        if check_setup(ROOT):
            state['status']='VERIFIED'
            state['source']='EXCHANGE_SYMBOL_CONFIGURATION_READBACK'
            save(state)
            result.update(status='VERIFIED_50X',settingWritesAttempted=transport.attempts)
        else:result.update(status='UNKNOWN_NO_RETRY',reason='EXCHANGE_NOT_50X')
    except Exception as exc:
        result.update(status='UNKNOWN_NO_RETRY',reason='READBACK_'+type(exc).__name__)
    return result

if __name__=='__main__':
    print(json.dumps(run(),ensure_ascii=False))
