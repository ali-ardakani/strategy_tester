from handler.datahandler import DataHandler
from models.trade import Trade
import pandas as pd
from commands.calculator_trade import CalculatorTrade
from backtest import Backtest

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
    
    _cash = 10000
    _initial_capital = 10000
    long = "long"
    short = "short"

    interval = "15m"
    _commission = 0.0
    # Amount of commission paid 
    commission_paid = 0
    current_candle = None
    open_positions = []
    closed_positions = []
    
        
        
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
        return strategy._interval
    
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
        
    def entry(strategy,
              signal: str,
              direction: str,
              qty: float=1,
              limit: float=None,
              stop: float=None,
              comment: str=None
              ):
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

        if strategy._cash > 0:
            strategy._commission_calc(qty)
            current_candle = strategy._current_candle_calc()
            trade = Trade(
                type=direction,
                entry_date=current_candle.close_time,
                entry_price=current_candle.close,
                entry_signal=signal,
                contract=strategy._contract_calc(qty),
                comment=comment
            )
            strategy.open_positions.append(trade)
            
    def exit(strategy,
             from_entry: str,
             signal: str=None,
             qty: float=1,
             limit: float=None,
             stop: float=None,
             comment: str=None
             ):
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
        qty = strategy._validate_qty(qty)
        if strategy.open_positions != []:
            trade = next((trade for trade in strategy.open_positions if trade.entry_signal == from_entry), None)
            if trade:
                current_candle = strategy._current_candle_calc()
                # Calculate parameters such as profit, draw down, etc.
                data_trade = strategy.data.loc[strategy.data.date.between(trade.entry_date, current_candle.close_time)]
                if not data_trade.empty:
                    trade.exit_date = current_candle.close_time
                    trade.exit_price = current_candle.close
                    trade.exit_signal = signal
                    CalculatorTrade(trade, data_trade)
                    strategy._cash_calc(trade)
                    strategy.closed_positions.append(trade)
                    strategy.open_positions.remove(trade)
                
        
    def _set_data(strategy, data: DataHandler=None):
        """Convert the data to DataHandler object and set the data to the StrategyTester.
        
        Parameters
        ----------
        data: DataFrame
            The data that you want to test the strategy with.
        """
        if data is None:
            data = DataHandler(interval=strategy.interval).data
        else:
            data = DataHandler(data=data).data
        data = data.reset_index(drop=True)
        strategy.data = data
        strategy.open = data.open
        strategy.high = data.high
        strategy.low = data.low
        strategy.close = data.close
        strategy.volume = data.volume
        
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
        commission = commission/100
        return commission
        
        
    def _commission_calc(strategy, qty:float):
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
        
    def _cash_calc(strategy, trade:Trade):
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
        
    def _contract_calc(strategy, qty:float):
        """
        Calculate the contract for the trade.
        
        Parameters
        ----------
        qty: float
            The quantity of the trade.
        """
        current_candle = strategy._current_candle_calc()
        contract = (qty * strategy._cash) / current_candle.close
        # Subtract the contract from the cash
        strategy._cash -= qty * strategy._cash
        return contract
    
    def _current_candle_calc(strategy):
        """
        Calculate the current candle for the strategy.
        """
        current_candle = strategy.data.iloc[strategy.current_candle]
        return current_candle
    
    @staticmethod
    def _validate_qty(qty: float) -> float:
        """
        Validate the quantity of the trade.
        
        Parameters
        ----------
        qty: float
            The quantity of the trade.
        """
        if not (qty>0 and qty<=1):
            raise ValueError("The quantity of the trade must be between 0 and 1.")
        return qty
        
    def list_of_trades(strategy) -> list:
        """List of trades.
        
        Returns
        -------
        list
            The list of all the open trades and closed trades.
        """
        return strategy.closed_positions + strategy.open_positions
    
    def backtest(strategy) -> dict:
        """
        Calculate the backtest of the strategy.
        
        Returns
        -------
        dict
            The backtest of the strategy.
        """
        trades = pd.DataFrame(strategy.closed_positions + strategy.open_positions)
        if strategy.closed_positions:
            back_test = Backtest(trades, strategy.data, strategy._initial_capital)
            result = back_test.result
            return result
        else:
            raise ValueError("There are no closed positions.")