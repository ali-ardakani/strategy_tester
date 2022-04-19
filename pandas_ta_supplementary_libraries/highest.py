import pandas as pd

# def highest(df:pd.Series, length:int) -> pd.Series:
#     _len = len(df)
#     result = list()
#     for i in range(1, _len+1):
#         if i < length:
#             result.append(0)
#         else:
#             res = df.loc[i-length:i-1].max()
#             result.append(res)
#     result = pd.Series(result)
#     return result

def highest(src:pd.Series, length:int, candle:int=None) -> float or pd.Series:
    """
    Returns the highest value of the last 'length' candles.

    :param candle: The current candle.
    :param src: The source series e.g. close.
    :param length: The length of the period.
    :return: The highest value of the last 'length' candles.
    """
    # Convert float to int.
    length = int(length)
    src = src.copy(deep=True)
    # Check if the length is valid.
    if length < 1:
        raise ValueError("The length must be greater than 0.")
    elif length > len(src):
        raise ValueError("The length must be smaller than the length of the source series.")
    
    if candle is not None:
        # Find the last 'length' candles from teh current candle.
        result = src.iloc[(candle+1-length):candle+1].max()
    else:
        result = src.rolling(window=length).max()
        # result.reset_index(drop=True, inplace=True)
    return result