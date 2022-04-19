import pandas as pd
import numpy as np

def crossover(source1:pd.Series, source2:pd.Series) -> pd.Series:
    """
    Returns the crossover of the two series.
    :param source1: The first source series.
    :param source2: The second source series.
    :return: The crossover of the two DataFrame.
    """
    # Determine True or False in the previous candle that source2 is higher than source1.
    is_higher = (source1 > source2)
    # Determine True or False in the current candle that source2 is lower than source1.
    is_lower = (source1 < source2).shift()
    # Determine in the current candle that is_higher and is_lower are True or False.
    result = pd.Series((is_higher & is_lower), name='crossover')
    return result

