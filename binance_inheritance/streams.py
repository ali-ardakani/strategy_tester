from binance import ThreadedWebsocketManager
from binance.exceptions import BinanceAPIException
import asyncio

class ThreadedWebsocketManager(ThreadedWebsocketManager):
    async def start_listener(self, socket, path: str, callback):
        async with socket as s:
            while self._socket_running[path]:
                try:
                    msg = await asyncio.wait_for(s.recv(), 3)
                except asyncio.TimeoutError:
                    msg = {"stream": "error", "data":{'e':'connection error'}}
                except BinanceAPIException:
                    msg = {"stream": "error", "data":{'e':"stream live error"}}

                if not msg:
                    continue
                callback(msg)
        del self._socket_running[path]