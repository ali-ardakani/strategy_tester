from datetime import datetime
import io
import math
import random
import re
from time import time
from typing import Dict, Optional
from copy import deepcopy

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from binance import Client
from binance.exceptions import BinanceAPIException

from strategy_tester.binance_inheritance import (ThreadedWebsocketManager,
                                                 StreamUserData)
from strategy_tester.commands import CalculatorTrade
from strategy_tester.decorator import validate_float
from strategy_tester.models import Trade
from strategy_tester.strategy import Strategy


class User(Client, Strategy):

    _user = True
    _exit = False
    _entry = False
    _permission_long = True
    _permission_short = True

    _current_kline = None

    def __init__(strategy,
                 api_key: str,
                 api_secret: str,
                 primary_pair: str,
                 secondary_pair: str,
                 interval: str,
                 leverage: int,
                 margin_type: str,
                 min_usd: float = 25,
                 max_usd: float = 100,
                 chunk: bool = False,
                 custom_amount_cash: float = None,
                 keep_time_limit_chunk: float = None,
                 percent_sl: float = None,
                 requests_params: Optional[Dict[str, str]] = None,
                 tld: str = 'com',
                 testnet: bool = False,
                 data: Optional[pd.DataFrame] = None,
                 telegram_bot=None,
                 **kwargs):
        super(Client, strategy).__init__(api_key, api_secret, requests_params,
                                         tld, testnet)
        strategy.primary_pair, strategy.secondary_pair = \
            strategy._validate_pair(primary_pair, secondary_pair)
        strategy.threaded_websocket_manager_spot = \
            ThreadedWebsocketManager(api_key, api_secret)
        # strategy.stream_user_data = StreamUserData(
        #     api_key=api_key,
        #     api_secret=api_secret,
        #     callback=strategy.__stream_live_account)
        # strategy.stream_user_data.start()
        strategy.current_candle = None
        strategy._open_positions = []
        strategy._closed_positions = []
        strategy._limit_chunk = []
        strategy._in_bot = False
        strategy.start_trade = False
        strategy.connection_internet = True
        strategy.telegram_bot = telegram_bot
        strategy.min_usd = min_usd
        strategy.max_usd = max_usd
        strategy.chunk = chunk
        if strategy.open_positions != []:
            msg = f"{strategy.primary_pair}{strategy.secondary_pair}"\
                " has open positions."
            strategy._send_message(msg)
        strategy.interval = interval
        strategy.percent_sl = percent_sl
        strategy.leverage = strategy._set_leverage(leverage)
        strategy.margin_type = strategy._set_margin_type(margin_type)
        strategy.custom_amount_cash = custom_amount_cash \
            if custom_amount_cash is None else \
            strategy.\
            _validate_custom_amount_cash(custom_amount_cash)
        strategy.keep_time_limit_chunk = strategy.\
            _validate_keep_time_limit_chunk(keep_time_limit_chunk)
        # Start the thread's activity.
        strategy.threaded_websocket_manager_spot.start()
        # Create a tmp dataframe for add kline websocket data
        # In order to receive the data correctly
        # and not to interrupt their time
        # (the final candle in the get_historical_klines is not closed)
        # , the variable is create
        # to run the websocket at the same time by the get_historical_klines
        # and replacing them.
        # Prevent this operation by closing
        # the final websocket candles with the get_historical_klines.
        strategy.tmp_data = pd.DataFrame(columns=[
            'date', 'close_time', 'open', 'close', 'high', 'low', 'volume',
            'num_trades'
        ])

        strategy._validate_data(data)

        strategy.counter__ = 0

    @property
    def hlcc4(strategy):
        hlcc = strategy.high + strategy.low + strategy.close + strategy.close
        strategy._hlcc4 = hlcc / 4
        return strategy._hlcc4

    @property
    def free_primary(strategy):
        """
        Get free primary pair
        """
        primary = next(item for item in strategy.futures_account_balance()
                       if item["asset"] == strategy.primary_pair)
        primary = float(primary['withdrawAvailable'])
        return primary

    @property
    def locked_primary(strategy):
        """
        Get locked primary pair
        """
        return strategy.get_asset_balance(
            asset=strategy.primary_pair)["locked"]

    @property
    def free_secondary(strategy):
        """
        Get free secondary pair
        """
        secondary = next(item for item in strategy.futures_account_balance()
                         if item["asset"] == strategy.secondary_pair)
        secondary = float(secondary["withdrawAvailable"])
        # Set a price of less than $ 1,000
        if strategy.custom_amount_cash:
            if secondary > strategy.custom_amount_cash:
                secondary = strategy.custom_amount_cash
            else:
                secondary = secondary
        return secondary

    @property
    def locked_secondary(strategy):
        """
        Get locked secondary pair
        """
        return strategy.get_asset_balance(
            asset=strategy.secondary_pair)["locked"]

    @property
    def open_positions(strategy):
        if strategy._in_bot:
            return strategy._open_positions
        else:
            open_positions = strategy.futures_position_information(
                symbol=strategy.symbol)
            open_orders = [
                order for order in strategy.futures_get_open_orders()
                if order["symbol"] == strategy.symbol
            ]
            strategy._in_bot = True
            if open_positions[0]:
                if float(open_positions[0]["positionAmt"]) == 0:
                    return []
            for position in open_positions:
                trade = Trade(
                    type="long"
                    if position["positionAmt"][0] != "-" else "short",
                    entry_date=position["updateTime"],
                    entry_price=float(position["entryPrice"]),
                    entry_signal="long"
                    if position["positionAmt"][0] != "-" else "short",
                    contract=abs(float(position["positionAmt"])),
                    comment="This is the first trade after restart bot.")
                strategy._open_positions.append(trade)
            for order in open_orders:
                trade = Trade(
                    orderid=order["orderId"],
                    order_type=order["type"],
                    type="long" if order["side"].lower() == "buy" else "short",
                    entry_date=order["time"],
                    entry_price=float(order["price"]),
                    entry_signal="long"
                    if order["side"].lower() == "buy" else "short",
                    contract=abs(float(order["origQty"])),
                    comment="This is the first trade after restart bot.")
                strategy._open_positions.append(trade)
            return strategy._open_positions

    @property
    def current_kline(self):
        return self._current_kline

    @current_kline.setter
    def current_kline(self, kline):
        kline.date = pd.to_datetime(kline.date, unit='ms')
        # Convert dataframe to series
        kline = kline.iloc[0]
        self._current_kline = kline

    @property
    def current_time(self):
        return time() * 1000

    def trade(strategy, row):
        """Execute the trade for the strategy.

        Description
        -----------
        This function is used to execute the trade for the strategy.
        In this function, set the current candle and
        execute the trade_calc function.

        Parameters
        ----------
        row: DataFrame
            The row of the data that you want to execute the trade for.
        """
        print("Last candle: ", strategy.data.iloc[-1].name)
        print("Current candle: ", row.name)
        print("Last Cond: ", strategy._conditions.iloc[-1].name, end="\n\n")
        strategy.current_candle = row.name
        if strategy.percent_sl is not None:
            strategy._sl_onion()

        strategy.trade_calc(row)

    @staticmethod
    @validate_float
    def _validate_custom_amount_cash(custom_amount_cash):
        if custom_amount_cash < 0:
            raise ValueError("The custom amount cash must be greater than 0.")
        else:
            return custom_amount_cash

    def _get_remind_kline(strategy, kline: pd.DataFrame = None):
        """
        Get remind kline data
        """
        if kline:  # Get remind kline data
            last_kline = kline.iloc[-1]
            remind_kline = pd.DataFrame(
                strategy.get_historical_klines(
                    strategy.symbol, strategy.interval,
                    last_kline["close_time"])).iloc[:, :7]
        else:  # Get 5000 kline data
            num, period = re.match(r"([0-9]+)([a-z]+)", strategy.interval,
                                   re.I).groups()
            # Get <num> kline data ago
            num = 3000 * int(num)
            remind_kline = pd.DataFrame(
                strategy.get_historical_klines(
                    strategy.symbol,
                    strategy.interval,
                    start_str=f"{num}{period} ago UTC")).iloc[:, :9]

        remind_kline.columns = [
            "date", "open", "high", "low", "close", "volume", "close_time",
            "quote_asset_volume", "num_trades"
        ]
        remind_kline.index = remind_kline["date"]
        remind_kline.drop(columns=["quote_asset_volume"], inplace=True)
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

            required_columns = [
                'date', 'open', 'high', 'low', 'close', 'volume', 'close_time'
            ]

            wrong_columns = [
                column for column in required_columns
                if column not in data.columns.to_list()
            ]
            if wrong_columns:
                raise ValueError(
                    "The data must have the columns: {}".format(wrong_columns))

            # Check type of the date and close_time
            if np.issubdtype(data["date"], np.datetime64):
                data["date"] = data["date"].astype(np.int64) / 10**6
            if np.issubdtype(data['close_time'], np.datetime64):
                data['close_time'] = data['close_time'].astype(
                    np.int64) / 10**6

        # Get remind kline data
        data = strategy._get_remind_kline(data)
        print(len(data))

        # <symbol>@kline_<interval>
        # strategy.stream = \
        #     strategy.threaded_websocket_manager.start_kline_socket(
        #         strategy._human_readable_kline,
        #         strategy.symbol,
        #         strategy.interval)

        # Run stream live account
        try:
            strategy.listen_key = strategy.futures_stream_get_listen_key()
            strategy.start_listen_key = data.iloc[-1].date
            strategy.stream = strategy.symbol.lower() + "@kline_" + \
                strategy.interval

            strategy.stream_live_account = \
                strategy.threaded_websocket_manager_spot\
                    .start_multiplex_socket(
                        callback=strategy.__stream_live_account,
                        streams=[strategy.stream],
                    )

        except Exception as e:
            strategy._send_error_message(e)

        data.index = data.date
        strategy.data = data
        strategy.open = data.open
        strategy.high = data.high
        strategy.low = data.low
        strategy.close = data.close
        strategy.volume = data.volume
        strategy.last_candle = data.date.iloc[-1]

    def __stream_live_account(strategy, msg: dict):
        """
        Get stream live account

        Description
        -----------
            Send all possible changes if any.
        """
        if msg["data"]["e"] == "connection error":
            if strategy.connection_internet:
                connected = msg["connected_check"]
                error_msg = msg["error_msg"]
                txt = "Disconnected from the internet at \n"\
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"\
                    f"Internet connection is {connected}\n"\
                    f"Error message: {error_msg}"
                strategy._send_message(txt)
                strategy.connection_internet = False
        elif msg["data"]["e"] == "stream live error":
            txt = "Stream live error at \n"\
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            strategy._send_message(txt)
            strategy.threaded_websocket_manager_spot.stop()
            strategy._validate_data(strategy.data)
        else:
            if not strategy.connection_internet:
                strategy.connection_internet = True
                txt = "Connected to the internet at \n"\
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                strategy._send_message(txt)

        if msg["stream"] == strategy.stream:
            strategy._human_readable_kline(msg["data"])
            # Check difference between date of
            # current candle and date of start_listen_key
            # equal or greater than 55 min
            if (msg["data"]["E"] - strategy.start_listen_key) >= 1 * 60 * 1000:
                try:

                    strategy.futures_stream_keepalive(strategy.listen_key)
                    strategy.start_listen_key = msg["data"]["E"]
                except BinanceAPIException as e:
                    if "This listenKey does not exist." in e.message:
                        msg = "Stream live error at \n"\
                            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        strategy._send_message(msg)
                        strategy.threaded_websocket_manager_spot.stop()
                        strategy._validate_data(strategy.data)

        elif msg["data"]["e"] == "listenKeyExpired":
            # Get new listen key and restart stream live account
            try:
                strategy.futures_stream_keepalive(strategy.listen_key)
                strategy.start_listen_key = msg["data"]["E"]
            except BinanceAPIException as e:
                if "This listenKey does not exist." in e.message:
                    msg = "Stream live error at \n"\
                        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    strategy._send_message(msg)
                    strategy.threaded_websocket_manager_spot.stop()
                    strategy._validate_data(strategy.data)
        elif msg["data"]["e"] == "MARGIN_CALL":
            # Convert int time to datetime
            event_time = pd.to_datetime(msg["data"]["E"], unit="ms")
            for position in msg["data"]["p"]:
                symbol = position.get("s", None)
                side = position.get("ps", None)
                contract = position.get("pa", None)
                margin_type = position.get("mt", None)
                # Isolated Wallet(If isolated position)
                isolated_wallet = position.get("iw", None)
                mark_price = position.get("mp", None)
                unrealized_pnl = position.get("up", None)
                message = f"#MARGIN_CALL\n\n"\
                    f"Event time: {event_time}\n"\
                    f"Symbol: {symbol}\n"\
                    f"Side: {side}\n"\
                    f"Contract: {contract}\n"\
                    f"Margin type: {margin_type}\n"\
                    f"Isolated wallet: {isolated_wallet}\n"\
                    f"Mark price: {mark_price}\n"\
                    f"Unrealized PNL: {unrealized_pnl}\n"

                # Send message to channel
                strategy._send_message(message)

        elif msg["data"]["e"] == "ACCOUNT_UPDATE":
            event_time = pd.to_datetime(msg["data"]["E"], unit="ms")
            transaction_time = pd.to_datetime(msg["data"]["T"], unit="ms")
            update = msg["data"]["a"]
            event_reason_type = update["m"]
            for balance in update["B"]:
                asset = balance.get("a", None)
                wallet_balance = balance.get("wb", None)
                cross_wallet_balance = balance.get("cwb", None)
                balance_change = balance.get("c", None)
                message = f"#ACCOUNT_UPDATE\n\n"\
                    f"Event time: {event_time}\n"\
                    f"Transaction time: {transaction_time}\n"\
                    f"Event reason type: {event_reason_type}\n"\
                    f"Asset: {asset}\n"\
                    f"Wallet balance: {wallet_balance}\n"\
                    f"Cross wallet balance: {cross_wallet_balance}\n"\
                    f"Balance change: {balance_change}\n"

                # Send message to channel
                strategy._send_message(message)
            for position in update["P"]:
                symbol = position.get("s", None)
                contract = position.get("pa", None)
                enter_price = position.get("ep", None)
                unrealized_pnl = position.get("up", None)
                margin_type = position.get("mt", None)
                isolated_wallet = position.get("iw", None)
                mark_price = position.get("mp", None)
                message = f"#ACCOUNT_UPDATE\n\n"\
                    f"Event time: {event_time}\n"\
                    f"Symbol: {symbol}\n"\
                    f"Contract: {contract}\n"\
                    f"Enter price: {enter_price}\n"\
                    f"Unrealized PNL: {unrealized_pnl}\n"\
                    f"Margin type: {margin_type}\n"\
                    f"Isolated wallet: {isolated_wallet}\n"\
                    f"Mark price: {mark_price}\n"

                # Send message to channel
                strategy._send_message(message)

        elif msg["data"]["e"] == "ORDER_TRADE_UPDATE":
            event_time = pd.to_datetime(msg["data"]["E"], unit="ms")
            transaction_time = pd.to_datetime(msg["data"]["T"], unit="ms")
            order = msg["data"]["o"]
            symbol = order.get("s", None)
            client_order_id = order.get("c", None)
            side = order.get("S", None)
            position_side = order.get("ps", None)
            order_type = order.get("o", None)
            time_in_force = order.get("f", None)
            original_quantity = order.get("q", None)
            original_price = order.get("p", None)
            average_price = order.get("ap", None)
            stop_price = order.get("sp", None)
            execution_type = order.get("x", None)
            order_status = order.get("X", None)
            order_id = order.get("i", None)
            order_last_filled_qty = order.get("l", None)
            order_filled_accumulated_quantity = order.get("z", None)
            last_filled_price = order.get("L", None)
            commission_asset = order.get("N", None)
            commission = order.get("n", None)
            order_trade_time = pd.to_datetime(order.get("T", None), unit="ms")
            trade_id = order.get("t", None)
            bids_notional = order.get("b", None)
            ask_notional = order.get("a", None)
            maker_side = order.get("m", None)
            reduce_only = order.get("R", None)
            realized_profit = order.get("rp", None)
            message = f"#ORDER_TRADE_UPDATE\n\n"\
                f"Event time: {event_time}\n"\
                f"Transaction time: {transaction_time}\n"\
                f"Symbol: {symbol}\n"\
                f"Client order id: {client_order_id}\n"\
                f"Side: {side}\n"\
                f"Position side: {position_side}\n"\
                f"Order type: {order_type}\n"\
                f"Time in force: {time_in_force}\n"\
                f"Original quantity: {original_quantity}\n"\
                f"Original price: {original_price}\n"\
                f"Average price: {average_price}\n"\
                f"Stop price: {stop_price}\n"\
                f"Execution type: {execution_type}\n"\
                f"Order status: {order_status}\n"\
                f"Order id: {order_id}\n"\
                f"Order last filled quantity: {order_last_filled_qty}\n"\
                f"Order filled accumulated quantity: "\
                f"{order_filled_accumulated_quantity}\n"\
                f"Last filled price: {last_filled_price}\n"\
                f"Commission asset: {commission_asset}\n"\
                f"Commission: {commission}\n"\
                f"Order trade time: {order_trade_time}\n"\
                f"Trade id: {trade_id}\n"\
                f"Bids notional: {bids_notional}\n"\
                f"Ask notional: {ask_notional}\n"\
                f"Maker side: {maker_side}\n"\
                f"Reduce only: {reduce_only}\n"\
                f"Realized profit: {realized_profit}\n"

            # Send message to channel
            strategy._send_message(message)

            strategy._send_message(msg["data"])

        else:
            print(strategy.stream)
            print(msg)

    def _combine_data(strategy, frame: pd.DataFrame):
        """Add last websocket data to main data"""

        frame = frame.filter(strategy.data.columns)
        if frame.date.iloc[0] == strategy.data.iloc[-1].date:
            strategy.data.iloc[-1] = frame.iloc[0].values
        else:
            strategy.data = pd.concat([strategy.data, frame]).iloc[1:]

    def _human_readable_kline(strategy, msg: dict):
        """
        Convert kline data to pandas dataframe
        """
        if strategy.start_trade:
            strategy._convert_expired_orders_limit()
        frame = pd.DataFrame([msg['k']])
        frame = frame.filter(['t', 'T', 'o', 'c', 'h', 'l', 'v', 'n'])
        frame.columns = [
            'date', 'close_time', 'open', 'close', 'high', 'low', 'volume',
            'num_trades'
        ]
        frame.index = frame['date']
        frame = frame.astype(float)

        if msg["k"]["x"]:
            # strategy.tmp_data = pd.concat([strategy.tmp_data, frame], axis=0)
            while strategy.data.empty:
                pass
            strategy._combine_data(frame)
            strategy.high = strategy.data.high
            strategy.low = strategy.data.low
            strategy.open = strategy.data.open
            strategy.close = strategy.data.close
            strategy.volume = strategy.data.volume
            print("Last kline after combine: ", strategy.data.iloc[-1].name)
            print("Last Frame: ", frame.iloc[-1].name)
            if strategy.start_trade:
                try:
                    strategy.set_parameters(**strategy.parameters)
                except Exception as e:
                   strategy._send_error_message(e)
                
                try:
                    strategy._init_indicator()
                except Exception as e:
                    strategy._send_error_message(e)

                try:
                    strategy.indicators()
                except Exception as e:
                    strategy._send_error_message(e)

                try:
                    strategy.start()
                except Exception as e:
                    strategy._send_error_message(e)

                try:
                    strategy.condition()
                except Exception as e:
                    strategy._send_error_message(e)

                try:
                    strategy.conditions.apply(strategy.trade, axis=1)
                except Exception as e:
                    strategy._send_error_message(e)
                    
        strategy.current_kline = frame

    def entry(strategy,
              signal: str,
              direction: str,
              percent_of_assets: float = 1,
              qty: float = None,
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
        if strategy._permission_entry(signal=signal,
                                      direction=direction,
                                      percent_of_assets=percent_of_assets,
                                      limit=limit,
                                      stop=stop,
                                      comment=comment,
                                      current_candle=current_candle):
            # If there is no open position,
            # then open position
            # (Only used for having 1 open position at the same time)
            # if strategy.open_positions == []:
            if qty is None:
                quantity = float(
                    str(strategy.free_secondary * percent_of_assets * 0.999 /
                        current_candle["close"])[:5])
            else:
                quantity = float(str(qty)[:5])
            if direction == "long":
                side = "BUY"
            elif direction == "short":
                side = "SELL"
            if strategy.minQty <= quantity * current_candle["close"]:
                if strategy.keep_time_limit_chunk is not None \
                  and limit is None:

                    entry_price = \
                        strategy.free_secondary * percent_of_assets * 0.999
                    if entry_price >= strategy.max_usd:
                        chunks = strategy.decomposition(entry_price)
                        for chunk in chunks[1:]:
                            chunk = float(
                                str(chunk / current_candle["close"])[:5])
                            multiplier = 0.1 / (len(chunks) - 1)
                            if direction == "short":
                                multiplier = -multiplier
                            _limit = (1 - multiplier) * current_candle["close"]
                            _limit = float(f"{_limit:.1f}")
                            strategy.entry(signal=signal,
                                           direction=direction,
                                           percent_of_assets=percent_of_assets,
                                           qty=chunk,
                                           limit=_limit,
                                           stop=stop,
                                           comment=comment)

                        quantity = float(
                            str(chunks[0] / current_candle["close"])[:5])

                try:
                    if limit is None:
                        order = strategy.futures_create_order(
                            symbol=strategy.symbol,
                            side=side,
                            type="MARKET",
                            quantity=quantity,
                            newOrderRespType='RESULT')
                    else:
                        order = strategy.futures_create_order(
                            symbol=strategy.symbol,
                            side=side,
                            type="LIMIT",
                            quantity=quantity,
                            price=limit,
                            newOrderRespType='RESULT',
                            timeInForce="GTC")

                    trade = Trade(
                        orderid=order["orderId"],
                        type=direction,
                        entry_date=order["updateTime"],
                        entry_price=current_candle["close"],
                        entry_signal=signal,
                        contract=quantity,
                        order_type="MARKET" if limit is None else "LIMIT",
                        comment=comment)

                    close_time = current_candle.close_time
                    plot = strategy._plot_to_channel(trade)
                    caption = f"#Open#{direction}#{signal}\n\n\n"\
                        f"Open {direction} in"\
                        f"{strategy._round_time(close_time)}"\
                        f"\n\nOpen Price: {trade.entry_price}"\
                        f"\nContract: {quantity}"\
                        f"\nComment: {comment}"
                    # strategy._send_image(plot, caption=caption)

                    strategy._open_positions.append(trade)
                except BinanceAPIException as e:
                    msg = "Error in Open Position\n"\
                        f"\nSymbol: {strategy.symbol}"\
                        f"\nSide: {side}\nQuantity: {quantity}"\
                        f"\nEntry Price: {current_candle['close']}"\
                        f"\nError: {e}"
                    strategy._send_message(msg)

    def _permission_entry(strategy, **kwargs):
        """Check if the user has permission to open a position"""
        if strategy._entry and \
            strategy.start_trade and \
            strategy.data.date.iloc[
                -1] == kwargs["current_candle"]["date"] and\
                strategy.free_secondary > strategy.minQty:
            side = kwargs["direction"]
            entry_date = strategy._round_time(
                kwargs["current_candle"].close_time)
            if strategy._permission_long and side == "long":
                return True
            elif side == "long":
                # Send message to Telegram
                msg = "Strategy is not allowed to open a long position"\
                    f"\n\nSymbol: {strategy.symbol}"\
                    f"\nEntry Date: {entry_date}"\
                    f"\nEntry Signal: {kwargs['signal']}"\
                    f"\nComment: {kwargs['comment']}"
                strategy._send_message(msg)
                return False
            elif strategy._permission_short and side == "short":
                return True
            elif side == "short":
                # Send message to Telegram
                msg = "Strategy is not allowed to open a short position"\
                    f"\n\nSymbol: {strategy.symbol}"\
                    f"\nEntry Date: {entry_date}"\
                    f"\nEntry Signal: {kwargs['signal']}"\
                    f"\nComment: {kwargs['comment']}"
                print(msg)
                strategy._send_message(msg)
                return False
            else:
                return False
        else:
            return False

    def exit(strategy,
             from_entry: str,
             signal: str = None,
             qty: float = 1,
             limit: float = None,
             stop: float = None,
             comment: str = None,
             reduceOnly: bool = False):
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
            if strategy.start_trade and strategy.data.date.iloc[
                    -1] == current_candle["date"]:
                open_position = [
                    position for position in strategy.open_positions
                    if position.entry_signal == from_entry
                ]
                for position in open_position:
                    if position.type == "long":
                        side = "SELL"
                    elif position.type == "short":
                        side = "BUY"
                    try:
                        # Calculate parameters such as profit, draw down, etc.
                        data_trade = strategy.data.loc[
                            strategy.data.close_time.between(
                                position.entry_date,
                                current_candle.close_time + 1)]
                        quantity = position.contract * qty
                        strategy.futures_create_order(
                            symbol=strategy.symbol,
                            side=side,
                            type='MARKET',
                            quantity=quantity,
                            newOrderRespType='RESULT',
                            reduceOnly=reduceOnly)
                        position.exit_date = strategy._prepare_time(
                            current_candle.close_time)
                        position.exit_price = current_candle.close
                        position.exit_signal = signal
                        CalculatorTrade(position, data_trade)
                        close_time = current_candle.close_time
                        plot = strategy._plot_to_channel(position)
                        caption = f"#Close#{position.type}#{signal}\n\n\n"\
                            f"Close {position.type} in "\
                            f"{strategy._round_time(close_time)}"\
                            f"\n\nClose Price: {current_candle.close}\n"\
                            f"Contract: {position.contract}\n"\
                            f"Comment: {comment}\n"\
                            f"Profit: {position.profit}\n"\
                            f"Profit Percent: {position.profit_percent}\n"\
                            f"Draw Down: {position.draw_down}\n"\
                            f"Entry Price: {position.entry_price}\n"\
                            f"Entry Signal: {position.entry_signal}\n"\
                            f"Entry Date: {position.entry_date}\n\n"\
                            f"Exit Price: {position.exit_price}\n"\
                            f"Exit Signal: {position.exit_signal}\n"\
                            f"Exit Date: {position.exit_date}"
                        strategy._send_image(plot, caption=caption)

                        strategy._open_positions.remove(position)
                        strategy._closed_positions.append(position)
                    except BinanceAPIException as e:
                        msg = f"Error in Close Position\n\n"\
                            f"Symbol: {strategy.symbol}\n"\
                            f"Side: {side}\nQuantity: {quantity}\n "\
                            f"Entry Price: {position.entry_price}\n "\
                            f"Exit Price: {current_candle['close']}\n"\
                            f"Error: {e}"
                        strategy._send_message(msg)
            else:
                strategy._check_exit_if_position(current_candle, from_entry)

    def _check_exit_if_position(self, current_candle: pd.Series,
                                from_entry: str) -> None:
        """
        Control the exit signal if it has a position.

        Description:
            If current_candle is not the last candle in data
            and receive an exit signal from the strategy,
            so send message to user that the exit signal is received
            and strategy could not close position so
            if you want to close position you should use the command
            /stop_close_position.
        """
        if self.start_trade:
            open_position = [
                position for position in self.open_positions
                if position.entry_signal == from_entry
            ]
            for position in open_position:
                if position.entry_date < current_candle.date:
                    msg = "Exit signal received at"\
                        f" {self._round_time(current_candle.close_time)}"\
                        " but position is not closed"\
                        f"\n\nSymbol: {self.symbol}"\
                        f"\nEntry Date: {position.entry_date}"\
                        f"\nEntry Signal: {position.entry_signal}"\
                        f"\nComment: {position.comment}"

                    self._send_message(msg)

    def close_positions(strategy):
        """
        Close all open positions.
        """
        strategy.current_candle = strategy.data.iloc[-1].name
        for position in strategy.open_positions:
            strategy.exit(from_entry=position.entry_signal, reduceOnly=True)

    def _current_candle_calc(strategy):
        """
        Calculate the current candle for the strategy.
        """

        current_candle = strategy.data.iloc[-1]
        return current_candle

    def round_down(strategy, x, base=5):
        """ Round down to the nearest 'base' """
        return int(base * math.floor(float(x) / base))

    def run(self):
        """Run the strategy."""
        self._exit = True
        self._entry = True
        self._permission_long = True
        self._permission_short = True
        self.start_trade = True

    def setdata(self, data):
        """This function used in Strategy class
        but in User class should not do anything."""
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
        list_of_symbols = strategy.futures_exchange_info()["symbols"]
        try:
            info = next(item for item in list_of_symbols
                        if item["symbol"] == symbol)
            strategy.symbol = symbol
            strategy.minQty = float(
                next(item for item in info["filters"]
                     if item["filterType"] == "MARKET_LOT_SIZE")["minQty"])
            return primary, secondary
        except StopIteration:
            err = f"The pair {symbol} is not supported."\
                f"({primary=}, {secondary=})"
            raise ValueError(err)

    @staticmethod
    def _plot(candles: pd.DataFrame,
              entry_date: int or pd.Timestamp = None,
              exit_date: int or pd.Timestamp = None,
              type_: str = None):
        """Plot the candles."""
        show_exit = True
        if exit_date is None:
            show_exit = False
            exit_date = entry_date
        if not type_:
            type_ = "candle"
        if type_ == "candle":
            entry_color = "blue"
            exit_color = "blue"
            y_entry = candles.close.loc[0]
            y_exit = candles.close.loc[-1]
        elif type_ == "long":
            entry_color = "green"
            exit_color = "red"
            candle_entry = candles.loc[entry_date]
            candle_exit = candles.loc[exit_date]
            y_entry = candle_entry.high
            y_exit = candle_exit.low
        else:
            entry_color = "red"
            exit_color = "green"
            candle_entry = candles.loc[entry_date]
            candle_exit = candles.loc[exit_date]
            y_entry = candle_entry.low
            y_exit = candle_exit.high

        candles.index = pd.to_datetime(candles.date, unit="ms")
        chart = go.Candlestick(x=candles.index,
                               open=candles.open,
                               high=candles.high,
                               low=candles.low,
                               close=candles.close)

        entry_arrow = go.Scatter(x=[candle_entry.date],
                                 y=[y_entry],
                                 mode="markers",
                                 marker=dict(color=entry_color, size=10))

        if show_exit:
            exit_arrow = go.Scatter(x=[candle_exit.date],
                                    y=[y_exit],
                                    mode="markers",
                                    marker=dict(color=exit_color, size=10))
            data = [chart, entry_arrow, exit_arrow]
        else:
            data = [chart, entry_arrow]
        layout = go.Layout(title=type_,
                           xaxis=dict(title="Date"),
                           yaxis=dict(title="Price"))
        fig = go.Figure(data=data, layout=layout)

        # disable range slider
        fig.update_layout(
            xaxis=dict(rangeslider=dict(visible=False), type="date"))

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
            data = data.reset_index(drop=True)
            start_trade = data.iloc[-1].name
            end_trade = None
        else:
            start_trade = data[(data.close_time >= start_date
                                )].iloc[0].name if start_date else 0
            # end_trade = data[(data.close_time <= end_date)].iloc[-1].name
            end_trade = data.iloc[-1].name
            data = data.iloc[start_trade - 50:end_trade + 1]

        return strategy._plot(data,
                              entry_date=start_trade,
                              exit_date=end_trade,
                              type_=trade.type)

    def _set_leverage(strategy, leverage: int):
        """
        Set the leverage of the strategy.
        Parameters
        ----------
        leverage : int
            The leverage of the strategy.
        """
        if leverage < 1:
            strategy._send_message(
                f"Leverage must be greater than 1.\n\nLeverage: {leverage}")
            raise ValueError("Leverage must be greater than 1.")
        try:
            strategy.futures_change_leverage(symbol=strategy.symbol,
                                             leverage=leverage)
            strategy._send_message(f"Leverage changed to {leverage}")
            return leverage
        except BinanceAPIException as e:
            err = f"Error in Set Leverage\n\n"\
                f"Leverage: {leverage}\nError: {e}"
            strategy._send_message(err)
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
            msg = f"Margin type must be either isolated or crossed.\n\n"\
                f"Margin Type: {margin_type}"
            strategy._send_message(msg)
            raise ValueError("Margin type must be either isolated or crossed.")
        try:
            strategy.futures_change_margin_type(symbol=strategy.symbol,
                                                marginType=margin_type)
            strategy._send_message(f"Margin type changed to {margin_type}")
            return margin_type
        except BinanceAPIException as e:
            if e.message == "No need to change margin type.":
                strategy._send_message(f"Margin type is already {margin_type}")
                return margin_type
            else:
                err = f"Error in Set Margin Type\n\n"\
                    f"Margin Type: {margin_type}\nError: {e}"
                strategy._send_message(err)
            raise e

    def _send_error_message(strategy, err: Exception):
        """
        Send an error message to the channel.
        Parameters
        ----------
        msg : str
            The error message to send.
        """
        strategy.start_trade = False
        strategy._entry = False
        strategy._exit = False
        msg = str(err) + "\n" + "User is down!!"
        if strategy.telegram_bot:
            strategy.telegram_bot.send_message_to_channel(msg)
        else:
            print(msg)

    def _send_message(self, msg: str) -> None:
        """
        Send a message to the channel.
        Parameters
        ----------
        msg : str
            The message to send.
        """
        if self.telegram_bot:
            self.telegram_bot.send_message_to_channel(msg)
        else:
            print(msg)

    def _send_image(self, img, caption: str = None) -> None:
        """
        Send an image to the channel.
        Parameters
        ----------
        img : Image
            The image to send.
        caption : str
            The caption of the image.
        """
        if self.telegram_bot:
            self.telegram_bot.send_image_to_channel(img, caption=caption)
        else:
            print(img)

    def decomposition(self, num):
        """
        Decomposition of a number into random numbers between 80 and 120
        until our sum of numbers is equal to the number we are decomposing.
        Parameters
        ----------
        num : int
            The number to decompose.
        """
        origin_num = num
        numbers = []
        while num > 0:
            if num < self.min_usd:
                numbers = [i + (num / len(numbers)) for i in numbers]
                if sum(numbers) != origin_num:
                    diff = origin_num - sum(numbers)
                    numbers[0] += diff
                break
            rand_int = random.randint(self.min_usd, self.max_usd)
            numbers.append(rand_int)
            num -= rand_int

        return numbers

    def _validate_keep_time_limit_chunk(self,
                                        keep_time_limit_chunk: str = None):
        """
        Validate the keep time limit chunk.
        Parameters
        ----------
        keep_time_limit_chunk : str
            The keep time limit chunk.
        """
        if not keep_time_limit_chunk:
            return None
        numerical = float(keep_time_limit_chunk[0])
        letter = keep_time_limit_chunk[1].lower()
        if letter not in ["s", "m", "h", "d"]:
            raise ValueError("Keep time limit chunk must be in s, "
                             "m, h or d.")
        if numerical < 0:
            raise ValueError("Keep time limit chunk must be greater than 0.")

        if letter == "s":
            numerical = numerical

        if letter == "m":
            numerical = numerical * 60

        if letter == "h":
            numerical = numerical * 60 * 60

        if letter == "d":
            numerical = numerical * 60 * 60 * 24

        interval = self.interval.lower()
        int_ = int(interval[0])
        # Convert interval to seconds
        if interval[1] == "s":
            interval = int_
        elif interval[1] == "m":
            interval = int_ * 60
        elif interval[1] == "h":
            interval = int_ * 60 * 60
        elif interval[1] == "d":
            interval = int_ * 60 * 60 * 24

        return numerical * 1000

    def _sl_onion(self):
        """
        In case of setting percent_sl
        positions that reach percent_sl of
        their entry price will be closed.
        """
        current_candle = self.data.loc[self.current_candle]
        for position in self._open_positions:
            if position.type == "long":
                if current_candle.close < position.entry_price * (
                        1 - self.percent_sl):
                    self.exit(position.entry_signal,
                              signal="STOP LOSS (ONION)")
            else:
                if current_candle.close > position.entry_price * (
                        1 + self.percent_sl):
                    self.exit(position.entry_signal,
                              signal="STOP LOSS (ONION)")

    def _convert_expired_orders_limit(self):
        """
        Convert expired limit orders to market orders.
        """
        for order in self._open_positions:
            if order.order_type.lower() == "limit" and\
              (self.current_time - order.entry_date)\
              > self.keep_time_limit_chunk:
                try:
                    self.futures_cancel_order(orderId=order.orderid,
                                              symbol=self.symbol)
                    # Delete order from open positions
                    self._open_positions.remove(order)
                    # Create market order
                    new_order = self.futures_create_order(
                        symbol=self.symbol,
                        side="BUY" if order.type.lower() == "long" else "SELL",
                        type="MARKET",
                        quantity=order.contract)

                    trade = Trade(orderid=new_order["orderId"],
                                  type=order.type,
                                  entry_date=new_order["updateTime"],
                                  entry_price=new_order["price"],
                                  entry_signal=order.signal,
                                  contract=order.contract,
                                  order_type="MARKET",
                                  comment=order.comment)

                    close_time = trade.entry_date
                    plot = self._plot_to_channel(trade)
                    caption = f"#Open#{order.type}#{order.signal}\n\n\n"\
                        f"Open {order.type} in"\
                        f"{self._round_time(close_time)}"\
                        f"\n\nOpen Price: {trade.entry_price}"\
                        f"\nContract: {order.contract}"\
                        f"\nComment: {order.comment}"
                    self._send_image(plot, caption=caption)

                    self._open_positions.append(trade)
                except BinanceAPIException as e:
                    msg = "Error in Open Position\n"\
                        f"\nSymbol: {self.symbol}"\
                        f"\nSide: {order.direction}\n"\
                        f"Quantity: {order.contract}"\
                        f"\nEntry Price: {order.entry_price}"\
                        f"\nError: {e}"
                    self._send_message(msg)

    def restart_streams(self):
        """
        Restart client and threads.
        """
        self._validate_data(data=None)
