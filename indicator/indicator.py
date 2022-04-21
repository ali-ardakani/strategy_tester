import hashlib
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
        
    def _set_cache(self):
        """
        Set the cache for the strategy.
        
        Description:
            This function using args and kwargs to generate the name chache and cache the result.
        
        Returns:
            result: pd.Series or pd.DataFrame
        """
        if not os.path.exists('./cache/'):
            os.makedirs('./cache/')
        # Generate the name of the cache file based on the args and kwargs
        name = f"{self.name}_{self.func.__name__}_{hashlib.sha256(str(self.args).encode('utf-8')).hexdigest()}_{hashlib.sha256(str(self.kwargs).encode('utf-8')).hexdigest()}"
        result = self.func(*self.args, **self.kwargs).rename(self.name)
        result.to_pickle('./cache/{}.pickle'.format(name))
        return result
        
    def _get_cache(self):
        """
        Get the cache for the strategy.
        
        Description:
            This function checks if the cache exists and returns the result.
            If the cache does not exist, it returns False.
        Returns:
            exist: bool
                True if the cache exists, False otherwise.
            result: pd.Series or pd.DataFrame
                The result of the cache.
        """
        name = f"{self.name}_{self.func.__name__}_{hashlib.sha256(str(self.args).encode('utf-8')).hexdigest()}_{hashlib.sha256(str(self.kwargs).encode('utf-8')).hexdigest()}"
        path_cache = './cache/{}.pickle'.format(name)
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
        exist, result = self._get_cache()
        if not exist:
            result = self._set_cache()
        return result