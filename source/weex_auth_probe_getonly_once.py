"""One-shot WEEX API auth triage, GET ONLY, redacted diagnostic.

Use the locally provided key strictly for signed account/balance GET on
both WEEX hostnames. Never print credentials, response bodies, balances,
identifiers, HTTP headers, or exception strings. No write operation exists.
"""
import base64,hashlib,hmac,json,time,urllib.request,urllib.error
from pathlib import Path
P=Path(__file__).with_name('weex_sim_v3_credentials.json')
PATH='/capi/v3/account/balance'
def run():
    c=json.loads(P.read_text(encoding='utf-8-sig'))
    assert c['environment']=='WEEX_SIM_V3'
    hosts=('api-sim.weex.com','api-contract.weex.com')
    for host in hosts:
        ts=str(int(time.time()*1000))
        sig=base64.b64encode(hmac.new(c['secret_key'].encode(),
                 (ts+'GET'+PATH).encode(),hashlib.sha256).digest()).decode()
        req=urllib.request.Request('https://'+host+PATH,method='GET',
            headers={'ACCESS-KEY':c['api_key'],'ACCESS-SIGN':sig,
                     'ACCESS-TIMESTAMP':ts,'ACCESS-PASSPHRASE':c['passphrase'],
                     'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=8) as rsp:
                status=rsp.status
                body=rsp.read(2048)
        except urllib.error.HTTPError as e:
            status=e.code
            body=e.read(2048)
        except Exception as e:
            print(host,'NETWORK_ERROR',type(e).__name__)
            continue
        # Only known error code; NEVER reveal msg or any other response.
        code=None
        try:
            data=json.loads(body)
            if isinstance(data,dict):
                value=data.get('code')
                if isinstance(value,(str,int)) and str(value).lstrip('-').isdigit():code=int(value)
        except (ValueError,TypeError):pass
        print(host,'HTTP_STATUS',status,'ERROR_CODE',code)
if __name__=='__main__':run()
