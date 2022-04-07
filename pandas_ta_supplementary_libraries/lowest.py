import pandas as pd

# def lowest(src:pd.Series, length:int) -> pd.Series:
#     """
#     Returns the all-time lowest value of the last 'length' candles.

#     :param src: The source series e.g. close.
#     :param length: The length of the period.
#     :return: The all-time lowest value of the last 'length' candles.
#     """
#     # Check if the length is valid.
#     if length < 1:
#         raise ValueError("The length must be greater than 0.")
#     elif length > len(src):
#         raise ValueError("The length must be smaller than the length of the source series.")
    
#     _len = len(df)
#     result = list()
#     for i in range(1, _len+1):
#         if i < length:
#             result.append(0)
#         else:
#             res = df.loc[i-length:i-1].min()
#             result.append(res)
#     result = pd.Series(result)
#     return result

def lowest(src:pd.Series, length:int, candle:int=None) -> float or pd.Series:
    """
    If the candle is not None, return the lowest value of between candle-length and candle. else returns the lowest value of the last 'length' candles.

    :param candle: The current candle.
    :param src: The source series e.g. close.
    :param length: The length of the period.
    :return: The lowest value of the last 'length' candles.
    """
    # Convert float to int.
    length = int(length)
    # Check if the length is valid.
    if length < 1:
        raise ValueError("The length must be greater than 0.")
    elif length > len(src):
        raise ValueError("The length must be smaller than the length of the source series.")

    if candle is not None:
        # Find the last 'length' candles from teh current candle.
        result = src.iloc[(candle+1-length):candle+1].min()
    else:
        result = src.rolling(window=length).min()
    return result