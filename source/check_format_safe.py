import json,pathlib
p=pathlib.Path(__file__).parent/"weex_credentials.json"
data=json.loads(p.read_text(encoding="utf-8"))
for k in ("api_key","secret_key","passphrase"):
 s=data[k]
 print(k,"length",len(s),"leading_or_trailing_spaces",s!=s.strip(),"real_line_break",("\r" in s or "\n" in s))
