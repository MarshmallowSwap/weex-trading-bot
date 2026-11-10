from weex_contract_sdk import Contract


client = Contract.from_env()
response = client.rest_api.execute_operation(
    "get_capi_v3_market_depth",
    {"query": {"symbol": "BTCUSDT", "limit": 15}},
)
print(response.status_code)
print(response.data)
