from dataclasses import dataclass


@dataclass
class Candle:
    """
    Candle class
    """
    date: float
    open: float
    high: float
    low: float
    close: float
    volume: float