"""Read-only static inspection of QUARANTINED crash-test prototype. Never import/execute its sources."""
import ast,zipfile,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
z=ROOT/'weex_50x_crash_UNRELEASED_20261109.zip'
results=[]
with zipfile.ZipFile(z) as archive:
    for name in archive.namelist():
        raw=archive.read(name)
        source=raw.decode('utf-8-sig')
        try:
            tree=ast.parse(source,filename=name)
            syntax='PASS'
        except SyntaxError as exc:
            syntax='FAIL_'+str(exc.lineno)
            tree=None
        imported=[x.module for x in ast.walk(tree) if isinstance(x,ast.ImportFrom)] if tree else []
        results.append({'name':name,'sha256':hashlib.sha256(raw).hexdigest(),
          'syntax':syntax,'imports':imported})
    child=archive.read('weex_real_50x_crash_child_20261109.py').decode('utf-8-sig')
    parent=archive.read('weex_real_50x_crash_supervisor_20261109.py').decode('utf-8-sig')
    prototype=archive.read('weex_refactor_50x_supervisor_20261109.py').decode('utf-8-sig')
findings=[
 {'severity':'BLOCKER','id':'CRASH_LIFECYCLE_OUT_OF_MANIFEST','present':True,
 'detail':'Prototype requires editing protected Lifecycle and release gate, both restored to certified state.'},
 {'severity':'BLOCKER','id':'GUARD_BYPASS_FOR_TEST_ENTRY','present':"engine.send_once(" in child,
 'detail':'Direct send_once path does not invoke normal Lifecycle.guard full fresh context/dispatch_permission.'},
 {'severity':'BLOCKER','id':'RECOVERY_NOT_ASSURED_ON_SUPERVISOR_TERMINATION','present':'subprocess.run(' in parent,
 'detail':'Original supervisor runs child synchronously and lacks independent externally supervised guaranteed close.'},
 {'severity':'BLOCKER','id':'EXCHANGE_READBACK_API_BUDGET_DEPENDENT','present':'order_history(reader)' in parent,
 'detail':'Recovery relies on API quota and bounded history rather than a guaranteed exchange-independent emergency closer.'},
 {'severity':'BLOCKER','id':'UNTESTED_REFACTOR_ARCHIVED_SEPARATELY','present':True,
 'detail':'Resumable refactor is source code in ZIP but is not verified or deployed.'},
 {'severity':'WARNING','id':'CROSS_COLLATERAL_EXPOSED','present':True,
 'detail':'50x small notional is not a guaranteed limit on loss of cross-margin collateral.'},
]
report={'status':'NOT_RELEASE_READY','archiveSha256':hashlib.sha256(z.read_bytes()).hexdigest(),
 'archiveSources':results,'blockers':[x for x in findings if x['severity']=='BLOCKER' and x['present']],
 'warnings':[x for x in findings if x['severity']=='WARNING'],
 'sourceExecuted':False,'exchangeWrites':0,'automaticTradingActivated':False}
print(json.dumps(report,ensure_ascii=False))
