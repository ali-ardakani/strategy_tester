# strategy tester
## Installation
``` bash
pip install -r requirements.txt
```
## Usage
Here a snippet of the strategy tester:

```python
from strategy_tester import StrategyTester
import pandas as pd
import pandas_ta as ta
from pandas_ta_supplementary_libraries import *
import numpy as np

class SimpleStrategy(StrategyTester):
    def __init__(strategy, data:pd.DataFrame):
        # Set data
        strategy.setdata(data)
        # Set all initial parameters here
        strategy.in_long = False
        strategy.in_short = False
        ma = ta.sma(strategy.close, 100).rename("ma")

        # Set constraints for the strategy
        strategy.conditions = ma,

    def trade_calc(strategy, row):
        if row.close > row.ma:
            if strategy.in_short:
                strategy.exit("short")
                strategy.in_short = False
            strategy.entry("long", "long")
            strategy.in_long = True
        elif row.close < row.ma:
            if strategy.in_long:
                strategy.exit("long")
                strategy.in_long = False
            strategy.entry("short", "short")
            strategy.in_short = True

strategy = SimpleStrategy(data)
# Run the strategy tester
strategy.run()
# Get back test results
backtest = strategy.backtest()
# Get list of trades
list_of_trades = strategy.list_of_trades()
# Get list of open positions
list_of_open_positions = strategy.open_positions
# Get list of closed positions
list_of_closed_positions = strategy.closed_positions
```