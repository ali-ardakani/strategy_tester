from random import seed
from strategy_tester import StrategyTester
from .indicator import IndicatorsParallel
from .encoder import NpEncoder
import pandas as pd
from threading import Thread
import os
import time
from .sheet import Sheet

class Strategy(StrategyTester, IndicatorsParallel):
    """
    StrategyTester is a class that tests a strategy.
    
    StrategyTester can be used to test a strategy in financial markets.
    """
    
        
    @property
    def conditions(strategy):
        return strategy._conditions
    
    @conditions.setter
    def conditions(strategy, *conditions):
        parts = [strategy.data]
        parts.extend(*conditions)
        strategy._conditions = pd.concat(parts, axis=1)

    def __init__(strategy) -> None:
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


    def run(strategy):
        """Run the strategy."""
        strategy.set_init()
        strategy._init_indicator()
        strategy.indicators()
        strategy.start()
        strategy.condition()
        strategy.conditions.apply(strategy.trade, axis=1)