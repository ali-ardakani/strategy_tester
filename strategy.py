from strategy_tester import StrategyTester


class Strategy(StrategyTester):
    """
    StrategyTester is a class that tests a strategy.
    
    StrategyTester can be used to test a strategy in financial markets.
    """

    def __init__(strategy) -> None:
        """ StrategyTester constructor.

        Description:
            If you want to test a strategy, you need to create a StrategyTester object.
            Then you can set the strategy and the data.
            All variables that need to be set are set in the constructor.
        """
        super().__init__()
        strategy.data = strategy.setdata()
    
    def conditions(strategy, data: pd.DataFrame) -> bool:
        """
        This function is used to test the conditions of the strategy.
        If the conditions are met, the strategy will be executed.
        
        Parameters
        ----------
        data: DataFrame
            The data that you want to test the strategy with.
            
        Returns
        -------
        bool
            True if the conditions are met, False otherwise.
        """
        pass