from dataclasses import dataclass
 

@dataclass
class Trade:
    type: str
    entry_date: float
    entry_price: float
    contract: float
    entry_signal: str = None
    exit_date: float = None
    exit_price: float = None
    exit_signal: str = None
    comment: str = None
    profit: float = None
    profit_percent: float = None
    draw_down: float = None
    run_up: float = None
    cum_profit: float = None
    cum_profit_percent: float = None
    bars_traded: int = None
