# strategy tester
## Installation
``` bash
pip install -r requirements.txt
```
## Usage
Here a snippet of the strategy tester:

```python
from strategy_tester import Strategy
from strategy_tester.indicator import Indicator
import strategy_tester.pandas_ta_supplementary_libraries as ta
import pandas as pd

class SimpleStrategy(Strategy):
    """
    SimpleStrategy is a Strategy class that implements a simple strategy.
    """
    
    def __init__(strategy, **kwargs) -> None:
        super().__init__(**kwargs)

    def indicators(strategy) -> None:
        """Set the indicators for the strategy."""
        # Create indicator for multiprocessing
        sma = Indicator("sma", ta.sma, args=(strategy.close, strategy.sma_len_input))
        # Add indicator to the ParallelIndicator
        strategy.add(sma)


    def condition(strategy):
        # Create conditions
        entry_long_cond = (strategy.close > strategy.sma).rename("entry_long_cond")
        entry_short_cond = (strategy.close < strategy.sma).rename("entry_short_cond")
        
        # Set conditions to use in the trade_calc function
        strategy.conditions = entry_long_cond, entry_short_cond                        
                        
    def trade_calc(strategy, row):
        # Check conditions in each candle
        if row.entry_long_cond:
            # Exit short position
            strategy.exit("short")
            # Enter long position
            strategy.entry("long", "long")
            
        elif row.entry_short_cond:
            # Exit long position
            strategy.exit("long")
            # Enter short position
            strategy.entry("short", "short")

# Get btcbusd data two months ago
data = DataHandler(symbol="BTCBUSD", interval="5m", months=2).data
# Create instance of SimpleStrategy
strategy = SimpleStrategy()
# Set the data for the strategy
strategy.setdata(data)
# Run the strategy tester
strategy.run()
# Get back test results
backtest_results = strategy.result()
# Get list of trades
list_of_trades = strategy.list_of_trades()
# Get list of open positions
list_of_open_positions = strategy.open_positions
# Get list of closed positions
list_of_closed_positions = strategy.closed_positions
# Plot the indicators
strategy.plot_indicators([{"value": ta.wma(strategy.close, 10), "color": "red"}, {"value": strategy.sma, "color": "blue"}])
# Get periodic backtest results in every month
periodic_backtest_results = strategy.periodic_calc(days=30)
```

## Repository
[Github](https://github.com/ali-ardakani/strategy_tester)
[pypi](https://pypi.org/project/strategy-tester/)