from strategy_tester.models import Trade
from strategy_tester.backtest import Backtest
import pandas as pd
import numpy as np

class PeriodicCalc:
    """
    PeriodicCalc is created for calculating the backtest for the given period.
    
    Attributes:
        backtests: A dictionary of backtests for each period
        results: A dictionary of results for each period
    
    
    """
    def __init__(self, initial_capital:float, trades:pd.DataFrame, data:pd.DataFrame, freq:str=None, start_date:str=None, end_date:str=None):
        self.initial_capital = initial_capital
        self.trades = self._valid_trades(trades)
        self.data = self._valid_data(data)
        self.freq = freq if freq else len(self.data)
        self.start_date = start_date if start_date else None
        self.end_date = end_date if end_date else self.data.date.max() # Get the last date
        self._backtests = {}
        self._results = {}
        self.backtest_calc()
        
    @property
    def results(self):
        """Get the results of the backtests"""
        return self._results
    
    @property
    def backtests(self):
        """Get the backtests"""
        return self._backtests

    @staticmethod
    def _valid_trades(trades:pd.DataFrame):
        """Validate the trades"""
        if trades.empty:
            raise ValueError("No trades found")
        if not isinstance(trades, pd.DataFrame):
            raise TypeError("The trades must be a pandas DataFrame")
        if not isinstance(trades["entry_date"], np.datetime64):
            trades["entry_date"] = pd.to_datetime(trades["entry_date"], unit="ms").round("1s")
        if not isinstance(trades["exit_date"], np.datetime64):
            trades["exit_date"] = pd.to_datetime(trades["exit_date"], unit="ms").round("1s")
        return trades
 
    
    def _valid_data(self, data:pd.DataFrame, key:str='date'):
        """Check if the data is valid"""
        if data.empty:
            raise ValueError('No data available')
        elif not isinstance(data[key], np.datetime64):
            data[key] = pd.to_datetime(data[key], unit="ms").round("1s")
            
        return data
        
    def backtest_calc(self):
        """Calculate the backtest results for the given trades"""
        
        if self.start_date:
            self.data = self.data[self.data.date >= self.start_date]

        steps = self.data.groupby(pd.Grouper(key='date', freq=self.freq))
        for step in steps:
            # Get the trades for the current step
            trades = self._get_trades(data=step[1])
            if trades.empty:
                continue
            
            index_first_trade = trades.iloc[0].name
            if index_first_trade != 0:
                initial_capital = self._initial_capital(self.trades.iloc[trades.iloc[0].name-1])
            else:
                initial_capital = self.initial_capital
            trades.to_pickle("trades.pkl")
            # Create the Backtest object
            backtest = self._calc_backtest(trades, step[1], initial_capital)
            
            self._backtests[step[0]] = backtest
            self._results[step[0]] = backtest.result
            
    def _grouping(self):
        """Group the data by days"""
        return self.data.groupby(pd.Grouper(key='date', freq=self.freq))
    
    def _get_trades(self, data):
        """Get the trades for the given data"""
        return self.trades[self.trades.entry_date.isin(data.date)]
    
    @staticmethod
    def _initial_capital(trade):
        return trade.contract * trade.exit_price
    
    @staticmethod
    def _calc_backtest(trades:pd.DataFrame, data:pd.DataFrame, initial_capital:float) -> Backtest:
        """Create Backtest object"""
        return Backtest(trades=trades, candles=data, initial_capital=initial_capital)
            
        
