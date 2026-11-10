"""WEEX read-only paginated conditional orders; fail closed on incomplete fetches."""
from monitor import query
def fetch_pages(path_template,max_pages=5,limit=100,start=1):
 if not 1<=max_pages<=20 or not 1<=limit<=100:raise ValueError("Invalid bounds")
 rows=[];seen=set();complete=False;pages=0
 for idx in range(start,start+max_pages):
  path=path_template.format(limit=limit,page=idx)
  data=query(path)
  if not isinstance(data,list):raise ValueError("Unexpected WEEX response")
  pages+=1
  for row in data:
   if not isinstance(row,dict):raise ValueError("Invalid row")
   key=str(row.get("algoId") or row.get("orderId") or row.get("clientAlgoId") or "")
   if not key:raise ValueError("Order identity unavailable")
   if key not in seen:rows.append(row);seen.add(key)
  if len(data)<limit:complete=True;break
 return {"records":rows,"pagesFetched":pages,"boundedComplete":complete}
def all_protections():
 conditional=fetch_pages("/capi/v3/openAlgoOrders?limit={limit}&page={page}",start=1)
 trailing=fetch_pages("/capi/v3/trailing/openOrders?limit={limit}&page={page}",start=0)
 return {"conditional":conditional,"trailing":trailing,"allComplete":conditional["boundedComplete"] and trailing["boundedComplete"]}
if __name__=="__main__":
 x=all_protections()
 print("conditional",len(x["conditional"]["records"]),"trailing",len(x["trailing"]["records"]),"complete",x["allComplete"])
