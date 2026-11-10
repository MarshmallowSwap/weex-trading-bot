from weex_contract_sdk import Contract


client = Contract.from_env()
ws_api = client.websocket_api
ws_api.connect()
ws_api.subscribe_orders()
print(ws_api.receive())
ws_api.close()
