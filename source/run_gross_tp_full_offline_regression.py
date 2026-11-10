"""Network-disabled WEEX regression runner. Never reads credentials or sends orders."""
import socket,unittest
from pathlib import Path
class NoNetworkSocket(socket.socket):
 def connect(self,*a,**kw):raise PermissionError('OFFLINE_REGRESSION_NETWORK_BLOCKED')
 def connect_ex(self,*a,**kw):raise PermissionError('OFFLINE_REGRESSION_NETWORK_BLOCKED')
socket.socket=NoNetworkSocket
exclude={'test_readonly','test_scopes'}
names=sorted(x.stem for x in Path(__file__).parent.glob('test_*.py')
             if x.stem not in exclude)
suite=unittest.defaultTestLoader.loadTestsFromNames(names)
result=unittest.TextTestRunner(verbosity=1).run(suite)
print('MODULES',len(names),'TESTS',result.testsRun,'FAIL',len(result.failures),'ERROR',len(result.errors),'SKIP',len(result.skipped))
raise SystemExit(0 if result.wasSuccessful() else 1)
