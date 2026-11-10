from weex_http_guard import prepare_sdk_request
p={'symbol':'ETHUSDT','side':'SELL','positionSide':'LONG','type':'MARKET','quantity':'0.002','newClientOrderId':'wxclose_sim_v37a01','reduceOnly':True}
print(prepare_sdk_request('post_capi_v3_order',p))
