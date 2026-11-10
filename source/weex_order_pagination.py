"""Read-only paginated WEEX history, with bounds and de-duplication."""
from monitor import query
def history(max_pages=5,limit=100):
 if max_pages<1 or max_pages>20 or limit<1 or limit>100:raise ValueError("bounds")
 seen={};pages=0
 for page in range(max_pages):
  data=query(f"/capi/v3/order/history?limit={limit}&page={page}")
  if not isinstance(data,list):raise ValueError("Unexpected history response")
  pages+=1
  for row in data:
   ident=str(row.get("orderId",""))
   if ident:seen[ident]=row
  if len(data)<limit:break
 return {"pagesFetched":pages,"orders":list(seen.values()),"completeWithinRequestedBounds":pages<max_pages}
if __name__=="__main__":
 r=history()
 print("pages",r["pagesFetched"],"unique",len(r["orders"]),"boundedComplete",r["completeWithinRequestedBounds"])
