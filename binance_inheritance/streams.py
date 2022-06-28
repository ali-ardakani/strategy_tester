from binance import ThreadedWebsocketManager
import asyncio

class ThreadedWebsocketManager(ThreadedWebsocketManager):
    async def start_listener(self, socket, path: str, callback):
        async with socket as s:
            while self._socket_running[path]:
                try:
                    msg = await asyncio.wait_for(s.recv(), 3)
                except asyncio.TimeoutError:
                    msg = {"data":{'e':'connection error'}}

                if not msg:
                    continue
                callback(msg)
        del self._socket_running[path]