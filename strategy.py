from strategy_tester import StrategyTester
from .indicator import IndicatorsParallel
import pandas as pd
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
        for key, value in kwargs.items():
            strategy.__setattr__(key, value)
        
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
    
    def run(strategy):
        """Run the strategy."""
        strategy._set_init()
        strategy._set_init_indicators()
        strategy.indicators()
        strategy.start()
        strategy.condition()
        strategy.conditions.apply(strategy.trade, axis=1)