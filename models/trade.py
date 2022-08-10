from dataclasses import dataclass
from pandas import DataFrame

class TradeType:
    LONG = 'long'
    SHORT = 'short'

class OrderType:
    LIMIT = 'LIMIT'
    MARKET = 'MARKET'
    STOP = 'STOP'
    TAKE_PROFIT = 'TAKE_PROFIT'
    STOP_MARKET = 'STOP_MARKET'
    TAKE_PROFIT_MARKET = 'TAKE_PROFIT_MARKET'
    TRAILING_STOP_MARKET = 'TRAILING_STOP_MARKET'

class Side:
    BUY = 'BUY'
    SELL = 'SELL'

@dataclass
class Order:
    entry: bool # A variable to determine trade entry or exit(True for entry, False for exit)
    side: str
    cumQty: int
    cumQuote: int
    executedQty: int
    orderId: int
    avgPrice: float
    origQty: int
    price: float
    reduceOnly: bool
    positionSide: str
    status: str
    stopPrice: float
    closePosition: bool
    symbol: str
    timeInForce: str
    type: OrderType
    origType: str
    updateTime: int
    workingType: str
    priceProtect: bool
    filledAccumulatedQty: float = 0.0
    activatePrice: float = None # activation price, only return with TRAILING_STOP_MARKET order
    priceRate: float = None # callback rate, only return with TRAILING_STOP_MARKET order
    entry_signal: str = None
    comment: str = None
    
    def __str__(self):
        return f'{self.side=}\n{self.cumQty=}\n{self.cumQuote=}\n{self.executedQty=}\n{self.orderId=}\n{self.avgPrice=}\n{self.origQty=}\n{self.price=}\n{self.reduceOnly=}\n{self.positionSide=}\n{self.status=}\n{self.stopPrice=}\n{self.closePosition=}\n{self.symbol=}\n{self.timeInForce=}\n{self.type=}\n{self.origType=}\n{self.activatePrice=}\n{self.priceRate=}\n{self.updateTime=}\n{self.workingType=}\n{self.priceProtect=}'
    
    def __repr__(self) -> str:
        return f'{self.side=}\n{self.cumQty=}\n{self.cumQuote=}\n{self.executedQty=}\n{self.orderId=}\n{self.avgPrice=}\n{self.origQty=}\n{self.price=}\n{self.reduceOnly=}\n{self.positionSide=}\n{self.status=}\n{self.stopPrice=}\n{self.closePosition=}\n{self.symbol=}\n{self.timeInForce=}\n{self.type=}\n{self.origType=}\n{self.activatePrice=}\n{self.priceRate=}\n{self.updateTime=}\n{self.workingType=}\n{self.priceProtect=}'

@dataclass
class Trade:
    type: str
    entry_date: float
    entry_price: float
    contract: float
    orderid: int = None
    order_type: str = OrderType.MARKET
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

class OrderToTrade:
    @staticmethod
    def entry(order: Order):
        """
        After a new order filled, convert it to a trade(create a new position)
        """
        _type = TradeType.LONG if order.side == Side.BUY else TradeType.SHORT
        return Trade(
            type=_type,
            entry_date=order.updateTime,
            entry_price=order.price,
            contract=order.origQty,
            orderid=order.orderId,
            order_type=order.type,
            entry_signal=order.entry_signal,
            comment=order.comment
        )     

    @staticmethod
    def exit(trade: Trade, order: Order, data: DataFrame):
        trade.exit_date = order.updateTime
        trade.exit_price = order.price
        data = OrderToTrade._validate_data(trade, data)
        trade.profit = OrderToTrade._profit(trade)
        trade.profit_percent = OrderToTrade._profit_percent(trade)
        trade.draw_down = OrderToTrade._draw_down(trade, data)
        trade.run_up = OrderToTrade._run_up(trade, data)
        trade.bars_traded = OrderToTrade._bars_traded(data)
        return trade
        
    @staticmethod
    def _profit(trade:Trade) -> float:
        if trade.exit_price is not None:
            profit = trade.exit_price - trade.entry_price if trade.type == 'long' else trade.entry_price - trade.exit_price  
        else:
            profit = None
            
        return profit
    
    @staticmethod
    def _profit_percent(trade:Trade) -> float:
        if trade.profit is not None:
            profit_percent = trade.profit*100 / trade.entry_price
        else:
            profit_percent = None
            
        return profit_percent
    
    @staticmethod
    def _draw_down(trade:Trade, data:DataFrame) -> float:
        if trade.type == "long":
            draw_down = (data.low.min() - data.open.iat[0])*100 / data.open.iat[0]
        else:
            draw_down = -(data.high.max() - data.open.iat[0])*100 / data.open.iat[0]
            
        return draw_down
    
    @staticmethod
    def _run_up(trade:Trade, data:DataFrame) -> float:
        if trade.type == "long":
            run_up = (data.high.max() - data.open.iat[0])*100 / data.open.iat[0]
        else:
            run_up = -(data.low.min() - data.open.iat[0])*100 / data.open.iat[0]
        
        return run_up

    @staticmethod
    def _bars_traded(data:DataFrame) -> int:
        return len(data)
    
    @staticmethod
    def _validate_data(trade:Trade, data:DataFrame):
        data = data.loc[
            data.close_time.between(
            trade.entry_date,
            trade.exit_date + 1)]
        return data
    
    