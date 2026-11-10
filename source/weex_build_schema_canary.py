from pathlib import Path
src=Path(__file__).with_name('weex_sim_partial_close_canary.py')
body=src.read_text(encoding='utf-8')
anchor="        s['tpAndSlInitiallySeen']=len(observed[ALGOS])==2"
insert="""        s['simAlgoSchema']=[{'keys':sorted(x.keys()),
           'orderType':x.get('orderType'),
           'planType':x.get('planType'),
           'algoStatus':x.get('algoStatus'),
           'side':x.get('side'),'reduceOnly':x.get('reduceOnly'),
           'hasClientAlgoId':bool(x.get('clientAlgoId')),
           'algoIdIsInt':isinstance(x.get('algoId'),int)}
           for x in observed[ALGOS]]
"""
if body.count(anchor)!=1:raise ValueError('UNIQUE_ANCHOR_MISSING')
body=body.replace(anchor,insert+anchor)
target=src.with_name('weex_sim_algo_schema_canary_once.py')
target.write_text(body,encoding='utf-8')
compile(body,str(target),'exec')
print('SCHEMA_ONLY_DEMO_CANARY_READY')
