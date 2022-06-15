import io
import math
import re
from typing import Dict, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from binance import Client, ThreadedWebsocketManager
from binance.exceptions import BinanceAPIException

from strategy_tester.commands import CalculatorTrade
from strategy_tester.decorator import validate_float
from strategy_tester.models import Trade

from .strategy import Strategy


class User(Client, Strategy):

    _user = True
    _exit = False
    _entry = False
    _permission_long = True
    _permission_short = True

    def __init__(strategy,
                 api_key: str,
                 api_secret: str,
                 primary_pair: str,
                 secondary_pair: str,
                 interval: str,
                 leverage: int,
                 margin_type: str,
                 custom_amount_cash: float = None,
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
        strategy.threaded_websocket_manager = \
            ThreadedWebsocketManager(api_key, api_secret)
        strategy.current_candle = None
        strategy._open_positions = []
        strategy._closed_positions = []
        strategy._in_bot = False
        strategy.start_trade = False
        strategy.telegram_bot = telegram_bot
        if strategy.open_positions != []:
            msg = f"{strategy.primary_pair}{strategy.secondary_pair}"\
                " has open positions."
            strategy.telegram_bot.send_message_to_channel(msg)
        strategy.leverage = strategy._set_leverage(leverage)
        strategy.margin_type = strategy._set_margin_type(margin_type)
        strategy.custom_amount_cash = strategy.\
            _validate_custom_amount_cash(custom_amount_cash)
        # Start the thread's activity.
        strategy.threaded_websocket_manager.start()
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
            "date", "open", "high", "low", "close", "volume", "close_time"
        ])

        strategy.interval = interval
        strategy.data = strategy._validate_data(data)

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
            return strategy._open_positions

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
            num = 1500 * int(num)
            remind_kline = pd.DataFrame(
                strategy.get_historical_klines(
                    strategy.symbol,
                    strategy.interval,
                    start_str=f"{num}{period} ago UTC")).iloc[:, :7]

        remind_kline.columns = [
            "date", "open", "high", "low", "close", "volume", "close_time"
        ]
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

        strategy.stream = \
            strategy.threaded_websocket_manager.start_kline_socket(
                strategy._human_readable_kline,
                strategy.symbol,
                strategy.interval)

        # Run stream live account
        try:
            strategy.listen_key = strategy.futures_stream_get_listen_key()
            strategy.stream_live_account = \
                strategy.threaded_websocket_manager\
                    .start_futures_multiplex_socket(
                        callback=strategy.__stream_live_account,
                        streams=[strategy.listen_key],
                    )
        except Exception as e:
            strategy._send_error_message(e)

        # Get remind kline data
        data = strategy._get_remind_kline(data)
        print(len(data))

        return data

    def __stream_live_account(strategy, msg: dict):
        """
        Get stream live account

        Description
        -----------
            Send all possible changes if any.
        """

        if msg["e"] == "listenKeyExpired":
            # Get new listen key and restart stream live account
            strategy.futures_stream_keepalive(strategy.listen_key)
        elif msg["e"] == "MARGIN_CALL":
            # Convert int time to datetime
            event_time = pd.to_datetime(msg["E"], unit="ms")
            for position in msg["p"]:
                symbol = position["s"]
                side = position["ps"]
                contract = position["pa"]
                margin_type = position["mt"]
                # Isolated Wallet(If isolated position)
                isolated_wallet = position["iw"]
                mark_price = position["mp"]
                unrealized_pnl = position["up"]
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
                strategy.telegram_bot.send_message_to_channel(message)

        elif msg["e"] == "ACCOUNT_UPDATE":
            event_time = pd.to_datetime(msg["E"], unit="ms")
            transaction_time = pd.to_datetime(msg["T"], unit="ms")
            for update in msg["a"]:
                event_reason_type = update["m"]
                for balance in update["B"]:
                    asset = balance["a"]
                    wallet_balance = balance["wb"]
                    cross_wallet_balance = balance["cwb"]
                    balance_change = balance["c"]
                    message = f"#ACCOUNT_UPDATE\n\n"\
                        f"Event time: {event_time}\n"\
                        f"Transaction time: {transaction_time}\n"\
                        f"Event reason type: {event_reason_type}\n"\
                        f"Asset: {asset}\n"\
                        f"Wallet balance: {wallet_balance}\n"\
                        f"Cross wallet balance: {cross_wallet_balance}\n"\
                        f"Balance change: {balance_change}\n"

                    # Send message to channel
                    strategy.telegram_bot.send_message_to_channel(message)
                for position in update["P"]:
                    symbol = position["s"]
                    contract = position["pa"]
                    enter_price = position["ep"]
                    unrealized_pnl = position["up"]
                    margin_type = position["mt"]
                    isolated_wallet = position["iw"]
                    mark_price = position["mp"]
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
                    strategy.telegram_bot.send_message_to_channel(message)

        elif msg["e"] == "ORDER_TRADE_UPDATE":
            event_time = pd.to_datetime(msg["E"], unit="ms")
            transaction_time = pd.to_datetime(msg["T"], unit="ms")
            for order in msg["o"]:
                symbol = order["s"]
                client_order_id = order["c"]
                side = order["S"]
                position_side = order["ps"]
                order_type = order["o"]
                time_in_force = order["f"]
                original_quantity = order["q"]
                original_price = order["p"]
                average_price = order["ap"]
                stop_price = order["sp"]
                execution_type = order["x"]
                order_status = order["X"]
                order_id = order["i"]
                order_last_filled_qty = order["l"]
                order_filled_accumulated_quantity = order["z"]
                last_filled_price = order["L"]
                commission_asset = order["N"]
                commission = order["n"]
                order_trade_time = pd.to_datetime(order["T"], unit="ms")
                trade_id = order["t"]
                bids_notional = order["b"]
                ask_notional = order["a"]
                maker_side = order["m"]
                reduce_only = order["R"]
                realized_profit = order["rp"]
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
                strategy.telegram_bot.send_message_to_channel(message)

            strategy.telegram_bot.send_message_to_channel(msg)

    def _combine_data(strategy):
        """Add last websocket data to main data"""

        last_kline_data = strategy.data.iloc[
            -1]  # Last candle in the historical kline

        # If the last candle in the historical kline
        # is in the websocket data
        if not strategy.tmp_data[strategy.tmp_data.date ==
                                 last_kline_data.date].empty:
            # Replace the last candle in the historical kline
            # with the websocket data
            strategy.data.iloc[-1] = strategy.tmp_data[
                strategy.tmp_data.date == last_kline_data.date].iloc[0]
        strategy.data = pd.concat([
            strategy.data,
            strategy.tmp_data[strategy.tmp_data.date > last_kline_data.date]
        ]).iloc[1:]  # Add the websocket data to the historical kline

    def _human_readable_kline(strategy, msg: dict):
        """
        Convert kline data to pandas dataframe
        """
        if msg["k"]["x"]:
            frame = pd.DataFrame([msg['k']])
            frame = frame.filter(['t', 'T', 'o', 'c', 'h', 'l', 'v'])
            frame.columns = [
                'date', 'close_time', 'open', 'close', 'high', 'low', 'volume'
            ]
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

    def entry(strategy,
              signal: str,
              direction: str,
              percent_of_assets: float = 1,
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
        if strategy._permission_entry(signal=signal,
                                      direction=direction,
                                      percent_of_assets=percent_of_assets,
                                      limit=limit,
                                      stop=stop,
                                      comment=comment):
            current_candle = strategy.data.loc[strategy.current_candle]
            if strategy.start_trade and strategy.data.date.iloc[
                    -1] == current_candle["date"]:
                # If there is no open position,
                # then open position
                # (Only used for having 1 open position at the same time)
                if strategy.open_positions == []:
                    quantity = float(
                        str(strategy.free_secondary * percent_of_assets *
                            0.997 / current_candle["close"])[:5])
                    if direction == "long":
                        side = "BUY"
                    elif direction == "short":
                        side = "SELL"

                    try:
                        # strategy.futures_create_order(
                        #     symbol=strategy.symbol,
                        #     side=side,
                        #     type='MARKET',
                        #     quantity=quantity,
                        #     newOrderRespType='RESULT')

                        trade = Trade(type=direction,
                                      entry_date=strategy._prepare_time(
                                          current_candle.close_time),
                                      entry_price=current_candle.close,
                                      entry_signal=signal,
                                      contract=quantity,
                                      comment=comment)

                        if strategy.telegram_bot:
                            close_time = current_candle.close_time
                            plot = strategy._plot_to_channel(trade)
                            caption = f"#Open#{direction}#{signal}\n\n\n"\
                                f"Open {direction} in"\
                                f"{strategy._round_time(close_time)}"\
                                f"\n\nOpen Price: {current_candle.close}"\
                                f"\nContract: {quantity}"\
                                f"\nComment: {comment}"
                            strategy.telegram_bot.send_image_to_channel(
                                plot, caption=caption)
                        print(caption)
                        strategy._open_positions.append(trade)
                    except BinanceAPIException as e:
                        if strategy.telegram_bot:
                            msg = "Error in Open Position\n"\
                                f"\nSymbol: {strategy.symbol}"\
                                f"\nSide: {side}\nQuantity: {quantity}"\
                                f"\nEntry Price: {current_candle['close']}"\
                                f"\nError: {e}"
                            strategy.telegram_bot.send_message_to_channel(msg)
                        print(msg)

    def _permission_entry(strategy, **kwargs):
        """Check if the user has permission to open a position"""
        if strategy._entry:
            side = kwargs["direction"]
            if strategy._permission_long and side == "long":
                strategy.entry(**kwargs)
            elif side == "long":
                # Send message to Telegram
                if strategy.telegram_bot:
                    msg = "You don't have permission to open a long position"\
                        " so strategy passed"
                    strategy.telegram_bot.send_message_to_channel(msg)
            elif strategy._permission_short and side == "short":
                strategy.entry(**kwargs)
            elif side == "short":
                # Send message to Telegram
                if strategy.telegram_bot:
                    msg = "You don't have permission to open a short position"\
                        " so strategy passed"
                    strategy.telegram_bot.send_message_to_channel(msg)

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
                        # strategy.futures_create_order(
                        #     symbol=strategy.symbol,
                        #     side=side,
                        #     type='MARKET',
                        #     quantity=quantity,
                        #     newOrderRespType='RESULT',
                        #     reduceOnly=reduceOnly)
                        position.exit_date = strategy._prepare_time(
                            current_candle.close_time)
                        position.exit_price = current_candle.close
                        position.exit_signal = signal
                        CalculatorTrade(position, data_trade)
                        if strategy.telegram_bot:
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
                            strategy.telegram_bot.send_image_to_channel(
                                plot, caption=caption)

                        print(caption)
                        strategy._open_positions.remove(position)
                        strategy._closed_positions.append(position)
                    except BinanceAPIException as e:
                        if strategy.telegram_bot:
                            msg = f"Error in Close Position\n\n"\
                                f"Symbol: {strategy.symbol}\n"\
                                f"Side: {side}\nQuantity: {quantity}\n "\
                                f"Entry Price: {position.entry_price}\n "\
                                f"Exit Price: {current_candle['close']}\n"\
                                f"Error: {e}"
                            strategy.telegram_bot.send_message_to_channel(msg)
                        print(msg)

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

    def run(strategy):
        """Run the strategy."""
        strategy.start_trade = True

    def set_data(self, data):
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
        list_of_symbols = strategy.get_exchange_info()["symbols"]
        try:
            next(item for item in list_of_symbols if item["symbol"] == symbol)
            strategy.symbol = symbol
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
            if strategy.telegram_bot:
                strategy.telegram_bot.send_message_to_channel(
                    f"Leverage must be greater than 1.\n\nLeverage: {leverage}"
                )
            raise ValueError("Leverage must be greater than 1.")
        try:
            strategy.futures_change_leverage(symbol=strategy.symbol,
                                             leverage=leverage)
            strategy.telegram_bot.send_message_to_channel(
                f"Leverage changed to {leverage}")
            return leverage
        except BinanceAPIException as e:
            if strategy.telegram_bot:
                err = f"Error in Set Leverage\n\n"\
                    f"Leverage: {leverage}\nError: {e}"
                strategy.telegram_bot.send_message_to_channel(err)
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
                msg = f"Margin type must be either isolated or crossed.\n\n"\
                    f"Margin Type: {margin_type}"
                strategy.telegram_bot.send_message_to_channel(msg)
            raise ValueError("Margin type must be either isolated or crossed.")
        try:
            strategy.futures_change_margin_type(symbol=strategy.symbol,
                                                marginType=margin_type)
            strategy.telegram_bot.send_message_to_channel(
                f"Margin type changed to {margin_type}")
            return margin_type
        except BinanceAPIException as e:
            if strategy.telegram_bot:
                if e.message == "No need to change margin type.":
                    strategy.telegram_bot.send_message_to_channel(
                        f"Margin type is already {margin_type}")
                    return margin_type
                else:
                    err = f"Error in Set Margin Type\n\n"\
                        f"Margin Type: {margin_type}\nError: {e}"
                    strategy.telegram_bot.send_message_to_channel(err)
                raise e

    def _send_error_message(strategy, err: Exception):
        """
        Send an error message to the channel.
        Parameters
        ----------
        msg : str
            The error message to send.
        """
        if strategy.telegram_bot:
            strategy.start_trade = False
            strategy._entry = False
            strategy._exit = False
            msg = str(err) + "\n" + "User is down!!"
            strategy.telegram_bot.send_message_to_channel(msg)
