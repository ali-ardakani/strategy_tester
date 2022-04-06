from pandas_ta_supplementary_libraries import *
import pandas_ta as ta
import  pandas as pd

class Indicator:
    
    def __init__(self, data) -> None:
        self.count = 0
        in_position = False
        long_top = 0
        long_bot = 0
        long_diff = 0
        short_top = 0
        short_bot = 0
        short_diff = 0
        long_trade = False
        short_trade = False
        
        # Parameters
        self.reset_stdev = 65
        self.reset_counter_to = 245
        self.take_profit_stop_loss = 1.1
        entry_stdev = 90
        long_ma_max  = 1000
        short_ma_min = -20
        
        self.open = data['open']
        self.high = data['high']
        self.low = data['low']
        close = data['close']
        
        stdev20 = ta.stdev(self.close, 20)*10000/ta.sma(self.close, 9)
        sma100  = ta.sma(self.close,100)
        sma500  = ta.sma(self.close,500)
        sma_cond_long= (1000*(sma500 - sma100)/sma500)<long_ma_max
        sma_cond_short= (1000*(sma500 - sma100)/sma500)>short_ma_min
        
        diff_top_bot = stdev20.apply(self.diff_calc, axis=1)

        same_highest_cond = diff_top_bot["top"] <= diff_top_bot["top"].shift(5)
        same_lowest_cond = diff_top_bot["bot"] >= diff_top_bot["bot"].shift(5)

        entry_condition = stdev20 <= entry_stdev
        long_entry_cond = (close <= diff_top_bot["bot"] + 0.2 * diff_top_bot["diffrent_top_bot"]) & same_lowest_cond & entry_condition & sma_cond_long
        short_entry_cond = (close >= diff_top_bot["bot"] + 0.8 * diff_top_bot["diffrent_top_bot"]) & same_highest_cond & entry_condition & sma_cond_short
        self.conditions = pd.concat([long_entry_cond, short_entry_cond, diff_top_bot, close], axis=1).rename(columns={0: "long_entry_cond", 1: "short_entry_cond"})
        
        
    def diff_calc(self, row):
        if row>=self.reset_stdev:
            self.count = self.reset_counter_to
        elif self.count>0:
            self.count -= 1
            
        row["top"] = highest(self.high, 250-self.count, row)
        row["bot"] = lowest(self.low, 250-self.count, row)
        row["diffrent_top_bot"] = row["top"] - row["bot"]
        return row
            
    
    