from binance import Client
from typing import Dict, Optional
import pandas as pd
import numpy as np
import pandas as pd
from binance import ThreadedWebsocketManager
from binance.exceptions import BinanceAPIException
import re
from strategy_tester.models import Trade
from strategy_tester.commands import CalculatorTrade
from .strategy import Strategy
import math
import plotly.graph_objects as go
import io

class User(Client, Strategy):
    
    _user = True
    _exit = False
    _entry = False
    
    def __init__(strategy, 
                api_key: str, 
                api_secret: str, 
                primary_pair: str,
                secondary_pair: str,
                interval: str,
                leverage: int,
                margin_type: str,
                requests_params: Optional[Dict[str, str]] = None, 
                tld: str = 'com',
                testnet: bool = False, 
                data: Optional[pd.DataFrame] = None,
                telegram_bot = None,
                **kwargs):
        super(Client, strategy).__init__(api_key, api_secret, requests_params, tld, testnet)
        strategy.primary_pair, strategy.secondary_pair = strategy._validate_pair(primary_pair, secondary_pair)
        strategy.threaded_websocket_manager = ThreadedWebsocketManager(api_key, api_secret)
        
        strategy.current_candle = None
        strategy._open_positions = []
        strategy._closed_positions = []
        strategy._in_bot = False # 
        strategy.start_trade = False
        
        strategy.telegram_bot = telegram_bot
        
        if strategy.open_positions != []:
            strategy.telegram_bot.send_message_to_channel(f"{strategy.primary_pair}{strategy.secondary_pair} has open positions.")
            
        strategy.leverage = strategy._set_leverage(leverage)
        strategy.margin_type = strategy._set_margin_type(margin_type)
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
        strategy.data = strategy._validate_data(data)

        strategy.counter__ = 0
    @property
    def free_primary(strategy):
        """
        Get free primary pair
        """
        primary = next(item for item in strategy.futures_account_balance() if item["asset"] == strategy.primary_pair)
        primary = float(primary['withdrawAvailable'])
        return primary
    
    @property
    def locked_primary(strategy):
        """
        Get locked primary pair
        """
        return strategy.get_asset_balance(asset=strategy.primary_pair)["locked"]
    
    @property
    def free_secondary(strategy):
        """
        Get free secondary pair
        """
        secondary = next(item for item in strategy.futures_account_balance() if item["asset"] == strategy.secondary_pair)
        secondary = float(secondary["withdrawAvailable"])
        # Set a price of less than $ 1,000
        if secondary > 30:
            secondary = 30
        else:
            secondary = secondary
        return secondary
    
    @property
    def locked_secondary(strategy):
        """
        Get locked secondary pair
        """
        return strategy.get_asset_balance(asset=strategy.secondary_pair)["locked"]
    
    @property
    def open_positions(strategy):
        if strategy._in_bot:
            return strategy._open_positions
        else:
            open_positions = strategy.futures_position_information(symbol=strategy.symbol)
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
                     
        strategy.stream = strategy.threaded_websocket_manager.start_kline_socket(strategy._human_readable_kline, strategy.symbol, strategy.interval)
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
        if strategy._entry:
            current_candle = strategy.data.loc[strategy.current_candle]
            if strategy.start_trade and strategy.data.date.iloc[-1] == current_candle["date"]:
                # If there is no open position, then open position (Only used for having 1 open position at the same time)
                if strategy.open_positions == []:
                    quantity = float(str(strategy.free_secondary * percent_of_assets * 0.997 / current_candle["close"])[:5])
                    print(strategy.free_secondary * percent_of_assets * 0.997 / current_candle["close"])
                    if direction == "long":
                        side = "BUY"
                    elif direction == "short":
                        side = "SELL"
                    
                    try:
                        strategy.futures_create_order(symbol=strategy.symbol, side=side, type='MARKET', quantity=quantity, newOrderRespType='RESULT')
                        
                        entry_date_datetime = pd.to_datetime(current_candle.close_time, unit="ms").round("1s")                                       
                        trade = Trade(type=direction,
                                entry_date=entry_date_datetime.timestamp()*1000,
                                entry_price=current_candle.close,
                                entry_signal=signal,
                                contract=quantity,
                                comment=comment)
                        
                        if strategy.telegram_bot:
                            plot = strategy._plot_to_channel(trade)
                            strategy.telegram_bot.send_image_to_channel(plot, caption=f"#Open#{direction}#{signal}\n\n\nOpen {direction} in {entry_date_datetime}\n\nOpen Price: {current_candle.close}\nContract: {quantity}\nComment: {comment}")
                        print(f"Open Position with {trade.type} {trade.contract} contracts at {trade.entry_price}")
                        strategy._open_positions.append(trade)
                    except BinanceAPIException as e:
                        if strategy.telegram_bot:
                            strategy.telegram_bot.send_message_to_channel(f"Error in Open Position\n\nSymbol: {strategy.symbol}\nSide: {side}\nQuantity: {quantity}\n Entry Price: {current_candle['close']}\nError: {e}")
                        print(f"Error in Open Position\n\nSymbol: {strategy.symbol}\nSide: {side}\nQuantity: {quantity}\n Entry Price: {current_candle['close']}\nError: {e}")
            
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
        if strategy._exit:
            current_candle = strategy.data.loc[strategy.current_candle]
            if strategy.start_trade and strategy.data.date.iloc[-1] == current_candle["date"]:
                open_position = [position for position in strategy.open_positions if position.entry_signal == from_entry]
                for position in open_position:
                    if position.type == "long":
                        side = "SELL"
                    elif position.type == "short":
                        side = "BUY"
                    try:
                        # Calculate parameters such as profit, draw down, etc.
                        data_trade = strategy.data.loc[strategy.data.date.between(
                            position.entry_date, current_candle.close_time)]
                        quantity = position.contract * qty
                        strategy.futures_create_order(symbol=strategy.symbol, side=side, type='MARKET', quantity=quantity,
                                                newOrderRespType='RESULT')
                        exit_date_datetime = pd.to_datetime(current_candle.close_time, unit="ms").round("1s")
                        position.exit_date = exit_date_datetime.timestamp()*1000
                        position.exit_price = current_candle.close
                        position.exit_signal = signal
                        CalculatorTrade(position, data_trade)
                        if strategy.telegram_bot:
                            plot = strategy._plot_to_channel(position)
                            strategy.telegram_bot.send_image_to_channel(plot, caption=f"#Close#{position.type}#{signal}\n\n\nClose {position.type} in {exit_date_datetime}\n\nClose Price: {current_candle.close}\nContract: {position.contract}\nComment: {comment}\nProfit: {position.profit}\nProfit Percent: {position.profit_percent}\nDraw Down: {position.draw_down}\nEntry Price: {position.entry_price}\nEntry Signal: {position.entry_signal}\nEntry Date: {position.entry_date}\n\nExit Price: {position.exit_price}\nExit Signal: {position.exit_signal}\nExit Date: {position.exit_date}")
                            # strategy.telegram_bot.send_image_to_channel(strategy._plot_to_channel(position))

                        print(f"Closing position with {position.type} {position.contract} contracts at {position.exit_price}")
                        strategy._open_positions.remove(position)
                        strategy._closed_positions.append(position)
                    except BinanceAPIException as e:
                        if strategy.telegram_bot:
                            strategy.telegram_bot.send_message_to_channel(f"Error in Close Position\n\nSymbol: {strategy.symbol}\nSide: {side}\nQuantity: {quantity}\n Entry Price: {position.entry_price}\n Exit Price: {current_candle['close']}\nError: {e}")
                        print(f"Error in Close Position\n\nSymbol: {strategy.symbol}\nSide: {side}\nQuantity: {quantity}\n Entry Price: {position.entry_price}\n Exit Price: {current_candle['close']}\nError: {e}")
                
    def close_positions(strategy):
        """
        Close all open positions.
        """
        print(strategy.open_positions)
        for position in strategy.open_positions:
            print(position.entry_signal)
            strategy.exit(from_entry=position.entry_signal)
            
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
        
    def set_data(self, data):
        """This function used in Strategy class but in User class should not do anything."""
        pass
    
    def _validate_pair(strategy, primary, secondary):
        """
        Validate the pair of the strategy.
        
        Parameters
        ----------
        primary : str
            The primary pair of the strategy.
        secondary : str
            The secondary pair of the strategy.
        """
        primary = primary.upper()
        secondary = secondary.upper()
        symbol = primary + secondary
        list_of_symbols = strategy.get_exchange_info()["symbols"]
        try:
            next(item for item in list_of_symbols if item["symbol"] == symbol)
            strategy.symbol = symbol
            return primary, secondary
        except StopIteration:
            raise ValueError(f"The pair {symbol} is not supported.({primary=}, {secondary=})")
        
    @staticmethod
    def _plot(candles:pd.DataFrame, entry_date: int or pd.Timestamp=None, exit_date: int or pd.Timestamp=None, type_: str=None):
        """Plot the candles."""
        if not type_:
            type_ = "candle"
        if type_ == "candle":
            entry_color = "blue"
            exit_color = "blue"
            y_entry= candles.close.iloc[0]
            y_exit = candles.close.iloc[-1]
        elif type_ == "long":
            entry_color = "green"
            exit_color = "red"
            y_entry = candles.loc[entry_date, "high"]
            y_exit = candles.loc[exit_date, "low"]
        else:
            entry_color = "red"
            exit_color = "green"
            y_entry = candles.loc[entry_date, "low"]
            y_exit = candles[exit_date, "high"]
            
        chart = go.Candlestick(x=candles.index,
                            open=candles.open,
                            high=candles.high,
                            low=candles.low,
                            close=candles.close)
        
        entry_arrow = go.Scatter(x=[entry_date],
                                 y=[y_entry],
                                 mode="markers",
                                 marker=dict(color=entry_color, size=10))
        if exit_date is None:
            exit_date = entry_date
            
        exit_arrow = go.Scatter(x=[exit_date],
                                y=[y_exit],
                                mode="markers",
                                marker=dict(color=exit_color, size=10))
        data = [chart, entry_arrow, exit_arrow]
        layout = go.Layout(title=type_,
                           xaxis=dict(title="Date"),
                           yaxis=dict(title="Price"))
        fig = go.Figure(data=data, layout=layout)
        
        # Create a binary image to send to channel
        img_byte = io.BytesIO()
        fig.write_image(img_byte, format="png")
        img_byte.seek(0)
        return img_byte
        
    def _plot_to_channel(strategy, trade: Trade):
        data = strategy.data.reset_index(drop=True)
        start_date = trade.entry_date
        end_date = trade.exit_date

        if end_date is None:
            data = data.tail(100)
        else:
            start_trade = data[(data.date >= start_date)].iloc[0].name -50 if start_date else 0
            end_trade = data[(data.date >= end_date)].iloc[0].name+1
            data = data.iloc[start_trade:end_trade]
        data.index = data.date
        return strategy._plot(data, entry_date=start_date, exit_date=end_date, type_=trade.type)
    
    def _set_leverage(strategy, leverage: int):
        """
        Set the leverage of the strategy.
        
        Parameters
        ----------
        leverage : int
            The leverage of the strategy.
        """
        if leverage < 1:
            if strategy.telegram_bot:
                strategy.telegram_bot.send_message_to_channel(f"Leverage must be greater than 1.\n\nLeverage: {leverage}")
            raise ValueError("Leverage must be greater than 1.")
        try:
            strategy.futures_change_leverage(symbol=strategy.symbol, leverage=leverage)
            strategy.telegram_bot.send_message_to_channel(f"Leverage changed to {leverage}")
            return leverage
        except BinanceAPIException as e:
            if strategy.telegram_bot:
                strategy.telegram_bot.send_message_to_channel(f"Error in Set Leverage\n\nLeverage: {leverage}\nError: {e}")
            raise e
        
    def _set_margin_type(strategy, margin_type: str):
        """
        Set the margin type of the strategy.
        
        Parameters
        ----------
        margin_type : str
            The margin type of the strategy.
        """
        margin_type = margin_type.upper()
        if margin_type not in ["ISOLATED", "CROSSED"]:
            if strategy.telegram_bot:
                strategy.telegram_bot.send_message_to_channel(f"Margin type must be either isolated or crossed.\n\nMargin Type: {margin_type}")
            raise ValueError("Margin type must be either isolated or crossed.")
        try:
            strategy.futures_change_margin_type(symbol=strategy.symbol, marginType=margin_type)
            strategy.telegram_bot.send_message_to_channel(f"Margin type changed to {margin_type}")
            return margin_type
        except BinanceAPIException as e:
            if strategy.telegram_bot:
                if e.message == "No need to change margin type.":
                    strategy.telegram_bot.send_message_to_channel(f"Margin type is already {margin_type}")
                    return margin_type
                else:
                    strategy.telegram_bot.send_message_to_channel(f"Error in Set Margin Type\n\nMargin Type: {margin_type}\nError: {e}")
                raise e
            