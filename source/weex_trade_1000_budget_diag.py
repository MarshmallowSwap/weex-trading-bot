from weex_api_budget import Budget
import time
b=Budget()
print('USAGE',b.used())
print('LIMITS',b._limits())
with b.db() as c:
    now=time.time()
    print('META',[(k,round(v-now,1)) for k,v in c.execute("SELECT key,value FROM api_meta_v1 WHERE key IN ('pause','clock')")])
