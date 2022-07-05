import asyncio

from binance import ThreadedWebsocketManager
from binance.exceptions import BinanceAPIException
from strategy_tester.telegram_bot import internet
import time


class ThreadedWebsocketManager(ThreadedWebsocketManager):
    async def start_listener(self, socket, path: str, callback):
        async with socket as s:
            while self._socket_running[path]:
                try:
                    msg = await asyncio.wait_for(s.recv(), 5)
                except asyncio.TimeoutError as e:
                    msg = {"stream": "error", "data":{'e':'connection error'}, "error_msg": "timeout error"}
                except BinanceAPIException as e:
                    msg = {"stream": "error", "data":{'e':"stream live error"}, "error_msg": e.message}
                    
                if msg["stream"] == "error":
                    connected = internet()
                    # Time UTC
                    # _time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
                    msg["connected_check"] = connected
                    # msg["time_check"] = _time
                    
                if not msg:
                    continue
                callback(msg)
        del self._socket_running[path]
