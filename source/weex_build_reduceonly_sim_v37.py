from pathlib import Path
R=Path(__file__).resolve().parent
def make(source,target,edits):
 text=(R/source).read_text(encoding='utf-8')
 for old,new in edits:
  if text.count(old)!=1:raise ValueError(source+' NOT_UNIQUE '+repr(old)+' '+str(text.count(old)))
  text=text.replace(old,new,1)
 out=R/target
 if out.exists():raise FileExistsError(str(out))
 compile(text,str(out),'exec')
 out.write_text(text,encoding='utf-8')
 print('BUILT',target)
make('weex_sim_independent_supervisor_v36.py','weex_sim_independent_supervisor_v37.py',[
 ("'wxpilot_crashsim_v36a01'","'wxpilot_crashsim_v37a01'"),
 ("GETS=('get_capi_v3_account_position_allPosition','get_capi_v3_openOrders',\n      'get_capi_v3_openAlgoOrders','get_capi_v3_order_history')",
  "GETS=('get_capi_v3_account_position_allPosition','get_capi_v3_openOrders',\n      'get_capi_v3_openAlgoOrders','get_capi_v3_order_history','get_capi_v3_order')"),
 ("u.path!='/capi/v3/closePositions'","u.path!='/capi/v3/order'"),
 ("close={'symbol':'ETHUSDT','positionId':int(p['id'])}",
  "close={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG','type':'MARKET',\n     'quantity':'0.002','newClientOrderId':'wxclose_crashsim_v37a01','reduceOnly':True}"),
 ("ack=api.rest_api.execute_operation('post_capi_v3_closePositions',{'body':close}).data\n   good=isinstance(ack,list) and len(ack)==1 and ack[0].get('success') is True and str(ack[0].get('positionId'))==str(close['positionId'])\n   close_receipt.update(closePosts=1,closeAcknowledged=good,\n                       closeOrderId=str(ack[0].get('successOrderId')) if good else None)",
  "ack=api.rest_api.execute_operation('post_capi_v3_order',{'body':close}).data\n   order_id=str(ack.get('orderId','')) if isinstance(ack,dict) else ''\n   good=order_id.isdigit()\n   close_receipt.update(closePosts=1,closeAcknowledged=good,closeOrderId=order_id or None)"),
 ("   flat=all(x==[] for x in remaining)\n   close_receipt['flatReadback']=flat",
  "   flat=all(x==[] for x in remaining)\n   close_order=get('get_capi_v3_order',{'orderId':order_id}) if good else {}\n   fully_filled=(isinstance(close_order,dict) and close_order.get('status')=='FILLED'\n      and close_order.get('reduceOnly') is True and close_order.get('symbol')=='ETHUSDT'\n      and close_order.get('side')=='SELL' and close_order.get('positionSide')=='LONG'\n      and str(close_order.get('orderId'))==order_id\n      and D(str(close_order.get('executedQty','0')))==D('0.002'))\n   close_receipt['exactReduceOnlyFillVerified']=fully_filled\n   close_receipt['flatReadback']=flat"),
 ("if good and flat else","if good and flat and fully_filled else"),
 ("'verifiedFlat':bool(good and flat)","'verifiedFlat':bool(good and flat and fully_filled)"),
 ("'exitEndpoint':'post_capi_v3_closePositions'","'exitEndpoint':'post_capi_v3_order_reduceOnly'")
])
make('weex_demo_independent_supervisor_trial_v36.py','weex_demo_independent_supervisor_trial_v37.py',[
 ("'weex_demo_independent_supervisor_v36_result.json'","'weex_demo_independent_supervisor_v37_result.json'"),
 ("'weex_demo_independent_crash_child_v36.py'","'weex_demo_independent_crash_child_v37.py'"),
 ("'wxpilot_crashsim_v36a01'","'wxpilot_crashsim_v37a01'"),
 ("'weex_demo_independent_child_v36_state.json'","'weex_demo_independent_child_v37_state.json'"),
 ("'weex_demo_independent_child_v36_state.json'","'weex_demo_independent_child_v37_state.json'"),
 ("'weex_demo_independent_supervisor_v36_manifest.json'","'weex_demo_independent_supervisor_v37_manifest.json'"),
 ("'weex_sim_independent_supervisor_v36.py'","'weex_sim_independent_supervisor_v37.py'"),
 ("'weex_sim_independent_v36_'","'weex_sim_independent_v37_'")
])
