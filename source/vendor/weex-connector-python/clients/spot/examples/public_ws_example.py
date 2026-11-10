from weex_spot_sdk import Spot


client = Spot.from_env()
streams = client.websocket_streams
streams.connect()
streams.subscribe_ticker("BTCUSDT")
print(streams.receive())
streams.close()
