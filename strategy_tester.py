import inspect
import re
from datetime import datetime
from threading import Thread

import pandas as pd

from strategy_tester.backtest import Backtest
from strategy_tester.commands.calculator_trade import CalculatorTrade
from strategy_tester.encoder import NpEncoder
from strategy_tester.handler.datahandler import DataHandler
from strategy_tester.models.trade import Trade
from strategy_tester.periodic import PeriodicCalc
from strategy_tester.sheet import Sheet


class StrategyTester:
    """ 
    StrategyTester constructor.
    
    Description:
        If you want to test a strategy, you need to create a StrategyTester object.
        Then you can set the strategy and the data.
        The StrategyTester will test the strategy with the data.
    
    Attributes:
        strategy: Strategy
            The strategy that you want to test.
        data: DataHandler
            The data that you want to test the strategy with.
            If you don't set the data, the StrategyTester will get the data from the binance API.(default)
            default of period time for timeframes is set to '5m'(for the past month).
        interval: str
            The interval that you want to get the data.
        cash: float
            The initial capital for the strategy.(default 10000)
        commission: float
            The commission for the strategy.(default 0)
        open_positions: list
            When the strategy is tested, the open positions will be stored in this list.
        closed_positions: list
            When the strategy is tested, the closed positions will be stored in this list.
            
    Methods:
        setdata(data: DataFrame=None)
        ----------
        entry(signal: str, direction: str, qty: float=1, limit: float=None, stop: float=None, comment: str=None)
        ----------
        exit(signal: str, from_entry: str, qty: float=1, limit: float=None, stop: float=None, comment: str=None)
        ----------
        run()
        ----------
        list_of_trades()
        ----------
        backtest()
    """
    _commission = 0.0
    
    def set_init(strategy):
        strategy._contract = False
        strategy._cash = 10000
        strategy._initial_capital = 10000
        strategy.long = "long"
        strategy.short = "short"

        strategy.interval = "5m"
        # Amount of commission paid
        strategy.commission_paid = 0
        strategy.current_candle = None
        strategy.open_positions = []
        strategy.closed_positions = []
        strategy.links_results = {}
        strategy.threads_sheet = []
        strategy.cash_series = pd.Series(dtype=float)

    @property
    def cash(strategy):
        return strategy._cash

    @cash.setter
    def cash(strategy, cash):
        if cash:
            strategy._cash = cash
            strategy._initial_capital = cash

    @property
    def interval(strategy):
        return strategy.__dict__.get("_interval", "5m")

    @interval.setter
    def interval(strategy, interval):
        if interval:
            strategy._interval = interval

    @property
    def commission(strategy):
        return strategy._commission

    @commission.setter
    def commission(strategy, comm):
        strategy._commission = strategy._set_commission(comm)
        
    @property
    def contract(self):
        return self._contract
    
    @contract.setter
    def contract(strategy, contract):
        strategy._contract = contract
        
    @property
    def position_size(self):
        return len(self.open_positions)
    
    @property
    def open_profit_percent(self):
        if self.open_positions:
            current_candle = self._current_candle_calc()
            profits = []
            for position in self.open_positions:
                if position.type == "long":
                    profit = current_candle.close - position.entry_price
                else:
                    profit = position.entry_price - current_candle.close
                profit = profit * 100/position.entry_price
                profits.append(profit)
            return tuple(profits)
        else:
            return None

    def entry(strategy,
              signal: str,
              direction: str,
              qty: float = 1,
              limit: float = None,
              stop: float = None,
              comment: str = None):
        """
        Entry function is used to open a position.
        
        Parameters
        ----------
        signal: str
            The signal that you want to open a position with.
        direction: str
            The direction that you want to open a position with.
        qty: float
            The quantity of the position.
        limit: float
            The limit price of the position.
        stop: float
            The stop price of the position.
        comment: str
            The comment of the position.
        """
        # TODO: add limit and stop

        if strategy._cash > 50:
            current_candle = strategy._current_candle_calc()
            qty = strategy._validate_qty(qty)
            strategy._commission_calc(qty)
            trade = Trade(
                type=direction,
                entry_date=strategy._prepare_time(
                    current_candle.close_time
                ),
                entry_price=current_candle.close,
                entry_signal=signal,
                contract=strategy._contract_calc(qty),
                comment=comment)
            print("entry contract:", trade.contract)
            strategy.open_positions.append(trade)

    def exit(strategy,
             from_entry: str,
             signal: str = None,
             qty: float = 1,
             limit: float = None,
             stop: float = None,
             comment: str = None):
        """
        Exit function is used to close a position.
        
        Parameters
        ----------
        signal: str
            The signal that you want to close a position with.
        from_entry: str
            The entry signal that you want to close a position with.
        qty: float
            The quantity of the position.
        limit: float
            The limit price of the position.
        stop: float
            The stop price of the position.
        comment: str
            The comment of the position.
        """
        # TODO: add limit and stop
        if strategy.open_positions != []:
            for trade in strategy.open_positions:
                if trade.entry_signal == from_entry and \
                    strategy.current_candle < strategy.last_candle:
                    qty = strategy._validate_qty(qty, trade)
                    current_candle = strategy._current_candle_calc()
                    # Calculate parameters such as profit, draw down, etc.
                    data_trade = strategy.data.loc[strategy.data.date.between(
                        trade.entry_date, current_candle.close_time)]
                    if not data_trade.empty:
                        trade.exit_date = strategy._prepare_time(
                            current_candle.close_time)
                        trade.exit_price = current_candle.close
                        trade.contract = qty * trade.contract
                        trade.exit_signal = signal
                        CalculatorTrade(trade, data_trade)
                        strategy._cash_calc(trade)
                        strategy.closed_positions.append(trade)
                        if qty < 1:
                            # Update contract if qty is less than 1 in position of open_positions
                            trade.contract = (1-qty) * trade.contract
                        else:
                            strategy.open_positions.remove(trade)
                        strategy.cash_series = pd.concat([
                            strategy.cash_series,
                            pd.Series(data=strategy._cash,
                                    index=[current_candle.close_time])
                        ])

    @staticmethod
    def _round_time(time: int) -> datetime:
        """
        Round time to the nearest 1 second.
        
        Description:
            This function is written because when the strategy wants to open a position, it opens with the closing time of the previous candlestick, which is actually slightly shorter than the opening time of the actual candlestick, so to compensate for this difference, this function is set to 1 Rounds in seconds.
        """

        return pd.to_datetime(time, unit="ms").round("1s")

    @staticmethod
    def _convert_time(time: datetime) -> int:
        """
        Convert time to milliseconds.
        """
        return time.timestamp() * 1000

    def _prepare_time(self, time: int) -> int:
        """
        Prepare time to be used in the strategy.
        """
        return self._convert_time(self._round_time(time))

    def _set_data(strategy, data: DataHandler = None):
        """Convert the data to DataHandler object and set the data to the StrategyTester.
        
        Parameters
        ----------
        data: DataFrame
            The data that you want to test the strategy with.
        """
        if data is None:
            data = DataHandler(interval=strategy.interval, months=1).data
        else:
            data = DataHandler(data=data).data
        # data = data.reset_index(drop=True)
        data.index = data.date
        strategy.data = data
        strategy.open = data.open
        strategy.high = data.high
        strategy.low = data.low
        strategy.close = data.close
        strategy.volume = data.volume
        strategy.last_candle = data.date.iloc[-1]

    @staticmethod
    def _set_commission(commission: float):
        """ Set the commission for the strategy.
        
        Parameters
        ----------
        commission: float
            The commission for the strategy.
            
        Returns
        -------
        float
            The commission for the strategy.
        """
        commission = commission / 100
        return commission

    def _commission_calc(strategy, qty: float):
        """
        Calculate the commission for the trade.
        
        Parameters
        ----------
        qty: float
            The quantity of the trade.
        """
        commission_paid = strategy._commission * qty * strategy._cash
        # Subtract the commission from the cash

        strategy._cash -= commission_paid
        strategy.commission_paid += commission_paid

    def _cash_calc(strategy, trade: Trade):
        """ Calculate the cash for the trade.
        Parameters
        ----------
        trade: Trade
            The trade that you want to calculate the cash for.
        """
        received = trade.exit_price if trade.type == "long" else (
            2 * trade.entry_price) - trade.exit_price
        received_ = trade.contract * received
        commission = received_ * strategy._commission
        strategy._cash += received_ - commission
        strategy.commission_paid += commission

    def _contract_calc(strategy, qty: float):
        """
        Calculate the contract for the trade.
        
        Parameters
        ----------
        qty: float
            The quantity of the trade.
        """
        current_candle = strategy._current_candle_calc()
        if strategy.contract:
            contract = qty
            strategy._cash -= qty * current_candle.close
        else:
            contract = (qty * strategy._cash) / current_candle.close
            # Subtract the contract from the cash
            strategy._cash -= qty * strategy._cash
        return contract

    def _current_candle_calc(strategy):
        """
        Calculate the current candle for the strategy.
        """
        current_candle = strategy.data.loc[strategy.current_candle]
        return current_candle

    def _validate_qty(self, qty: float, trade: Trade = None):
        """
        Validate the quantity of the trade.

        Parameters
        ----------
        qty: float
            The quantity of the trade.
        """
        current_frame = inspect.currentframe()
        cal_frame = inspect.getouterframes(current_frame, 2)
        caller = cal_frame[1][3]

        if not qty > 0:
            raise ValueError(
                "The quantity of the trade must be greater than 0.")
        if self.contract:
            if caller == "exit":
                if qty > trade.contract:
                    raise ValueError(
                        "The quantity of the trade must be less than or equal to the contract.")
                else:
                    return qty
            # Check qty is not greater than the contract of cash
            current_candle = self._current_candle_calc()
            my_contract = self.cash/current_candle.close
            if qty > my_contract:
                raise ValueError(
                    "The quantity of the trade must be less than the contract of cash.")
            return qty
        
        if caller == "exit":
            if qty > 1:
                raise ValueError(
                    "The quantity of the trade must be less than 1.")
        if qty > 1:
            qty = qty / self._cash
            if qty > 1:
                raise ValueError(
                    "The quantity of the trade must be less than the cash.")
        return qty

    def list_of_trades(strategy) -> list:
        """List of trades.
        
        Returns
        -------
        list
            The list of all the open trades and closed trades.
        """
        trades = pd.DataFrame(strategy.closed_positions +
                              strategy.open_positions)
        trades.entry_date = pd.to_datetime(trades.entry_date,
                                           unit="ms").round("1s")
        trades.exit_date = pd.to_datetime(trades.exit_date,
                                          unit="ms").round("1s")
        return trades

    @property
    def backtest(strategy) -> dict:
        """
        Calculate the backtest of the strategy.
        
        Returns
        -------
        dict
            The backtest of the strategy.
        """
        trades = pd.DataFrame(strategy.closed_positions +
                              strategy.open_positions)
        if strategy.closed_positions:
            back_test = Backtest(trades, strategy.data,
                                 strategy._initial_capital)
            return back_test
        else:
            return "There are no closed positions."

    @staticmethod
    def insert_sheet(strategy, sheet: Sheet, results_objs: dict):
        """
        Insert the backtest result to the sheet.
        
        Parameters
        ----------
        sheet: Sheet
            The sheet that you want to insert the backtest result to.
        result: dict
            The backtest result that you want to insert to the sheet.
        """
        sheet = Sheet(sheet.sheet.title,
                      sheet.service_account,
                      sheet.email,
                      worksheet_name=re.sub("_.*", "", sheet.worksheet.title))
        results = []
        for column, result in results_objs.items():
            backtest_result = result.values()
            print(sheet._serialize([[str(column)] + list(backtest_result)]))
            results.append()
            sheet_id = sheet.sheet.id
            worksheet_id = sheet.worksheet.id
            strategy.links_results[
                column] = '=HYPERLINK("https://docs.google.com/spreadsheets/d/{}/edit#gid={}", "{}")'.format(
                    sheet_id, worksheet_id, result["net_profit_percent"])
        sheet.worksheet.append_rows(results)

    def periodic_calc(strategy,
                      freq: str = None,
                      start_date: str = None,
                      end_date: str = None,
                      sheet: Sheet = None) -> dict:
        """
        Calculate the periodic returns of the strategy.
        
        Description
        -----------
        After the strategy is tested, if you want to calculate the periodic returns of the strategy, you can use this function.
        
        Parameters
        ----------
        days: int
            The number of days that you want to calculate the periodic returns for.(default: 30 days)
        sheet: gspread.Spreadsheet
            The sheet that you want to save the results to.
            
        Returns
        -------
        results : dict
            The periodic returns of the strategy.       
        """
        if freq and not isinstance(freq, str):
            raise ValueError("The days must be an string(e.g. '1D', '1W', '1M', '1Y').")

        trades = pd.DataFrame(strategy.closed_positions)
        if trades.empty:
            return None
        periodic_obj = PeriodicCalc(initial_capital=strategy._initial_capital,
                                    trades=trades,
                                    data=strategy.data,
                                    freq=freq,
                                    start_date=start_date,
                                    end_date=end_date)

        results_objs = periodic_obj.results

        if sheet:
            thread = Thread(target=strategy.insert_sheet,
                            args=(strategy, sheet, results_objs))
            strategy.threads_sheet.append(thread)

        return results_objs

    def plot_initial_capital(strategy):
        strategy.cash_series.index = pd.to_datetime(strategy.cash_series.index,
                                                    unit="ms")
        strategy.cash_series.plot(label="Initial Capital Chart")
