import json
from weex_api_budget import budget
print(json.dumps(budget().used()))
