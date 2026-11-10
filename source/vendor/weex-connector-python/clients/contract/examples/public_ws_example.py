from weex_contract_sdk import Contract


client = Contract.from_env()
streams = client.websocket_streams
streams.connect()
streams.subscribe_ticker("BTCUSDT")
print(streams.receive())
streams.close()
