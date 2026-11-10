from monitor import query
d=query("/capi/v3/account/accountConfig")
print("canTrade",d.get("canTrade"),"dualSidePosition",d.get("dualSidePosition"))
