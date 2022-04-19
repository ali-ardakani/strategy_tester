import pandas as pd
import numpy as np

def crossunder(source1:pd.Series, source2:pd.Series) -> pd.DataFrame:
    """
    Returns the crossunder of the two series.
    :param source1: The first source series.
    :param source2: The second source series.
    :return: The crossunder of the two series.
    """
    # Determine True or False in the current candle that source1 is lower than source2.
    is_lower = (source1 < source2)
    # Determine True or False in the previous candle that source1 is higher than source2.
    is_higher = (source1 > source2).shift()
    # Determine in the current candle that is_higher and is_lower are True or False.
    result = pd.Series((is_higher & is_lower), name='crossunder')
    return result