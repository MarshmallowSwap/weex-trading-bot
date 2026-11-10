"""Independent dedicated-SIM GET-only audit for the new protected cycle."""
from pathlib import Path
R=Path(__file__).resolve().parent
source=(R/'weex_sim_active_stop_close_independent_audit_20261109.py').read_text(encoding='utf-8')
dest=R/'weex_sim_active_stop_close_independent_audit_20261109_run2.py'
pairs=[
 ("weex_sim_active_stop_close_trial_20261109.json","weex_sim_active_stop_close_trial_20261109_run2.json"),
 ("weex_sim_active_stop_close_independent_audit_20261109.json","weex_sim_active_stop_close_independent_audit_20261109_run2.json"),
 ("creds=json.loads((R/'weex_credentials.json').read_text())",
  "creds=json.loads((R/'weex_sim_v3_credentials.json').read_text());assert creds.get('environment')=='WEEX_SIM_V3'")
]
for old,new in pairs:
 if source.count(old)!=1:raise RuntimeError('INDEPENDENT_AUDIT_SOURCE_CHANGED')
 source=source.replace(old,new)
if dest.exists():raise PermissionError('AUDIT_SCRIPT_ALREADY_CREATED')
dest.write_text(source,encoding='utf-8')
print('INDEPENDENT_SIM_AUDITOR_CREATED')
