"""Build uniquely journaled, dedicated-credential simulation trial.
Does not execute it and never changes production modules.
"""
from pathlib import Path
R=Path(__file__).resolve().parent
source=(R/'weex_sim_active_stop_close_trial_20261109.py').read_text(encoding='utf-8')
dest=R/'weex_sim_active_stop_close_trial_20261109_run2.py'
required=[
 ("FILE=R/'weex_sim_active_stop_close_trial_20261109.json'",
  "FILE=R/'weex_sim_active_stop_close_trial_20261109_run2.json'"),
 ("CLIENT='wxpilot_sim_eth_20261109_active1'",
  "CLIENT='wxpilot_sim_eth_20261109_run2'"),
 ("creds=json.loads((R/'weex_credentials.json').read_text())",
  "creds=json.loads((R/'weex_sim_v3_credentials.json').read_text());assert creds.get('environment')=='WEEX_SIM_V3'")
]
for old,new in required:
 if source.count(old)!=1:raise RuntimeError('UNEXPECTED_TRIAL_SOURCE')
 source=source.replace(old,new)
if dest.exists():raise PermissionError('TRIAL_SCRIPT_ALREADY_PREPARED')
dest.write_text(source,encoding='utf-8')
print({'created':dest.name,'dedicatedSimulationCredentials':True,'productionCredentialRead':False,
       'targetHost':'https://api-sim.weex.com','uniqueClient':'wxpilot_sim_eth_20261109_run2',
       'orderWritesExecuted':0})
