from binance import Client
from typing import Dict, Optional
import pandas as pd
import datetime as dt
import numpy as np
import time
import websockets
import json
import pandas as pd
from binance import ThreadedWebsocketManager
from binance.exceptions import BinanceAPIException
import re
from strategy_tester.models import Trade
from strategy_tester.commands import CalculatorTrade
from .strategy import Strategy
import math

class User(Client, Strategy):

    def __init__(strategy, api_key: str, api_secret: str, symbol: str, interval: str,
        requests_params: Optional[Dict[str, str]] = None, tld: str = 'com',
        testnet: bool = False, data: Optional[pd.DataFrame] = None
        ):
        super(Client, strategy).__init__(api_key, api_secret, requests_params, tld, testnet)
        strategy.threaded_websocket_manager = ThreadedWebsocketManager(api_key, api_secret)
        
        # Start the thread's activity.
        strategy.threaded_websocket_manager.start()
        
        # Create a tmp dataframe for add kline websocket data
        # In order to receive the data correctly 
        # and not to interrupt their time(the final candle in the get_historical_klines is not closed)
        # , the variable is create to run the websocket at the same time by the get_historical_klines
        # and replacing them.
        # Prevent this operation by closing the final websocket candles with the get_historical_klines.
        strategy.tmp_data = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "close_time"])
        
        strategy.interval = interval
        strategy.symbol = symbol
        strategy.data = strategy._validate_data(data)

        strategy.current_candle = None
        strategy._open_positions = []
        strategy._closed_positions = []
        strategy._in_bot = False # 
        strategy.start_trade = False

        strategy.counter__ = 0
        
    @property
    def free_usdt(strategy):
        """
        Get free USDT
        """
        usdt = next(item for item in strategy.futures_account_balance() if item["asset"] == "USDT")
        return float(usdt['withdrawAvailable'])
    
    @property
    def locked_usdt(strategy):
        """
        Get locked USDT
        """
        return strategy.get_asset_balance(asset="USDT")["locked"]
    
    @property
    def free_btc(strategy):
        """
        Get free BTC
        """
        btc = next(item for item in strategy.futures_account_balance() if item["asset"] == "BTC")
        return float(btc["withdrawAvailable"])
    
    @property
    def locked_btc(strategy):
        """
        Get locked BTC
        """
        return strategy.get_asset_balance(asset="BTC")["locked"]
    
    @property
    def open_positions(strategy):
        if strategy._in_bot:
            return strategy._open_positions
        else:
            open_positions = strategy.futures_position_information(symbol="BTCUSDT")
            strategy._in_bot = True
            if open_positions[0]:
                if float(open_positions[0]["positionAmt"]) == 0:
                    return []
            for position in open_positions:
                trade = Trade(
                    type="long" if position["positionAmt"][0] != "-" else "short",
                          entry_date=position["updateTime"],
                          entry_price=float(position["entryPrice"]),
                          entry_signal="long" if position["positionAmt"][0] != "-" else "short",
                          contract=abs(float(position["positionAmt"])),
                          comment="This is the first trade after restart bot.")
                strategy._open_positions.append(trade)
            return strategy._open_positions
                
    def _get_remind_kline(strategy, kline: pd.DataFrame=None):
        """
        Get remind kline data
        """
        if kline: # Get remind kline data
            last_kline = kline.iloc[-1]
            remind_kline = pd.DataFrame(strategy.get_historical_klines(strategy.symbol, strategy.interval, last_kline["close_time"])).iloc[:, :7]
        else: # Get 5000 kline data
            num, period = re.match(r"([0-9]+)([a-z]+)", strategy.interval, re.I).groups()
            # Get <num> kline data ago
            num = 1500 * int(num)
            remind_kline = pd.DataFrame(strategy.get_historical_klines(strategy.symbol, strategy.interval, start_str=f"{num}{period} ago UTC")).iloc[:, :7]
            
        remind_kline.columns = ["date", "open", "high", "low", "close", "volume", "close_time"]
        remind_kline.index = remind_kline["date"]
        remind_kline = remind_kline.astype(float)
        
        return remind_kline
        
        
    def _validate_data(strategy, data: Optional[pd.DataFrame]) -> pd.DataFrame:
        """
        Check columns and index of dataframe and Add new data to dataframe
        """
        if data:
            if not isinstance(data, pd.DataFrame):
                raise TypeError("The data must be a pandas DataFrame.")

            if data.empty:
                raise ValueError("The data is empty.")

            required_columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'close_time']
            
            wrong_columns = [
                column for column in required_columns if column not in data.columns.to_list()
            ]
            if wrong_columns:
                raise ValueError(
                    "The data must have the columns: {}".format(wrong_columns))
                
            # Check type of the date and close_time
            if np.issubdtype(data["date"], np.datetime64):
                data["date"] = data["date"].astype(np.int64)/10**6
            if np.issubdtype(data['close_time'], np.datetime64):
                data['close_time'] = data['close_time'].astype(np.int64)/10**6
                     
        # while True:
        #     try:
        #         # Start the websocket
        strategy.stream = strategy.threaded_websocket_manager.start_kline_socket(strategy._human_readable_kline, strategy.symbol, strategy.interval)
            #     break
            # except AttributeError:
            #     print("We had a problem configuring the websocket, another attempt will be made in 2 seconds.")
            #     time.sleep(2)
        # try:
        #     # Start the websocket
        #     strategy.stream = strategy.start_kline_socket(strategy._human_readable_kline, strategy.symbol, strategy.interval)
        # except AttributeError:
        #     print("We had a problem configuring the websocket, another attempt will be made in 2 seconds.")
        #     time.sleep(2)
        
        # Get remind kline data
        data = strategy._get_remind_kline(data)
        print(len(data))

        return data
    
    def _combine_data(strategy):
        """Add last websocket data to main data"""
        
        
        last_kline_data = strategy.data.iloc[-1] # Last candle in the historical kline
        
        if not strategy.tmp_data[strategy.tmp_data.date==last_kline_data.date].empty: # If the last candle in the historical kline is in the websocket data
            strategy.data.iloc[-1] = strategy.tmp_data[strategy.tmp_data.date==last_kline_data.date].iloc[0] # Replace the last candle in the historical kline with the websocket data
        strategy.data = pd.concat([strategy.data, strategy.tmp_data[strategy.tmp_data.date>last_kline_data.date]]).iloc[1:] # Add the websocket data to the historical kline
        
    
    def _human_readable_kline(strategy, msg:dict):
        """
        Convert kline data to pandas dataframe
        """
        if msg["k"]["x"]:
            frame = pd.DataFrame([msg['k']])
            frame = frame.filter(['t', 'T', 'o', 'c', 'h', 'l', 'v'])
            frame.columns = ['date', 'close_time', 'open', 'close', 'high', 'low', 'volume']
            frame.index = frame['date']
            frame = frame.astype(float)
            strategy.tmp_data = pd.concat([strategy.tmp_data, frame], axis=0)
            while strategy.data.empty:
                pass
            strategy._combine_data()
            strategy.high = strategy.data.high
            strategy.low = strategy.data.low
            strategy.open = strategy.data.open
            strategy.close = strategy.data.close
            strategy.volume = strategy.data.volume
            if strategy.start_trade:
                strategy._init_indicator()
                strategy.indicators()
                strategy.start()
                strategy.condition()
                strategy.conditions.apply(strategy.trade, axis=1)
            
    def entry(strategy,
              signal: str,
              direction: str,
              percent_of_assets: float=1,
              limit: float = None,
              stop: float = None,
              comment: str = None):
        """
        Open a new position.
        
        Parameters
        ----------
        signal : str
            The signal to open the position.
        direction : str
            The direction of the signal.
        percent_of_assets : float
            The percent of the assets to open the position.
        limit : float
            The limit price of the position.
        stop : float
            The stop price of the position.
        comment : str
            The comment of the position.
        """
        current_candle = strategy.data.loc[strategy.current_candle]
        if strategy.start_trade and strategy.data.date.iloc[-1] == current_candle["date"]:
            print("start")
            print(strategy.open_positions)
            if strategy.open_positions == []:
                quantity = float(str(strategy.free_usdt * percent_of_assets * 0.99 / current_candle["close"])[:4])
                print(quantity)
                if direction == "long":
                    side = "BUY"
                elif direction == "short":
                    side = "SELL"
                
                # try:
                strategy.futures_create_order(symbol=strategy.symbol, side=side, type='MARKET', quantity=quantity,
                                        newOrderRespType='RESULT')
                trade = Trade(type=direction,
                        entry_date=current_candle.close,
                        entry_price=current_candle.close,
                        entry_signal=direction,
                        contract=quantity,
                        comment=comment)
                print(f"Open Position with {trade.type} {trade.contract} contracts at {trade.entry_price}")
                strategy._open_positions.append(trade)
                # except BinanceAPIException as e:
                #     pass
            
    def exit(strategy,
             from_entry: str,
             signal: str = None,
             qty: float = 1,
             limit: float = None,
             stop: float = None,
             comment: str = None):
        """
        Close an open position.
        
        Parameters
        ----------
        from_entry : str
            The signal to close the position.
        signal : str
            The signal to close the position.
        qty : float
            The quantity of the position to close.
        limit : float
            The limit price of the position.
        stop : float
            The stop price of the position.
        comment : str
            The comment of the position.
        """
        current_candle = strategy.data.loc[strategy.current_candle]
        if strategy.start_trade and strategy.data.date.iloc[-1] == current_candle["date"]:
            open_position = [position for position in strategy.open_positions if position.entry_signal == from_entry]
            for position in open_position:
                if position.type == "long":
                    side = "SELL"
                elif position.type == "short":
                    side = "BUY"
                # try:
                # Calculate parameters such as profit, draw down, etc.
                data_trade = strategy.data.loc[strategy.data.date.between(
                    position.entry_date, current_candle.close_time)]
                quantity = position.contract * qty
                strategy.futures_create_order(symbol=strategy.symbol, side=side, type='MARKET', quantity=quantity,
                                        newOrderRespType='RESULT')
                position.exit_date = current_candle.close_time
                position.exit_price = current_candle.close
                print(f"Closing position with {position.type} {position.contract} contracts at {position.exit_price}")
                position.exit_signal = signal
                CalculatorTrade(position, data_trade)
                strategy._open_positions.remove(position)
                strategy._closed_positions.append(position)
                # except BinanceAPIException as e:
                #     pass
            
    def _current_candle_calc(strategy):
        """
        Calculate the current candle for the strategy.
        """
        
        current_candle = strategy.data.iloc[-1]
        return current_candle

    def round_down(strategy, x, base=5):
        """ Round down to the nearest 'base' """
        return int(base * math.floor(float(x)/base))
        
    def run(strategy):
        """Run the strategy."""
        strategy.start_trade = True