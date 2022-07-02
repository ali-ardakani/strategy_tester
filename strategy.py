from strategy_tester import StrategyTester
from strategy_tester.backtest import Backtest
from .indicator import IndicatorsParallel
import pandas as pd
from threading import Thread
import os
from .sheet import Sheet
from datetime import datetime
import plotly.graph_objects as go


class Strategy(StrategyTester, IndicatorsParallel):
    """
    StrategyTester is a class that tests a strategy.
    StrategyTester can be used to test a strategy in financial markets.
    """
    
    _permission_long = True
    _permission_short = True

    @property
    def conditions(strategy):
        return strategy._conditions

    @conditions.setter
    def conditions(strategy, *conditions):
        parts = [strategy.data]
        parts.extend(*conditions)
        strategy._conditions = pd.concat(parts, axis=1)

    @property
    def hlcc4(strategy):
        _hlcc4 = strategy.__dict__.get("_hlcc4", None)
        if _hlcc4 is None:
            strategy._hlcc4 = (strategy.high + strategy.low + strategy.close + strategy.close)/4
        return strategy._hlcc4

    def __init__(strategy, **kwargs) -> None:
        """ StrategyTester constructor.

        Description:
            If you want to test a strategy, you need to create a StrategyTester object.
            Then you can set the strategy and the data.
            All variables that need to be set are set in the constructor.
        """
        pass
        
    def setdata(strategy, data: pd.DataFrame=None):
        """ Set the data for the strategy tester.
        Parameters
        ----------
        data: DataFrame
            The data that you want to test the strategy with.
        """
        strategy._set_data(data)
        
    def set_parameters(strategy, **kwargs):
        """Set the initial parameters for the strategy.
        
        Description:
            This function is used to set the initial parameters for the strategy.
        Parameters
        ----------
        kwargs: dict
            The parameters that you want to set.
        """
        parameters = []
        for key, value in kwargs.items():
            if value == "open":
                value = strategy.open
            elif value == "high":
                value = strategy.high
            elif value == "low":
                value = strategy.low
            elif value == "close":
                value = strategy.close
            elif value == "hlcc4":
                value = strategy.hlcc4
            parameters.append((key, value))
            strategy.__setattr__(key, value)
        strategy.parameters = tuple(parameters)
            
    def _set_cache(strategy):
        """
        Set the cache for the strategy.
        """
        if not os.path.exists('./cache/'):
            os.makedirs('./cache/')
        start_time = strategy.data.iloc[0].date
        end_time = strategy.data.iloc[-1].date
        interval = strategy.interval
        strategy.conditions.to_pickle('./cache/{}_{}_{}_{}.pickle'.format(strategy.__class__.__name__, interval, start_time, end_time))
        
        
    def _get_cache(strategy):
        start_time = strategy.data.iloc[0].date
        end_time = strategy.data.iloc[-1].date
        interval = strategy.interval
        path_cache = './cache/{}_{}_{}_{}.pickle'.format(strategy.__class__.__name__, interval, start_time, end_time)
        if os.path.exists(path_cache):
            strategy._conditions = pd.read_pickle(path_cache)
            return True
        else:
            return False
        
    def entry(strategy, signal: str, direction: str, qty: float = 1, limit: float = None, stop: float = None, comment: str = None):
        if strategy._permission_long and signal == "long":
            return super().entry(signal, direction, qty, limit, stop, comment)
        elif strategy._permission_short and signal == "short":
            return super().entry(signal, direction, qty, limit, stop, comment)
        
    def indicators(strategy) -> None:
        """
        Description:
            This function is called once at the beginning of the strategy.
            You can use this function to set the initial values of your indicators.
        
        Example:
            If you want to set your indicator, you can do it like this:
            ```
                hma500 = Indicator("hma500", ta.hma, strategy.close, timeperiod=500)
                self.add(hma500)
            ```
            or you want to set multiple indicators, you can do it like this:
            ```
                hma500 = Indicator("hma500", ta.hma, strategy.close, timeperiod=500)
                sma200 = Indicator("sma200", ta.sma, strategy.close, timeperiod=200)
                cross = Indicator("cross", crossunder, args=(hma500, sma200), wait=False)
                self.add(hma500, sma200, cross)
        """
        pass
    
    def condition(strategy):
        """
        Description:
            This function is called after the indicators are calculated.
            You can use this function to set the conditions for the indicators.
        
        Example:
            ```
                entry_long = strategy.hma500 > strategy.sma200
                entry_short = strategy.hma500 < strategy.sma200
                strategy.conditions = entry_long, entry_short
            ```
        """
        pass
    
    def trade(strategy, row):
        """Execute the trade for the strategy.
        
        Description
        -----------
        This function is used to execute the trade for the strategy.
        In this function, set the current candle and execute the trade_calc function.
        
        Parameters
        ----------
        row: DataFrame
            The row of the data that you want to execute the trade for.
        """
        strategy.current_candle = row.name
        strategy.trade_calc(row)
        
    def trade_calc(strategy, row):
        """Check terms and open/close positions.
        
        Description
        -----------
        All conditions for entering the position are checked.
        If the conditions are met, the position is opened.
        If the conditions are not met, the position is closed.
        
        Parameters
        ----------
        row: DataFrame
            The row of the data that you want to execute the trade for.
        """
        pass

    def _insert_main_to_sheet(strategy, sheet: Sheet, thread:Thread=None) -> None:
        """Add the main backtest result to sheet."""
        if thread:
            # Wait for all of threads created by the periodical function to finish.
            while thread.is_alive():
                pass
            
        backtest_result = strategy.backtest().values()
        if strategy.links_results:
            sheet.add_columns_names(list(strategy.links_results.keys()))
            sheet.add_row([[str(strategy.parameters)]+list(backtest_result) + list(strategy.links_results.values())])
        else:
            sheet.add_row([[str(strategy.parameters)]+list(backtest_result)])

    def add_to_sheet(strategy, sheet: Sheet) -> None:
        """Add the strategy to the sheet.
            
            Parameters
            ----------
            sheet: Sheet
                The sheet that you want to add the strategy to.
            """
        
        # Run the all of threads created by the periodical function before starting the _insert_main_to_sheet function.
        for thread in strategy.threads_sheet:
            thread.start()

        thread_main = Thread(target=strategy._insert_main_to_sheet, args=(sheet, thread))
        thread_main.start()

    # def periodic_backtest(strategy, start_date:str=None, end_date:str=None) -> dict:
    #TODO: Add the periodical backtest function.
    #     """Calculate the backtest result for the specific period.
        
    #     Description
    #     -----------
    #     This function is used to calculate the backtest result for the specific period.
    #     The backtest result is calculated by the backtest function.
    #     The backtest result is stored in the dictionary.
        
    #     Parameters
    #     ----------
    #     start_date: str
    #         The start date of the backtest.
    #     end_date: str
    #         The end date of the backtest.
        
    #     Returns
    #     -------
    #     dict
    #         The backtest result for the specific period.
    #     """
    #     if not start_date and not end_date:
    #         raise ValueError("start_date and end_date cannot be None at the same time.")

    #     start_date = datetime.strptime(start_date, '%Y-%m-%d').timestamp()*1000 if start_date else None
    #     end_date = datetime.strptime(end_date, '%Y-%m-%d').timestamp()*1000 if end_date else None

    #     if start_date:
    #         conditions = strategy.conditions[(strategy.data.date >= start_date)]
    #     if end_date:
    #         conditions = strategy.conditions[(strategy.data.date <= end_date)]

    #     new_instance = conditions
    
    @staticmethod
    def _plot(candles:pd.DataFrame, entry_date: int or pd.Timestamp=None, exit_date: int or pd.Timestamp=None, type_: str=None):
        """Plot the candles."""
        # TODO: Show more candles on both sides and distinguish the beginning and the end of the trade.
        if not isinstance(candles.index, pd.DatetimeIndex):
            candles.index = pd.to_datetime(candles.index, unit="ms").round("1s")
        if not entry_date:
            entry_date = candles.index[0]
        if not exit_date:
            exit_date = candles.index[-1]
        if not isinstance(entry_date, pd.Timestamp):
            entry_date = pd.to_datetime(entry_date, unit="ms").round("1s")
        if not isinstance(exit_date, pd.Timestamp):
            exit_date = pd.to_datetime(exit_date, unit="ms").round("1s")
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
            y_exit = candles.loc[exit_date, "high"]
            
        chart = go.Candlestick(x=candles.index,
                            open=candles.open,
                            high=candles.high,
                            low=candles.low,
                            close=candles.close)
        
        entry_arrow = go.Scatter(x=[entry_date],
                                 y=[y_entry],
                                 mode="markers",
                                 marker=dict(color=entry_color, size=10))
        exit_arrow = go.Scatter(x=[exit_date],
                                y=[y_exit],
                                mode="markers",
                                marker=dict(color=exit_color, size=10))
        data = [chart, entry_arrow, exit_arrow]
        layout = go.Layout(title=type_,
                           xaxis=dict(title="Date"),
                           yaxis=dict(title="Price"))
        fig = go.Figure(data=data, layout=layout)
        fig.show()
        
    def plot_candles(strategy, start_date:str=None, end_date:str=None) -> None:
        """Plot the candles.
        
        Description
        -----------
        This function is used to plot the candles.
        The candles are calculated by the backtest function.
        
        Parameters
        ----------
        start_date: str
            The start date of the backtest.
        end_date: str
            The end date of the backtest.
        """
        if not start_date and not end_date:
            raise ValueError("start_date and end_date cannot be None at the same time.")

        start_date = datetime.strptime(start_date, '%Y-%m-%d').timestamp()*1000 if start_date else None
        end_date = datetime.strptime(end_date, '%Y-%m-%d').timestamp()*1000 if end_date else None
        
        data = strategy.data
        data.index = pd.to_datetime(data.date, unit='ms')

        if start_date:
            data = data[(data.date >= start_date)]
        if end_date:
            data = data[(data.date <= end_date)]

        strategy._plot(data)
        
    def plot_trade(strategy, num_of_trade: int=None, start_trade: str=None):
        """Plot the trade.
        
        Description
        -----------
        This function is used to plot the trade.
        The trade is calculated by the backtest function.
        
        Parameters
        ----------
        num_of_trade: int
            The number of the trade that you want to plot.
        start_trade: str
            The start date of the trade that you want to plot.
        """
        if not num_of_trade and not start_trade:
            raise ValueError("num_of_trade and start_trade cannot be None at the same time.")
        
        trades = strategy.closed_positions + strategy.open_positions

        if num_of_trade:
            if num_of_trade > len(trades):
                raise ValueError("num_of_trade cannot be greater than the number of trades.")
            trade = trades[num_of_trade]
            
        if start_trade:
            _trades = []
            for trade in trades:
                entry_date = str(pd.to_datetime(trade.entry_date, unit="ms").round("1s"))
                if start_trade in entry_date:
                    _trades.append(trade)
                    
            if len(_trades) == 0:
                raise ValueError("start_trade cannot be found.")
            if len(_trades) > 1:
                _trades = [pd.to_datetime(trade.entry_date, unit="ms").round("1s") for trade in _trades]
                raise ValueError(f"Found {len(_trades)} trades that start with {start_trade}.\n Please choose one of the options bellow; \n {_trades}")
            
            trade = _trades[0]
            
        data = strategy.data.reset_index(drop=True)
        start_date = trade.entry_date
        end_date = trade.exit_date

        start_trade = data[(data.date >= start_date)].iloc[0].name -50 if start_date else 0
        end_trade = data[(data.date <= end_date)].iloc[-1].name +50 if end_date else len(data)
        data = data.iloc[start_trade:end_trade]
        data.index = data.date
        strategy._plot(data, entry_date=start_date, exit_date=end_date, type_=trade.type)
        
    def plot_indicators(strategy, list_of_indicators: list, start_date: str=None, end_date: str=None) -> None:
        """Plot the indicators.
        
        Parameters
        ----------
        list_of_indicators: list
            The list of the indicators that you want to plot.
            In the list, you must put the dictionary of the indicator.
            example:
            [{"name": "sma", "value": ta.sma(data.close, length=20), "color": "blue"}, {"name": "ema", "value": ta.ema(data.close, length=20), "color": "red"}]
        start_date: str
            The start date of the backtest.
        end_date: str
            The end date of the backtest.
        """
        chart = go.Candlestick(x=strategy.data.index,
                    open=strategy.data.open,
                    high=strategy.data.high,
                    low=strategy.data.low,
                    close=strategy.data.close)
        indicators = [chart]
        for indicator in list_of_indicators:
            name = indicator["name"] if "name" in indicator else indicator["value"].name
            indicators.append(go.Scatter(x=strategy.data.index,
                                         y=indicator["value"],
                                         name=name,
                                         marker=dict(color=indicator["color"])))
        layout = go.Layout(title="Indicators",
                           xaxis=dict(title="Date"),
                           yaxis=dict(title="Price"))
        fig = go.Figure(data=indicators, layout=layout)
        fig.show()
        
    def result(strategy):
        """
        Description:
            Return the backtest with the specific parameters.
        
        Returns:
            dict
                The backtest result.
        """
        backtest = strategy.backtest
        if not isinstance(backtest, Backtest):
            return pd.Series(dict(strategy.parameters))
        else:
            return pd.Series(backtest.result|dict(strategy.parameters))
        
    def just_long(self):
        """
        In this function, you can get backtest result of just long.
        
        Note:
            This function should only be called when the strategy has been ran.
        """
        trades = self.list_of_trades()
        trades_long = trades[trades.type == "long"]
        if trades_long.exit_date.dropna().empty:
            return None
        # Backtest
        backtest = Backtest(trades_long, self.data, self._initial_capital)
        return pd.Series(backtest.result|dict(self.parameters))
    
    def just_trades_long(self):
        """
        In this function, you can get series of trades of just long.
     
        Note:
            This function should only be called when the strategy is running.
        """
        trades = self.list_of_trades()
        trades_long = trades[trades.type == "long"]
        if trades_long.exit_date.dropna().empty:
            return None
        return trades_long
    
    def just_short(self):
        """
        In this function, you can get backtest result of just short.
        
        Note:
            This function should only be called when the strategy is running.
        """
        trades = self.list_of_trades()
        trades_short = trades[trades.type == "short"]
        if trades_short.exit_date.dropna().empty:
            return None
        # Backtest
        backtest = Backtest(trades_short, self.data, self._initial_capital)
        return pd.Series(backtest.result|dict(self.parameters))
    
    def just_trades_short(self):
        """
        In this function, you can get series of trades of just short.
     
        Note:
            This function should only be called when the strategy is running.
        """
        trades = self.list_of_trades()
        trades_short = trades[trades.type == "short"]
        if trades_short.exit_date.dropna().empty:
            return None
        return trades_short
    
    def only_long(self) -> "Strategy":
        """
        In this function, you can get backtest when
        the strategy is only allowed to enter long.
        
        Returns:
            Strategy
                The strategy that only enter long.

        Note:
            This function re-runs the strategy,
            except that it only has a long license.
        """
        
        self._permission_short = False
        self.run()
        return self
    
    def only_short(self) -> "Strategy":
        """
        In this function, you can get backtest when
        the strategy is only allowed to enter short.
        
        Returns:
            Strategy
                The strategy with only short license.

        Note:
            This function re-runs the strategy,
            except that it only has a short license.
        """
        self._permission_long = False
        self.run()
        return self
    
    def run(strategy):
        """Run the strategy."""
        strategy.set_init()
        strategy._init_indicator()
        strategy.indicators()
        strategy.start()
        strategy.condition()
        strategy.conditions.apply(strategy.trade, axis=1)