"""WEEX signed read-only account connectivity smoke test (NO TRADING)."""
import base64, hashlib, hmac, json, os, pathlib, sys, time, urllib.request, urllib.error
ROOT=pathlib.Path(__file__).resolve().parent
CONFIG=ROOT/"weex_credentials.json"
BASE="https://api-contract.weex.com"

def check():
    if not CONFIG.is_file():
        print("MISSING_CREDENTIALS: run setup_weex.ps1 locally first")
        return 2
    cfg=json.loads(CONFIG.read_text(encoding="utf-8"))
    if not all(cfg.get(k) for k in ("api_key","secret_key","passphrase")):
        print("MISSING_CREDENTIAL_FIELDS")
        return 2
    def signed_get(path):
        timestamp=str(int(time.time()*1000))
        signing=timestamp+"GET"+path
        signature=base64.b64encode(hmac.new(cfg["secret_key"].encode(),signing.encode(),hashlib.sha256).digest()).decode()
        headers={
          "ACCESS-KEY":cfg["api_key"],
          "ACCESS-SIGN":signature,
          "ACCESS-PASSPHRASE":cfg["passphrase"],
          "ACCESS-TIMESTAMP":timestamp,
          "Content-Type":"application/json"}
        req=urllib.request.Request(BASE+path,headers=headers)
        with urllib.request.urlopen(req,timeout=20) as res:
            return json.load(res)
    try:
        positions=signed_get("/capi/v3/account/position/allPosition")
        if not isinstance(positions,list):raise ValueError("unexpected response shape")
        print("WEEX_READ_ONLY_OK")
        print("POSITIONS",len(positions))
        for p in positions[:12]:
            print("POSITION",p.get("symbol","?"),p.get("side","?"),"leverage",p.get("leverage","?"),"size",p.get("size","?"))
        return 0
    except urllib.error.HTTPError as e:
        body=e.read(1024).decode("utf-8","replace")
        try:
            payload=json.loads(body)
            detail={k:payload.get(k) for k in ("code","msg","message","error") if k in payload}
        except Exception:
            detail={"response":"non JSON"}
        print("WEEX_API_REJECTED",e.code,"DETAIL",detail)
        return 1
    except Exception as e:
        print("WEEX_TEST_FAILED",type(e).__name__,str(e)[:180])
        return 1
if __name__=="__main__":sys.exit(check())
