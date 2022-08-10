import asyncio
import json
from threading import Thread
from typing import Callable

import websockets as ws
from binance import ThreadedWebsocketManager
from binance.client import Client
from typing import Optional, List, Dict, Callable, Any

from binance.exceptions import BinanceAPIException
from strategy_tester.telegram_bot import internet


class ThreadedWebsocketManager(ThreadedWebsocketManager):
    _count = 0
        
    async def start_listener(self, socket, path: str, callback):
        async with socket as s:
            while self._socket_running[path]:
                try:
                    msg = await asyncio.wait_for(s.recv(), 5)
                    self._count = 0
                except asyncio.TimeoutError as e:
                    self._count += 1
                    if self._count > 5:
                        msg = {
                            "stream": "error",
                            "data": {
                                'e': 'connection error'
                                },
                            "error_msg": "timeout error"
                            }
                    else:
                        continue
                except BinanceAPIException as e:
                    msg = {
                        "stream": "error",
                        "data": {
                            'e': "stream live error"
                            },
                        "error_msg": e.message
                        }
                if msg["stream"] == "error":
                    connected = internet()
                    msg["connected_check"] = connected

                if not msg:
                    continue
                callback(msg)
        del self._socket_running[path]
        
    def _reconnect(self, socket, path):
        self._socket_running[path] = False
        socket.close()
        socket = ws.connect(path)
        self._socket_running[path] = True
        return socket

    def futures_start_user_socket(self, callback) -> str:
        url = "wss://fstream.binance.com/ws/"
        return self._start_async_socket(
            callback=callback,
            socket_name='futures_user_socket',
            params={}
        )

        
class StreamUserData(Thread):
    """
    Instant access to account changes in futures.

    Description:
        This endpoint is used to receive realtime updates on account changes.

    Parameters
    ----------
    api_key : str
        Binance API Key.
    api_secret : str
        Binance API Secret.
    callback : callable
        Callback function to handle the data.
    timeout : int
        Timeout for the websocket(default=5).
    """

    BASEPATH = "wss://fstream.binance.com/ws/"

    def __init__(self,
                 api_key: str,
                 api_secret: str,
                 callback: Callable,
                 timeout: int = 3):

        self.api_key = api_key
        self.api_secret = api_secret

        self.callback = self._validate_callback(callback)
        self.timeout = float(timeout)

        self.client = Client(api_key, api_secret)
        
        self._listen_key = self.client.futures_stream_get_listen_key()
        self.client.futures_stream_keepalive(self._listen_key)
        
        self._path = self.BASEPATH + self._listen_key
        
        self.loop = asyncio.new_event_loop()
        super().__init__(target=self._start)

    async def _start_websocket(self):
        """ Start websocket connection. """
        async with ws.connect(self._path) as websocket:
            while True:
                try:
                    msg = await asyncio.wait_for(websocket.recv(), self.timeout)
                    if message:
                        message = json.loads(message)
                        if message["e"] == "listenKeyExpired":
                            self._listen_key = self.client.futures_stream_get_listen_key()
                            message = await websocket.recv()
                            message = json.loads(message)
                        msg = {
                            "stream": "user",
                            "data": message
                        }
                        self.callback(msg)
                    else:
                        continue
                except Exception as e:
                    if e.__class__ == BinanceAPIException:
                        message = e.message
                    elif e.__class__ == asyncio.TimeoutError:
                        message = "Timeout error"
                    else:
                        message = e
                    msg = {
                        "stream": "error",
                        "data": {
                            'e': "stream live error"
                        },
                        "error_msg": message
                    }
                    self.callback(msg)
    
    def _start(self):
        """
        Start streaming.
        """
        self.loop.call_soon_threadsafe(asyncio.create_task, self.keep_alive())
        self.loop.call_soon_threadsafe(asyncio.create_task,
                                       self._start_websocket())
        self.loop.run_forever()

    async def keep_alive(self):
        """
        Keep the connection alive.

        Description:
            This endpoint is running in the background every 55 minutes.
        """
        while True:
            try:
                await asyncio.create_task(self._keepalive_listen_key())
            except Exception as e:
                msg = {
                    "stream": "error",
                    "data": {
                        'e': "stream live error"
                    },
                    "error_msg": f"\n{e}"
                }
                self.callback(msg)
            await asyncio.sleep(3 * 60)
            
    async def _keepalive_listen_key(self):
        """
        Get listen key.
        """
        print("keep alive")
        self.client.futures_stream_keepalive(self._listen_key)

    def _validate_callback(self, callback: Callable):
        """
        Validate callback function.
        """
        if not callable(callback):
            raise ValueError("Callback must be a callable function.")
        return callback