from weex_spot_sdk import Spot


client = Spot.from_env()
response = client.rest_api.execute_operation(
    "getDepth",
    {"query": {"symbol": "BTCUSDT", "limit": 15}},
)
print(response.status_code)
print(response.data)
