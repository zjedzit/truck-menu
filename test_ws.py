import asyncio
import websockets

async def main():
    try:
        async with websockets.connect("ws://127.0.0.1:8080/ws?device_key=foo") as ws:
            print("Connected!")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
