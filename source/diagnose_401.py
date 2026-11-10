from pathlib import Path
p=Path(__file__).resolve().parent/"test_readonly.py"
s=p.read_text(encoding="utf-8")
s=s.replace('print("WEEX_API_REJECTED",e.code, "check permission, KYC, signed headers, IP whitelist")','''body=e.read(1024).decode("utf-8","replace")
        try:
            payload=json.loads(body)
            detail={k:payload.get(k) for k in ("code","msg","message","error") if k in payload}
        except Exception:
            detail={"response":"non JSON"}
        print("WEEX_API_REJECTED",e.code,"DETAIL",detail)''')
p.write_text(s,encoding="utf-8")
