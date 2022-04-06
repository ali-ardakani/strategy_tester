from xmlrpc.client import Boolean
import pandas as pd

def chunks(df_base:pd.DataFrame, n:int) -> list:
    """
    Splits a dataframe into chunks of size n.
    """
    
    list_split = []
    for num in range(0, len(df_base), n):
        candles = df_base[num:num + n]
        candle = {
            'date': candles['date'].iat[0],
            'open': candles['open_price'].iat[0],
            'high': candles.high_price.max(),
            'low': candles.low_price.min(),
            'close': candles['close_price'].iat[-1],
            'volume': candles.volume.sum(),
        }
        for i in range(0, len(candles)):
            list_split.append(candle)
    
    df = pd.DataFrame(list_split)
    
    return df
def get_chunks(source:pd.Series, num_slice:int, date=False, fill_gaps=True) -> list:
    """
    Splits a series into chunks of size n.
    :param source: The source series.
    :param num_slice: The number of slices.
    :param date: If True, the date of the first candle of the chunk will be the date of the first candle of the source series.
    :param fill_gaps: If False, the gaps between the candles of the source series will be dropped.
    :return: The dataframe of the chunks.
    """
    
    list_split = []
    for num in range(0, len(source), num_slice):
        src = source[num:num + num_slice]
        if date:
            candle = {
                'date': src.iat[0],
                'src': src.iat[0],
            }
        else:
            candle = {
                'src': src.iat[0],
            }
        if fill_gaps:
            for i in range(0, len(src)):
                list_split.append(candle)
        else:
            list_split.append(candle)
    
    df = pd.DataFrame(list_split)
    
    return df
    
