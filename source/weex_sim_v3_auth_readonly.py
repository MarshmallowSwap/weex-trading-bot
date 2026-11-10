"""Dedicated WEEX V3 simulation-account read-only readiness.

NEVER falls back to WEEX production credentials, host or endpoints.
Private GET calls require separately supplied simulation credentials.
No order submission/cancel method exists in this module.
"""
import base64,hashlib,hmac,json,time,urllib.request,urllib.error
from pathlib import Path
from weex_sim_v3_guard import assess,SIM_HOST
ROOT=Path(__file__).resolve().parent
CREDENTIALS=ROOT/'weex_sim_v3_credentials.json'
SIM_URL='https://'+SIM_HOST
PATHS=('/capi/v3/account/balance','/capi/v3/account/position/allPosition')

def readiness(credentials_path=CREDENTIALS):
    path=Path(credentials_path)
    if not path.is_file():
        return {'status':'BLOCKED','reason':'DEDICATED_SIM_CREDENTIALS_MISSING',
                'credentialsVerified':False,'privateReadsAttempted':0,
                'ordersSubmitted':False,'productionCredentialsRead':False}
    try:
        credentials=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(credentials,dict) or any(
            not isinstance(credentials.get(k),str) or not credentials.get(k)
            for k in ('api_key','secret_key','passphrase')):
            raise ValueError('INVALID_SIM_CREDENTIALS_SCHEMA')
        if credentials.get('environment')!='WEEX_SIM_V3':
            raise ValueError('EXPLICIT_SIM_ENVIRONMENT_TAG_REQUIRED')
        if set(credentials)-{'api_key','secret_key','passphrase','environment'}:
            raise ValueError('UNEXPECTED_CREDENTIALS_FIELDS')
        return {'status':'READY_FOR_READ_ONLY_AUTH_CHECK',
                'credentialsVerified':False,'privateReadsAttempted':0,
                'ordersSubmitted':False,'productionCredentialsRead':False}
    except (OSError,ValueError,TypeError,UnicodeError):
        return {'status':'BLOCKED','reason':'INVALID_SIM_CREDENTIAL_FILE',
                'credentialsVerified':False,'privateReadsAttempted':0,
                'ordersSubmitted':False,'productionCredentialsRead':False}

def signed_get(operation,*,credentials_path=CREDENTIALS,opener=None):
    """Single authenticated simulation GET. Never log or return secrets."""
    status=readiness(credentials_path)
    if status['status']!='READY_FOR_READ_ONLY_AUTH_CHECK':
        return status
    if operation not in PATHS:
        return {'status':'BLOCKED','reason':'OPERATION_NOT_ALLOWED',
                'ordersSubmitted':False,'productionCredentialsRead':False}
    target=SIM_URL+operation
    if assess('GET',target).get('allowed') is not True:
        raise PermissionError('SIM_GET_FIREWALL_DENIED')
    c=json.loads(Path(credentials_path).read_text(encoding='utf-8'))
    ts=str(int(time.time()*1000))
    payload=(ts+'GET'+operation).encode('utf-8')
    signature=base64.b64encode(hmac.new(c['secret_key'].encode(),payload,hashlib.sha256).digest()).decode()
    request=urllib.request.Request(target,headers={
        'ACCESS-KEY':c['api_key'],'ACCESS-SIGN':signature,
        'ACCESS-PASSPHRASE':c['passphrase'],'ACCESS-TIMESTAMP':ts,
        'Content-Type':'application/json'},method='GET')
    transport=opener or urllib.request.urlopen
    try:
        with transport(request,timeout=8) as response:
            result=json.load(response)
        if not isinstance(result,(dict,list)):
            raise ValueError('INVALID_SIM_RESPONSE')
        return {'status':'SIM_PRIVATE_GET_REACHED','responseType':type(result).__name__,
                'privateReadsAttempted':1,'ordersSubmitted':False,
                'productionCredentialsRead':False,
                'credentialsVerified':True,
                'simulationAccountIsolationVerified':False,
                'closeOnlyExitCertified':False}
    except urllib.error.HTTPError as exc:
        return {'status':'SIM_PRIVATE_GET_FAILED','errorType':'HTTPError',
                'httpStatus':exc.code,'privateReadsAttempted':1,
                'ordersSubmitted':False,'productionCredentialsRead':False,
                'credentialsVerified':False}
    except Exception as exc:
        return {'status':'SIM_PRIVATE_GET_FAILED','errorType':type(exc).__name__,
                'privateReadsAttempted':1,'ordersSubmitted':False,
                'productionCredentialsRead':False,'credentialsVerified':False}

if __name__=='__main__':
    print(json.dumps(readiness()))
