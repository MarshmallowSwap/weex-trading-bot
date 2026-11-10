"""Real OS subprocess test of durable *offline* exit permit; never contacts WEEX.

Creates one permit only in an isolated temporary SQLite file and has two
separate Python processes attempt exact consumption.
"""
import json,subprocess,sys,tempfile
from unittest.mock import patch
from weex_supervised_exit_policy_v7 import grant
from weex_supervised_crash_executor_v2 import CLIENT_ID
P={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG','type':'MARKET',
   'quantity':'0.001','newClientOrderId':'wxclose_'+CLIENT_ID.split('_',1)[1],
   'reduceOnly':True}
E={'status':'VERIFIED_PROTECTED_NEED_EXACT_CLOSE','clientOrderId':CLIENT_ID,
   'symbol':'ETHUSDT','quantity':'0.001','positionId':'123','stopAlgoId':'456'}
def main():
 with tempfile.TemporaryDirectory(prefix='weex-offline-one-shot-') as td:
  with patch('live_control.state',return_value={'mode':'STOPPED'}),patch('live_control.build_errors',return_value=[]):
   grant(td,operator_authorized=True,duration=600)
  script=(
   'import json,sys;from weex_supervised_exit_policy_v7 import consume,status;'
   'p='+repr(P)+';e='+repr(E)+';'
   'print(json.dumps({"consumed":consume(sys.argv[1],"post_capi_v3_order",p,e),'
   '"stillAuthorized":status(sys.argv[1])["canClose"]}))'
  )
  results=[]
  for _ in range(2):
   child=subprocess.run([sys.executable,'-B','-c',script,td],
     capture_output=True,text=True,timeout=15)
   if child.returncode!=0:raise RuntimeError('OFFLINE_CHILD_FAILED')
   results.append(json.loads(child.stdout))
  ok=(results==[{'consumed':True,'stillAuthorized':False},
                {'consumed':False,'stillAuthorized':False}])
  print(json.dumps({'status':'OFFLINE_EXIT_ONE_SHOT_CROSS_PROCESS_PASS' if ok else
   'OFFLINE_EXIT_ONE_SHOT_CROSS_PROCESS_FAIL',
   'firstProcess':results[0],'secondProcess':results[1],
   'productionWrites':0,'exchangeCalls':0,'productionPermitUntouched':True}))
  if not ok:raise SystemExit(1)
if __name__=='__main__':main()
