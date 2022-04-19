from numpy import isin
from . .handler.datahandler import DataHandler as dh
import pandas as pd
import os

class Indicator:
    """ Indicator class.
    
    Description:
        This class is used to create an indicator for use in class IndicatorsParallel.
    """
    def __init__(self, name:str, func:callable, args=None, wait=True, **kwargs):
        """ Initialize the indicator """
        self.name = name
        self.func = func
        self.wait = wait
        self.args = args
        self.kwargs = kwargs
        
    def _set_cache(self, src):
        """
        Set the cache for the strategy.
        """
        if not os.path.exists('./cache/'):
            os.makedirs('./cache/')
        start_time = src.index[0]
        end_time = src.index[-1]
        interval = dh._get_interval(src)
        result = self.func(*self.args, **self.kwargs).rename(self.name)
        result.to_pickle('./cache/{}_{}_{}_{}.pickle'.format(self.name, interval, start_time, end_time))
        return result
        
    def _get_cache(self, src):
        start_time = src.index[0]
        end_time = src.index[-1]
        interval = dh._get_interval(src)
        path_cache = './cache/{}_{}_{}_{}.pickle'.format(self.name, interval, start_time, end_time)
        if os.path.exists(path_cache):
            result = pd.read_pickle(path_cache)
            return True, result
        else:
            return False, None
        
    def __repr__(self) -> str:
        return self.name
    
    def __str__(self) -> str:
        return self.name

    def __call__(self):
        exist, result = self._get_cache(self.args[0])
        if not exist:
            print("Entering cache")
            result = self._set_cache(self.args[0])
        return result