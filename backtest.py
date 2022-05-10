from unittest import result
import pandas as pd
import numpy as np

class Backtest:
    """ Class to backtest a strategy

    Attributes:
        trades (pd.DataFrame): Dataframe with trades
        trades including:
            type (str): Type of trade
            entry_date (float): Entry date of trade
            exit_date (float): Exit date of trade
            entry_price (float): Entry price of trade
            exit_price (float): Exit price of trade
            entry_signal (str): Entry signal of trade
            exit_signal (str): Exit signal of trade
            contract (float): Contract of trade
            profit (float): Profit of trade
            profit_percent (float): Profit percentage of trade
            cum_profit (float): Cumulative profit of trade
            cum_profit_percent (float): Cumulative profit percentage of trade
            run_up (float): Run up of trade
            draw_down (float): Draw down of trade
            bars_traded (int): Number of bars traded

    """
    def __init__(self, trades:pd.DataFrame, candles:pd.DataFrame, initial_capital:float):
        self.trades = self._validate_trades(trades)
        self.initial_capital = initial_capital
        if self._validate_candles(candles):
            self.start_candle = candles.iloc[0]
            self.end_candle = candles.iloc[-1]
        

    @staticmethod
    def profit(trades:pd.Series) -> float:
        """ Calculate profit of trade

        Args:
            trades (pd.Series): Series with trades

        Returns:
            float: Profit of trade
        """
        profit = trades.profit * trades.contract
        return profit.sum(axis=0)
    
    @property
    def net_profit(self) -> float:
        """ Calculate net profit of strategy

        Returns:
            float: Net profit of strategy
        """
        net_profit = self.profit(self.trades)
        return net_profit
    
    @property
    def net_profit_percent(self) -> float:
        """ Calculate net profit percentage of strategy

        Returns:
            float: Net profit percentage of strategy
        """
        net_profit_percent = self.percentage_compared_to_initial_capital(self.net_profit)
        return net_profit_percent
    
    @property
    def gross_profit(self) -> float:
        """ Calculate gross profit of strategy

        Returns:
            float: Gross profit of strategy
        """
        gross_profit = self.profit(self.trades[self.trades.profit > 0])
        return gross_profit
    
    @property
    def gross_profit_percent(self) -> float:
        """ Calculate gross profit percentage of strategy

        Returns:
            float: Gross profit percentage of strategy
        """
        gross_profit_percent = self.percentage_compared_to_initial_capital(self.gross_profit)
        return gross_profit_percent
    
    @property
    def gross_loss(self) -> float:
        """ Calculate gross loss of strategy

        Returns:
            float: Gross loss of strategy
        """
        gross_loss = self.profit(self.trades[self.trades.profit <= 0])
        return gross_loss
    
    @property
    def gross_loss_percent(self) -> float:
        """ Calculate gross loss percentage of strategy

        Returns:
            float: Gross loss percentage of strategy
        """
        gross_loss_percent = self.percentage_compared_to_initial_capital(self.gross_loss)
        return gross_loss_percent
    
    @property
    def max_draw_down(self) -> float:
        """ Calculate maximum draw down of strategy

        Returns:
            float: Maximum draw down of strategy
        """
        draw_down = self.trades.draw_down.min()
        return draw_down
    
    @property
    def min_draw_down(self) -> float:
        """ Calculate minimum draw down of strategy

        Returns:
            float: Minimum draw down of strategy
        """
        draw_down = self.trades.draw_down.min()
        return draw_down
    
    @property
    def buy_and_hold_return(self) -> float:
        """ Calculate buy and hold return of strategy

        Returns:
            float: Buy and hold return of strategy
        """
        buy_and_hold_return = self.end_candle.close - self.start_candle.open
        return buy_and_hold_return
    
    @property
    def buy_and_hold_return_percent(self) -> float:
        """ Calculate buy and hold return percentage of strategy

        Returns:
            float: Buy and hold return percentage of strategy
        """
        buy_and_hold_return_percent = self.buy_and_hold_return*100/self.start_candle.open
        return buy_and_hold_return_percent

    @property
    def profit_factor(self) -> float:
        """ Calculate profit factor of strategy

        Returns:
            float: Profit factor of strategy
        """
        profit_factor = self.gross_profit / abs(self.gross_loss) if self.gross_loss != 0 else self.gross_profit
        return profit_factor
    
    @property
    def max_contract_held(self) -> float:
        """ Calculate maximum contract held of strategy

        Returns:
            float: Maximum contract held of strategy
        """
        max_contract_held = self.trades.contract.max()
        return max_contract_held
    
    @property
    def total_closed_trades(self) -> int:
        """ Calculate total closed trades of strategy

        Returns:
            int: Total closed trades of strategy
        """
        total_closed_trades = self.trades[~pd.isna(self.trades.exit_date)].shape[0]
        return total_closed_trades
    
    @property
    def total_open_trades(self) -> int:
        """ Calculate total open trades of strategy

        Returns:
            int: Total open trades of strategy
        """
        total_open_trades = self.trades.exit_date.isna().sum()
        return total_open_trades
    
    @property
    def number_wining_trades(self) -> int:
        """ Calculate number of winning trades of strategy

        Returns:
            int: Number of winning trades of strategy
        """
        number_wining_trades = self.trades[self.trades.profit > 0].shape[0]
        return number_wining_trades
    
    @property
    def number_losing_trades(self) -> int:
        """ Calculate number of losing trades of strategy

        Returns:
            int: Number of losing trades of strategy
        """
        number_losing_trades = self.trades[self.trades.profit <= 0].shape[0]
        return number_losing_trades
    
    @property
    def percent_profitable(self) -> float:
        """ Calculate percent profitable of strategy

        Returns:
            float: Percent profitable of strategy
        """
        percent_profitable = self.number_wining_trades * 100 / abs(self.total_closed_trades) if self.total_closed_trades != 0 else 0
        return percent_profitable
    
    @property
    def avg_trade(self) -> float:
        """ Calculate average trade of strategy

        Returns:
            float: Average trade of strategy
        """
        avg_trade = (self.trades.profit * self.trades.contract).mean()
        return avg_trade
    
    @property
    def avg_trade_percent(self) -> float:
        """ Calculate average trade percentage of strategy

        Returns:
            float: Average trade percentage of strategy
        """
        avg_trade_percent = self.trades.profit_percent.mean()
        return avg_trade_percent
    
    @property
    def avg_wining_trade(self) -> float:
        """ Calculate average winning trade of strategy

        Returns:
            float: Average winning trade of strategy
        """
        win_profit = self.trades[self.trades.profit > 0]
        avg_wining_trade = (win_profit.profit * win_profit.contract).mean()
        return avg_wining_trade
    
    @property
    def avg_wining_trade_percent(self) -> float:
        """ Calculate average winning trade percentage of strategy

        Returns:
            float: Average winning trade percentage of strategy
        """
        avg_wining_trade_percent = self.trades[self.trades.profit_percent > 0].profit_percent.mean()
        return avg_wining_trade_percent
    
    @property
    def avg_losing_trade(self) -> float:
        """ Calculate average losing trade of strategy

        Returns:
            float: Average losing trade of strategy
        """
        lose_profit = self.trades[self.trades.profit <= 0]
        avg_losing_trade = (lose_profit.profit * lose_profit.contract).mean()
        return avg_losing_trade
    
    @property
    def avg_losing_trade_percent(self) -> float:
        """ Calculate average losing trade percentage of strategy

        Returns:
            float: Average losing trade percentage of strategy
        """
        avg_losing_trade_percent = self.trades[self.trades.profit_percent <= 0].profit_percent.mean()
        return avg_losing_trade_percent
    
    @property
    def ratio_avg_win_divide_avg_lose(self) -> float:
        """ Calculate ratio average winning trade divide average losing trade of strategy

        Returns:
            float: Ratio average winning trade divide average losing trade of strategy
        """
        ratio_avg_win_divide_avg_lose = self.avg_wining_trade / abs(self.avg_losing_trade) if self.avg_losing_trade != 0 else 0
        return ratio_avg_win_divide_avg_lose
    
    @property
    def largest_wining_trade(self) -> float:
        """ Calculate largest winning trade of strategy

        Returns:
            float: Largest winning trade of strategy
        """
        largest_wining_trade = self._largest_wining_trade()
        return largest_wining_trade.profit * largest_wining_trade.contract
    
    @property
    def largest_wining_trade_percent(self) -> float:
        """ Calculate largest winning trade percent of strategy

        Returns:
            float: Largest winning trade percent of strategy
        """
        largest_wining_trade = self._largest_wining_trade()
        return largest_wining_trade.profit_percent
    
    @property
    def largest_lossing_trade(self) -> float:
        """ Calculate largest losing trade of strategy

        Returns:
            float: Largest losing trade of strategy
        """
        largest_lossing_trade = self._largest_lossing_trade()
        return largest_lossing_trade.profit * largest_lossing_trade.contract
    
    @property
    def largest_lossing_trade_percent(self) -> float:
        """ Calculate largest losing trade percent of strategy

        Returns:
            float: Largest losing trade percent of strategy
        """
        largest_lossing_trade = self._largest_lossing_trade()
        return largest_lossing_trade.profit_percent
    
    @property
    def avg_bars_in_trade(self) -> float:
        """ Calculate average bars in trade of strategy

        Returns:
            float: Average bars in trade of strategy
        """
        avg_bars_in_trade = self.trades.bars_traded.mean()
        return avg_bars_in_trade
    
    @property
    def avg_bars_in_wining_trade(self) -> float:
        """ Calculate average bars in winning trade of strategy

        Returns:
            float: Average bars in winning trade of strategy
        """
        avg_bars_in_wining_trade = self.trades[self.trades.profit > 0].bars_traded.mean()
        return avg_bars_in_wining_trade
    
    @property
    def avg_bars_in_losing_trade(self) -> float:
        """ Calculate average bars in losing trade of strategy

        Returns:
            float: Average bars in losing trade of strategy
        """
        avg_bars_in_losing_trade = self.trades[self.trades.profit <= 0].bars_traded.mean()
        return avg_bars_in_losing_trade
    
    @staticmethod
    def _validate_trades(trades:pd.DataFrame) -> pd.DataFrame:
        """ Validate trades
        
        Args:
            trades (pd.DataFrame): Dataframe with trades
        
        Returns:
            pd.DataFrame: Dataframe with trades
        """
        # Check trades not empty
        if trades.empty:
            raise ValueError("Trades are empty")
        
        # Check trades have all required columns
        required_columns = ['type', 'entry_date', 'exit_date', 'entry_price', 'exit_price', 'entry_signal', 'exit_signal', 'contract', 'profit', 'profit_percent', 'cum_profit', 'cum_profit_percent', 'run_up', 'draw_down', 'bars_traded']
        wrong_columns = [column for column in required_columns if column not in trades.columns]
        if wrong_columns:
            raise ValueError(f"Trades are missing columns: {wrong_columns}")

        return trades
    
    @staticmethod
    def _validate_candles(candles:pd.DataFrame) -> pd.DataFrame:
        """ Validate candles
        
        Args:
            candles (pd.DataFrame): Dataframe with candles
        
        Returns:
            pd.DataFrame: Dataframe with candles
        """
        # Check candles not empty
        if candles.empty:
            raise ValueError("Candles are empty")
        
        # Check candles have all required columns
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        wrong_columns = [column for column in required_columns if column not in candles.columns]
        if wrong_columns:
            raise ValueError(f"Candles are missing columns: {wrong_columns}")

        return True
    
    @staticmethod
    def _initial_capital(trades) -> float:
        """ Calculate initial capital of strategy

        Returns:
            float: Initial capital of strategy
        """
        first_trade = trades.iloc[0]
        initial_capital = first_trade.entry_price * first_trade.contract
        return initial_capital
        
    def _largest_wining_trade(self) -> float:
        """ Calculate largest winning trade of strategy

        Returns:
            float: Largest winning trade of strategy
        """
        largest_wining_trade = self.trades.loc[self.trades.profit_percent.idxmax()]
        return largest_wining_trade
    
    def _largest_lossing_trade(self) -> float:
        """ Calculate largest losing trade of strategy

        Returns:
            float: Largest losing trade of strategy
        """
        largest_lossing_trade = self.trades.loc[self.trades.profit_percent.idxmin()]
        return largest_lossing_trade
    
    def percentage_compared_to_initial_capital(self, src:float) -> float:
        """ Calculate percentage compared to initial capital of strategy

        Args:
            src (float): Source value
            initial_capital (float): Initial capital of strategy
            
        Returns:
            float: Percentage compared to initial capital of strategy
        """
        percentage_compared_to_initial_capital = (src / self.initial_capital) * 100
        return percentage_compared_to_initial_capital
    
    @property
    def result(self):
        """Get result of strategy

        Returns:
            dict: Return all attributes of strategy.
        """
        result = {
            'initial_capital':self.initial_capital, 
            'net_profit':self.net_profit, 
            'net_profit_percent':self.net_profit_percent,
            'gross_profit':self.gross_profit,
            'gross_profit_percent':self.gross_profit_percent,
            'gross_loss':self.gross_loss,
            'gross_loss_percent':self.gross_loss_percent,
            'max_draw_down':self.max_draw_down,
            'buy_and_hold_return': self.buy_and_hold_return,
            'buy_and_hold_return_percent':self.buy_and_hold_return_percent,
            'profit_factor':self.profit_factor,
            'max_contract_held':self.max_contract_held,
            'total_closed_trades':self.total_closed_trades,
            'total_open_trades':self.total_open_trades,
            'number_wining_trades':self.number_wining_trades,
            'number_losing_trades':self.number_losing_trades,
            'percent_profitable':self.percent_profitable,
            'avg_trade':self.avg_trade,
            'avg_trade_percent':self.avg_trade_percent,
            'avg_wining_trade':self.avg_wining_trade,
            'avg_wining_trade_percent':self.avg_wining_trade_percent,
            'avg_losing_trade':self.avg_losing_trade,
            'avg_losing_trade_percent':self.avg_losing_trade_percent,
            'largest_wining_trade':self.largest_wining_trade,
            'largest_wining_trade_percent':self.largest_wining_trade_percent,
            'largest_lossing_trade':self.largest_lossing_trade,
            'largest_lossing_trade_percent':self.largest_lossing_trade_percent,
            'ratio_avg_win_divide_avg_lose':self.ratio_avg_win_divide_avg_lose,
            'avg_bars_in_trade':self.avg_bars_in_trade,
            'avg_bars_in_wining_trade':self.avg_bars_in_wining_trade,
            'avg_bars_in_losing_trade':self.avg_bars_in_losing_trade,
        }

        return result