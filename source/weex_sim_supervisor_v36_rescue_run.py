import tempfile,subprocess,sys,json
from pathlib import Path
r=Path(__file__).resolve().parent
root=Path(tempfile.gettempdir())/'weex_v36_sim_independent_rescue_persistent'
if root.exists():raise SystemExit('RESCUE_ALREADY_STARTED_NO_RETRY')
root.mkdir(mode=0o700)
cp=subprocess.run([sys.executable,'-B',
    str(r/'weex_sim_independent_supervisor_v36.py'),str(root),
    str(r/'weex_demo_independent_supervisor_v36_manifest.json')],
    cwd=str(r),capture_output=True,text=True,timeout=45)
print('CHILD_EXIT',cp.returncode)
print('OUT',cp.stdout[:4500])
print('STDERR_LAST',cp.stderr[-1400:])
print('RESCUE_ROOT',str(root))
