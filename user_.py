from datetime import datetime, timezone
import io
import math
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from binance import Client
from binance.exceptions import BinanceAPIException

from strategy_tester.binance_inheritance import (ThreadedWebsocketManager)
from strategy_tester.models import Trade, Order
from strategy_tester.models.trade import OrderToTrade
from strategy_tester.strategy import Strategy
# from strategy_tester.binance_inheritance import StreamUserData


class User(Client, Strategy):
    """
    
    Attributes
    ----------
    api_key : str(required)
        The API key taken from the Binance exchange.
    api_secret : str(required)
        The API secret taken from the Binance exchange.
    primary_pair : str(required)
        The primary pair of the trading pair.
    secondary_pair : str(required)
        The secondary pair of the trading pair.
    interval : str(required)
        The interval of the kline.
    leverage : int(required)
        The leverage of the account.
    margin_type : str(required)
        The margin type of the account.
    telegram_bot : str(optional)
        The telegram_bot manager.(default: None)
    asset_limit : float(optional)
        The maximum amount of the wallet to trade. (default: None)
        Note: If the asset_limit is None, the asset_limit is set to the maximum amount of the wallet.
    """

    _user = True

    def __init__(self,
                 api_key: str,
                 api_secret: str,
                 primary_pair: str,
                 secondary_pair: str,
                 interval: str,
                 leverage: int,
                 margin_type: str,
                 telegram_bot=None,
                 asset_limit: float = math.inf,
                 safe_take_profit: float = 0.0,
                 safe_stop_loss: float = 0.0):
        # Configurations
        self._user_start = False
        self._user_exit = False
        self._user_entry = False
        self._current_kline = None
        self._current_candle = None
        self._user_connection_internet = True
        self._user_asset_limit = float(asset_limit)
        self.safe_take_profit = float(safe_take_profit)
        self.safe_stop_loss = float(safe_stop_loss)
        self.interval = interval

        self.telegram_bot = telegram_bot

        super(Client, self).__init__(api_key, api_secret)

        self.primary_pair, self.secondary_pair = \
            self._validate_pair(primary_pair, secondary_pair)

        self._user_open_positions = self._validate_open_positions()
        self._user_orders = self._validate_open_orders()
        self._user_orders_filled = {}
        self._user_closed_positions = []

        # self.websocket_manager = ThreadedWebsocketManager(api_key, api_secret)
        # self.websocket_manager.start()

        self._user_leverage = self._set_leverage(leverage)
        self._user_margin_type = self._set_margin_type(margin_type)
        # self._validate_data()
        
    @property
    def hlcc4(strategy):
        hlcc = strategy.high + strategy.low + strategy.close + strategy.close
        strategy._hlcc4 = hlcc / 4
        return strategy._hlcc4

    @property
    def user_open_positions(self) -> list:
        """Get the open positions."""
        # If bot at start, get the open positions from self.futures_position_information(symbol=self.symbol) else
        # return self._user_open_positions
        return self._user_open_positions

    @property
    def user_free_secondary(self):
        """Get the free secondary balance."""
        secondary = next(item for item in self.futures_account_balance()
                         if item["asset"] == self.secondary_pair)
        secondary = float(secondary["withdrawAvailable"])
        if secondary > self._user_asset_limit:
            secondary = self._user_asset_limit
        else:
            secondary = secondary
        return secondary

    def trade(strategy, row):
        """Execute the trade for the strategy.

        Description
        -----------
        In this function, set the current candle and
        execute the trade_calc function.

        Parameters
        ----------
        row: DataFrame
            The row of the data that you want to execute the trade for.
        """
        strategy.current_candle = row
        if strategy.percent_sl is not None:
            strategy._sl_onion()

        strategy.trade_calc(row)

    def entry(self,
              signal: str,
              direction: str,
              qty: int or float = 1,
              limit: int or float = None,
              stop: int or float = None,
              comment: str = None) -> None:
        """Send a new order
        
        Parameters
        ----------
        signal : str(required)
            The order identifier. It is possible to cancel or modify an order by referencing its identifier.
        direction : str(required)
            The direction of the order. Valid values are long or sell.
        qty : int or float(optional)
            Number of contracts/shares/lots/units to trade. The default value is 1.
        limit : int or float(optional)
            Limit price of the order. If it is specified, the order type is either 'limit', or 'stop-limit'. 'None' should be specified for any other order type.
        stop : int or float(optional)
            Stop price of the order. If it is specified, the order type is either 'stop', or 'stop-limit'. 'None' should be specified for any other order type.
        comment : str(optional)
            Additional notes on the order.
        """
        super().entry(signal, direction, qty, limit, stop, comment)
        if self._permission_entry(signal, direction, qty, limit, stop,
                                  comment):

            if qty is None:
                quantity = float(
                    str(self.user_free_secondary * 0.999 /
                        self.current_candle["close"])[:5])
            else:
                quantity = float(str(qty)[:5])

            if direction == "long":
                side = "BUY"
            elif direction == "short":
                side = "SELL"

            try:
                if limit:
                    order = self.futures_create_order(
                        symbol=self.symbol,
                        side=side,
                        type="LIMIT",
                        quantity=quantity,
                        price=limit,
                        newOrderRespType='RESULT',
                        timeInForce="GTC")
                else:
                    order = self.futures_create_order(
                        symbol=self.symbol,
                        side=side,
                        type="MARKET",
                        quantity=quantity,
                        newOrderRespType="RESULT",
                    )

                _order = Order(
                    entry=True,
                    side=order["side"],
                    cumQty=order["cumQty"],
                    cumQuote=order["cumQuote"],
                    executedQty=order["executedQty"],
                    orderId=order["orderId"],
                    avgPrice=order["avgPrice"],
                    origQty=order["origQty"],
                    price=order["price"],
                    reduceOnly=order["reduceOnly"],
                    positionSide=order["positionSide"],
                    status=order["status"],
                    stopPrice=order["stopPrice"],
                    closePosition=order["closePosition"],
                    symbol=order["symbol"],
                    timeInForce=order["timeInForce"],
                    type=order["type"],
                    origType=order["origType"],
                    updateTime=order["updateTime"],
                    workingType=order["workingType"],
                    priceProtect=order["priceProtect"],
                    activatePrice=order.get("activatePrice"),
                    priceRate=order.get("priceRate"),
                    entry_signal=order["entry_signal"],
                    exit_signal=order["exit_signal"],
                    comment=order["comment"],
                )

                close_time = self.current_candle["closeTime"]
                caption = f"#Send_open_order #{direction} #{signal}\n\n\n"\
                    f"Open {direction} in"\
                    f"{self._round_time(close_time)}"\
                    f"\n\nOrder ID: {order['orderId']}"\
                    f"\nEntry signal: {_order.entry_signal}"\
                    f"\nOpen Price: {_order.price}"\
                    f"\nContract: {quantity}"\
                    f"\nEntry amount: {_order.price * quantity}"\
                    f"\nComment: {comment}"

                self._user_orders[_order.orderId] = _order

            except BinanceAPIException as e:
                msg = "Error in Open Position\n"\
                    f"\nSymbol: {self.symbol}"\
                    f"\nSide: {side}\nQuantity: {quantity}"\
                    f"\nEntry Price: {self.current_candle['close']}"\
                    f"\nError: {e}"
                self._send_message(msg)

    def _validate_open_positions(self):
        """Validate the open positions."""
        positions = self.futures_position_information(symbol=self.symbol)
        if positions[0]:
            if float(positions[0]["positionAmt"]) == 0:
                return []
        else:
            open_positions = []
            for position in positions:
                position = Trade(
                    type="long"
                    if position["positionAmt"][0] != "-" else "short",
                    entry_date=position["updateTime"],
                    entry_price=float(position["entryPrice"]),
                    entry_signal="long"
                    if position["positionAmt"][0] != "-" else "short",
                    contract=abs(float(position["positionAmt"])),
                    comment="Position opened after bot start")
                open_positions.append(position)
            return open_positions

    def _validate_open_orders(self):
        """Validate the open orders."""
        open_orders = [
            order for order in self.futures_get_open_orders()
            if order["symbol"] == self.symbol
        ]
        orders = {}
        for order in open_orders:
            order = Trade(
                orderid=order["orderId"],
                order_type=order["type"],
                type="long" if order["side"].lower() == "buy" else "short",
                entry_date=order["time"],
                entry_price=float(order["price"]),
                entry_signal="long"
                if order["side"].lower() == "buy" else "short",
                contract=abs(float(order["origQty"])),
                comment="Order opened after bot start")
            orders[order.orderid] = order
        return orders

    def _set_leverage(self, leverage):
        """Set the leverage."""
        if leverage < 1:
            self._send_message(
                f"Leverage must be greater than 1.\n\nLeverage: {leverage}")
            raise ValueError("Leverage must be greater than 1.")
        try:
            self.futures_change_leverage(symbol=self.symbol, leverage=leverage)
            self._send_message(f"Leverage changed to {leverage}")
            return leverage
        except BinanceAPIException as e:
            err = f"Error in Set Leverage\n\n"\
                f"Leverage: {leverage}\nError: {e}"
            self._send_message(err)
            raise e

    def _set_margin_type(self, margin_type):
        """Set the margin type"""
        margin_type = margin_type.upper()
        if margin_type not in ["ISOLATED", "CROSSED"]:
            msg = f"Margin type must be either isolated or crossed."
            self._send_message(msg)
            raise ValueError("Margin type must be either isolated or crossed.")
        try:
            self.futures_change_margin_type(symbol=self.symbol,
                                            marginType=margin_type)
            self._send_message(f"Margin type changed to {margin_type}")
            return margin_type
        except BinanceAPIException as e:
            if e.message == "No need to change margin type.":
                self._send_message(f"Margin type is already {margin_type}")
                return margin_type
            else:
                err = f"Error in Set Margin Type\n\n"\
                    f"Margin Type: {margin_type}\nError: {e}"
                self._send_message(err)
                raise e

    def _validate_pair(self, primary, secondary):
        """Validate the pair."""
        primary = primary.upper()
        secondary = secondary.upper()
        symbol = primary + secondary
        symbols = self.futures_exchange_info()["symbols"]
        try:
            info = next(item for item in symbols if item["symbol"] == symbol)
            self.symbol = symbol
            self._user_minQty = float(
                next(item for item in info["filters"]
                     if item["filterType"] == "MARKET_LOT_SIZE")["minQty"])
            return primary, secondary
        except StopIteration:
            err = f"The pair {symbol} is not supported."\
                f"({primary=}, {secondary=})"
            raise ValueError(err)

    def _validate_data(self):
        """Validate the data."""
        data = self._get_data()
        try:
            self._user_listen_key = self.futures_stream_get_listen_key()
            # Update 
            self._user_stream = self.symbol.lower() + "@kline_" + \
                self.interval

            self.websocket_manager\
                .start_multiplex_socket(
                    callback=self._handle_socket_message,
                    streams=[self._user_stream],
                )

        except Exception as e:
            self._send_error_message(e)

        data.index = data.date
        self.data = data
        self.open = data.open
        self.high = data.high
        self.low = data.low
        self.close = data.close
        self.volume = data.volume
        self.last_candle = data.date.iloc[-1]

    def _get_data(self):
        """Get the 3000 latest data."""
        num, period = re.match(r"([0-9]+)([a-z]+)", self.interval,
                               re.I).groups()
        # Get <num> kline data ago
        num = 3000 * int(num)
        remind_kline = pd.DataFrame(
            self.get_historical_klines(
                self.symbol, self.interval,
                start_str=f"{num}{period} ago UTC")).iloc[:, :9]

        remind_kline.columns = [
            "date", "open", "high", "low", "close", "volume", "close_time",
            "quote_asset_volume", "num_trades"
        ]
        remind_kline.index = remind_kline["date"]
        remind_kline.drop(columns=["quote_asset_volume"], inplace=True)
        remind_kline = remind_kline.astype(float)

        return remind_kline

    def _handle_socket_message(self, msg):
        if msg["data"]["e"] == "connection error":
            self._disconnected(msg)
        elif msg["data"]["e"] == "stream live error":
            self._stream_live_error(msg)
        else:
            if self._user_connection_internet:
                self._user_connection_internet = True
                message = "Connected to the internet at "\
                  f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
                self._send_message(message)

        if msg["stream"] == self._user_stream:
            self._handle_socket_kline(msg["data"])
        elif msg["data"]["e"] == "listenKeyExpired":
            message = "Your listen key has expired. Please reconnect."
            self._send_message(message)
        elif msg["data"]["e"] == "MARGIN_CALL":
            self._margin_call(msg)
        elif msg["data"]["e"] == "ACCOUNT_UPDATE":
            self._account_update(msg)
        elif msg["data"]["e"] == "ORDER_TRADE_UPDATE":
            self._order_trade_update(msg)

    def _handle_socket_kline(strategy, msg: dict):
        """
        Convert kline data to pandas dataframe
        """
        frame = pd.DataFrame([msg['k']])
        frame = frame.filter(['t', 'T', 'o', 'c', 'h', 'l', 'v', 'n'])
        frame.columns = [
            'date', 'close_time', 'open', 'close', 'high', 'low', 'volume',
            'num_trades'
        ]
        frame.index = frame['date']
        frame = frame.astype(float)

        if msg["k"]["x"]:
            while strategy.data.empty:
                pass
            strategy._combine_data(frame)
            strategy.high = strategy.data.high
            strategy.low = strategy.data.low
            strategy.open = strategy.data.open
            strategy.close = strategy.data.close
            strategy.volume = strategy.data.volume
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

    def _combine_data(self, frame: pd.DataFrame):
        """Add last websocket data to main data"""

        frame = frame.filter(self.data.columns)
        if frame.date.iloc[0] == self.data.iloc[-1].date:
            self.data.iloc[-1] = frame.iloc[0].values
        else:
            self.data = pd.concat([self.data, frame]).iloc[1:]

    def _disconnected(self, msg):
        if self._user_connection_internet:
            connected = msg["connected_check"]
            error_msg = msg["error_msg"]
            # time in GTC

            txt = "Disconnected from the internet at"\
                f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n"\
                f"Internet connection is {connected}\n"\
                f"Error message: {error_msg}"
            self._send_message(txt)
            self._user_connection_internet = False

    def _stream_live_error(self, msg):
        msg = "Stream live error at \n"\
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
        self._send_message(msg)
        self._validate_data(msg)

    def _margin_call(self, msg):
        """
        Note
        ----
            When the user's position risk ratio is too high, this stream will be pushed.
            This message is only used as risk guidance information and is not recommended for investment strategies.
            In the case of a highly volatile market, there may be the possibility that the user's position has been liquidated at the same time when this stream is pushed out.
        """
        note_margin_call = "You will encounter a margin call when "\
            "your position risk ratio is to high."\
            "Note\n"\
            "-----\n"\
            "1. This message is only used as risk guidance information and"\
            "is not recommended for investment strategies."\
            "2. In the case of a highly volatile market, "\
            "there may be the possibility that "\
            "the user's position has been liquidated "\
            "at the same time when this stream is pushed out."

        self._send_message(note_margin_call)
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
            self._send_message(message)

    def _account_update(self, msg):
        """
        Note
        ----
        When balance or position get updated, this event will be pushed.

            ACCOUNT_UPDATE will be pushed only when update happens on user's account, including changes on balances, positions, or margin type.
            
            Unfilled orders or cancelled orders will not make the event ACCOUNT_UPDATE pushed, since there's no change on positions.
            
            Only positions of symbols with non-zero isolatd wallet or non-zero position amount will be pushed in the "position" part of the event ACCOUNT_UPDATE when any position changes.
            
        When "FUNDING FEE" changes to the user's balance, the event will be pushed with the brief message:

            When "FUNDING FEE" occurs in a crossed position, ACCOUNT_UPDATE will be pushed with only the balance B(including the "FUNDING FEE" asset only), without any position P message.
            When "FUNDING FEE" occurs in an isolated position, ACCOUNT_UPDATE will be pushed with only the balance B(including the "FUNDING FEE" asset only) and the relative position message P( including the isolated position on which the "FUNDING FEE" occurs only, without any other position message).

        The field "m" represents the reason type for the event and may shows the following possible types:

            DEPOSIT
            WITHDRAW
            ORDER
            FUNDING_FEE
            WITHDRAW_REJECT
            ADJUSTMENT
            INSURANCE_CLEAR
            ADMIN_DEPOSIT
            ADMIN_WITHDRAW
            MARGIN_TRANSFER
            MARGIN_TYPE_CHANGE
            ASSET_TRANSFER
            OPTIONS_PREMIUM_FEE
            OPTIONS_SETTLE_PROFIT
            AUTO_EXCHANGE

        The field "bc" represents the balance change except for PnL and commission.
        """
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
            self._send_message(message)
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
            self._send_message(message)

    def _order_trade_update(self, msg):
        """When new order created, order status changed will push such event. event type is ORDER_TRADE_UPDATE."""
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

        if order_id in self._user_orders:
            if order_status == "FILLED":
                _order = self._user_orders[order_id]
                _order.updateTime = order_trade_time
                if _order.entry:
                    trade = OrderToTrade.entry(_order)
                    self._user_open_positions.append(trade)
                    _order.filledAccumulatedQty = order_filled_accumulated_quantity
                    self._user_orders_filled[order_id] = _order
                    del self._user_orders[order_id]
                    plot = self._plot_to_channel(trade)
                    caption = f"#Open_position\n\n"\
                        f"Symbol: {self.symbol}\n"\
                        f"Contract: {trade.contract}\n"\
                        f"Type: {trade.type}\n"\
                        f"Entry price: {trade.entry_price}\n"\
                        f"Entry time: {trade.entry_date}\n"\
                        f"Comment: {trade.comment}\n"
                    self._send_image(plot, caption)
                else:
                    _trade = next(trade for trade in self._user_open_positions
                                  if trade.entry_signal == _order.entry_signal)
                    trade = OrderToTrade.exit(_trade, _order, self.data)
                    self._user_closed_positions.append(trade)
                    self._user_orders_filled[order_id] = _order
                    del self._user_orders[order_id]
                    plot = self._plot_to_channel(trade)
                    caption = f"#Closed_position\n\n"\
                        f"Symbol: {self.symbol}\n"\
                        f"Contract: {trade.contract}\n"\
                        f"Type: {trade.type}\n"\
                        f"Entry price: {trade.entry_price}\n"\
                        f"Entry time: {trade.entry_date}\n"\
                        f"Exit price: {trade.exit_price}\n"\
                        f"Exit time: {trade.exit_date}\n"\
                        f"Signal: {trade.entry_signal}\n"\
                        f"Profit: {trade.profit}\n"\
                        f'Profit percent: {trade.profit_percent}\n'\
                        f"Drawdown: {trade.draw_down}\n"\
                        f"Runup: {trade.run_up}\n"\
                        f"bars_traded: {trade.bars_traded}\n"\
                        f"Realized profit: {realized_profit}\n"\
                        f"Comment: {trade.comment}\n"
                    self._send_image(plot, caption)

            elif order_status == "PARTIALLY_FILLED":
                _order = self._user_orders[order_id]
                _order.filledAccumulatedQty = order_filled_accumulated_quantity
        else:
            # Send warning message to channel
            self._send_message("#WARNING\n\n"\
                f"Order id {order_id} with the following specifications "\
                "has not been created by the strategy,"\
                "please check immediately.")
            self._send_message(message)

    def _permission_entry(self, signal, direction, qty, limit, stop, comment):
        """Check if the user have permission to create an order."""
        last_candle = self.data.date.iloc[-1]

        if qty is None:
            quantity = float(
                str(self.user_free_secondary * 0.999 /
                    self.current_candle.close)[:5])
        else:
            quantity = float(str(qty)[:5])

        if self._user_start and \
            self._user_entry and \
            last_candle == self.current_candle.date and \
            quantity >= self._user_minQty:
            entry_date = self._round_time(self.current_candle.close_time)
            if (self._permission_long
                    and direction == "long") or (self._permission_short
                                                 and direction == "short"):
                return True
            else:
                msg = f"Strategy is not allowed to open a {direction} position"\
                    f"\n\nSymbol: {self.symbol}"\
                    f"\nEntry Date: {entry_date}"\
                    f"\nEntry Signal: {signal}"\
                    f"\nComment: {comment}"
                self._send_message(msg)
                return False

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

    def _plot_to_channel(self, trade: Trade):
        data = self.data.reset_index(drop=True)
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

        return self._plot(data,
                          entry_date=start_trade,
                          exit_date=end_trade,
                          type_=trade.type)

    @staticmethod
    def _round_time(time: float) -> datetime:
        """
        Round time to the nearest 1 second.
        
        Description:
            This function is written because when the strategy wants to open a position, it opens with the closing time of the previous candlestick, which is actually slightly shorter than the opening time of the actual candlestick, so to compensate for this difference, this function is set to 1 Rounds in seconds.
        """

        return pd.to_datetime(time, unit="ms").round("1s")

    @staticmethod
    def _convert_time(time: datetime) -> float:
        """
        Convert time to milliseconds.
        """
        return time.timestamp() * 1000

    def _send_error_message(self, err):
        """Send an error message."""
        self.start_trade = False
        self._user_entry = False
        self._user_exit = False
        msg = str(err) + "\n\n"\
            "User can't trade anymore."\
            "Please restart the program."
        if self.telegram_bot:
            self.telegram_bot.send_message_to_channel(msg)
        else:
            print(msg)

    def _send_message(self, msg):
        """Send a message."""
        if self.telegram_bot:
            self.telegram_bot.send_message_to_channel(msg)
        else:
            print(msg)

    def _send_image(self, img, caption):
        """Send an image."""
        if self.telegram_bot:
            self.telegram_bot.send_image_to_channel(img, caption)
        else:
            print(img, caption)
