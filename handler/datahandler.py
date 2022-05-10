from unicodedata import name
import pandas as pd
from binance import Client
import numpy as np

class DataHandler:
    """
    DataHandler constructor.
    
    Description:
        If the data is not set, get the data BTCUSDT from the binance API.    
        
    Attributes:
        data: DataFrame
            The data that you want to handle.
            The columns should be ['date', 'open', 'high', 'low', 'close', 'volume'].
        interval: str
            The interval that you want to get the data.
    
    """
    intervals = {
        '1m': '6 months ago',
        '3m': '9 months ago',
        '5m': '18 months ago',
        '15m': '2 years ago',
        '30m': '3 years ago',
        '1h': '4 years ago',
        '2h': '5 years ago',
        '4h': '6 years ago',
        '6h': '7 years ago',
        '8h': '8 years ago',
        '12h': '9 years ago',
        '1d': '10 years ago',
        '3d': '11 years ago',
        '1w': '12 years ago',
    } 

    def __init__(self, **params):
        """
        DataHandler constructor.
        
        Parameters
        ----------
        data: DataFrame
            The data that you want to handle.
            The columns should be ['date', 'open', 'high', 'low', 'close', 'volume', 'close_time'].
        interval: str
            The interval that you want to get the data.
        """
        if not params:
            raise ValueError("You need to set the data or the interval.")
        
        self.interval = self._validate_interval(params.get("interval", None))
        self.data = self._validate_data(params.get("data", None))
        
    def _validate_interval(self, interval: str) -> str:
        """
        Validate the interval.
        
        Parameters
        ----------
        interval: str
            The interval that you want to validate.
            
        Returns
        -------
        str
            The validated interval.
        """
        if interval is None:
            return None
        if interval not in self.intervals.keys():
            raise ValueError("The interval is not valid.")
        return interval

    def _validate_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Validate the data.
        
        Parameters
        ----------
        data: DataFrame
            The data that you want to validate.
        
        Returns
        -------
        DataFrame
            The validated data.
        """
        if data is None:
            data = self._get_data(self.interval)
        if not isinstance(data, pd.DataFrame):
            raise TypeError("The data must be a pandas DataFrame.")

        if data.empty:
            raise ValueError("The data is empty.")

        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'close_time']
        # wrong_columns = [
        #     column for column in required_columns if column not in data.columns.to_list()+[data.index.name]
        # ]
        # if wrong_columns:
        #     raise ValueError(
        #         "The data must have the columns: {}".format(wrong_columns))

        # if data.index.name != 'date':
        #     data.set_index('date', inplace=True)
            
        # # Check type of the date and close_time
        # if np.issubdtype(data.index, np.datetime64):
        #     data.index = data.index.astype(int)/10**6
        # if np.issubdtype(data['close_time'], np.datetime64):
        #     data['close_time'] = data['close_time'].astype(int)/10**6
            
        # # Set interval
        # self.interval = self._get_interval(data)
        # return data
        wrong_columns = [
            column for column in required_columns if column not in data.columns.to_list()
        ]
        if wrong_columns:
            raise ValueError(
                "The data must have the columns: {}".format(wrong_columns))

        # if data.index.name != 'date':
        #     data.set_index('date', inplace=True)
            
        # Check type of the date and close_time
        if np.issubdtype(data["date"], np.datetime64):
            data["date"] = data["date"].astype(np.int64)/10**6
        if np.issubdtype(data['close_time'], np.datetime64):
            data['close_time'] = data['close_time'].astype(np.int64)/10**6
            
        # Set interval
        self.interval = self._get_interval(data)
        return data

    def _get_data(self, interval: str) -> pd.DataFrame:
        """
        Get the data from the binance API.
        
        Description:
            Get candlestick BTCUSDT data from the binance API.
            
        Parameters
        ----------
        interval: str
            The interval that you want to get the data.
            
        Returns
        -------
        DataFrame
            The data from the binance API.
            
        """
        # Get the data from the binance API.
        client = Client()
        start_time = self.intervals[interval]
        data = client.get_historical_klines("BTCUSDT", interval, start_time)
        
        # Convert the data to a pandas DataFrame.
        data = pd.DataFrame(data)
        data.columns = ['date','open', 'high', 'low', 'close', 'volume','close_time', 'qav','num_trades','taker_base_vol','taker_quote_vol', 'ignore']
        data.drop(['qav','num_trades','taker_base_vol','taker_quote_vol', 'ignore'], axis=1, inplace=True)
        data = data.astype({'date': 'float', 'open': 'float64', 'high': 'float64', 'low': 'float64', 'close': 'float64', 'volume': 'float64', 'close_time': 'float'})
        
        return data

    @staticmethod
    def _get_interval(data: pd.DataFrame) -> str:
        """
        Get the interval of the data.
        
        Parameters
        ----------
        data: DataFrame
            The data that you want to get the interval of.
        
        Returns
        -------
        str
            The interval of the data.
        """
        if isinstance(data, pd.Series):
            data = data.reset_index()
            
        # Calculate the interval milliseconds
        interval = data.date.iloc[0:2].diff().iat[1]
        # Convert to interval string
        interval = interval / (1000 * 60)
        if interval == 1:
            interval = '1m'
        elif interval == 3:
            interval = '3m'
        elif interval == 5:
            interval = '5m'
        elif interval == 15:
            interval = '15m'
        elif interval == 30:
            interval = '30m'
        elif interval == 60:
            interval = '1h'
        elif interval == 120:
            interval = '2h'
        elif interval == 240:
            interval = '4h'
        elif interval == 360:
            interval = '6h'
        elif interval == 480:
            interval = '8h'
        elif interval == 720:
            interval = '12h'
        elif interval == 1440:
            interval = '1d'
        elif interval == 4320:
            interval = '3d'
        elif interval == 10080:
            interval = '1w'
        else:
            raise ValueError("The interval is not valid.")

        return interval

