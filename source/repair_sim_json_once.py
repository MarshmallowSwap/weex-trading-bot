"""Repair a four-key WEEX sim credential JSON without printing secrets.
Only fixes unquoted scalar values or BOM; saves untouched value strings.
"""
import json,re
from pathlib import Path
p=Path(__file__).with_name('weex_sim_v3_credentials.json')
raw=p.read_text(encoding='utf-8-sig')
expected={'environment','api_key','secret_key','passphrase'}
try:
    obj=json.loads(raw)
    print('JSON_ALREADY_VALID')
except json.JSONDecodeError:
    lines=[x.strip() for x in raw.splitlines() if x.strip() not in ('','{','}')]
    data={}
    for line in lines:
        m=re.match(r'^"([a-z_]+)"\s*:\s*(.*?)\s*,?$',line)
        if not m:
            print('MANUAL_FORMAT_FIX_REQUIRED')
            raise SystemExit(0)
        key,value=m.groups()
        if key not in expected or key in data or not value:
            print('MANUAL_FORMAT_FIX_REQUIRED')
            raise SystemExit(0)
        value=value.rstrip(',').strip()
        if value.startswith('"') and value.endswith('"'):
            try:value=json.loads(value)
            except json.JSONDecodeError:value=value[1:-1]
        data[key]=value
    if set(data)!=expected or any(not isinstance(v,str) or not v for v in data.values()):
        print('MANUAL_FORMAT_FIX_REQUIRED')
        raise SystemExit(0)
    obj=data
if obj.get('environment')!='WEEX_SIM_V3':
    print('ENVIRONMENT_MISMATCH_NO_CHANGE')
    raise SystemExit(0)
if any(str(obj[k]).startswith('INSERISCI_') for k in expected if k!='environment'):
    print('CREDENTIAL_PLACEHOLDERS_REMAIN')
    raise SystemExit(0)
p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('JSON_REPAIRED_NO_SECRETS_PRINTED')
