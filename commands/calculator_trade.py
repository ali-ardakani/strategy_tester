from pandas import DataFrame
from strategy_tester.models.trade import Trade

class CalculatorTrade:
    
    def __init__(self, trade:Trade, data:DataFrame):
        """CalculatorTrade constructor.
        
        Description:
            CalculatorTrade is a class that calculates the trade.
            It calculates parameters such as the profit, the draw down, etc.
        
        Attributes:
            trade: Trade
                The trade that you want to calculate.
            data: DataFrame
                The data that you want to calculate the trade with.
        """
        trade.profit = self._profit(trade)
        trade.profit_percent = self._profit_percent(trade)
        trade.draw_down = self._draw_down(trade, data)
        trade.run_up = self._run_up(trade, data)
        trade.bars_traded = self._bars_traded(data)
        
            
    @staticmethod
    def _profit(trade:Trade) -> float:
        """
        Calculate the profit of a trade.
        Parameters
        ----------
        trade: Trade
            The trade that you want to calculate the profit of.
        
        Returns
        -------
        float
            The profit of the trade.
        """
        if trade.exit_price is not None:
            profit = trade.exit_price - trade.entry_price if trade.type == 'long' else trade.entry_price - trade.exit_price  
        else:
            profit = None
            
        return profit
    
    @staticmethod
    def _profit_percent(trade:Trade) -> float:
        """
        Calculate the profit percent of a trade.
        Parameters
        ----------
        trade: Trade
            The trade that you want to calculate the profit percent of.
        
        Returns
        -------
        float
            The profit percent of the trade.
        """
        if trade.profit is not None:
            profit_percent = trade.profit*100 / trade.entry_price
        else:
            profit_percent = None
            
        return profit_percent
    
    @staticmethod
    def _draw_down(trade:Trade, data:DataFrame) -> float:
        """
        Calculate the draw down of a trade.
        Parameters
        ----------
        trade: Trade
            The trade that you want to calculate the draw down of.
        data: DataFrame
            The data that you want to calculate the draw down with.
        
        Returns
        -------
        float
            The draw down of the trade.
        """
        if trade.type == "long":
            draw_down = (data.low.min() - data.open.iat[0])*100 / data.open.iat[0]
        else:
            draw_down = -(data.high.max() - data.open.iat[0])*100 / data.open.iat[0]
            
        return draw_down
    
    @staticmethod
    def _run_up(trade:Trade, data:DataFrame) -> float:
        """
        Calculate the run up of a trade.
        Parameters
        ----------
        trade: Trade
            The trade that you want to calculate the run up of.
        data: DataFrame
            The data that you want to calculate the run up with.
        
        Returns
        -------
        float
            The run up of the trade.
        """
        if trade.type == "long":
            run_up = (data.high.max() - data.open.iat[0])*100 / data.open.iat[0]
        else:
            run_up = -(data.low.min() - data.open.iat[0])*100 / data.open.iat[0]
        
        return run_up

    @staticmethod
    def _bars_traded(data:DataFrame) -> int:
        """
        Calculate the bars traded of a trade.
        Parameters
        ----------
        data: DataFrame
            The data that you want to calculate the bars traded with.
        
        Returns
        -------
        int
            The bars traded of the trade.
        """
        return len(data)