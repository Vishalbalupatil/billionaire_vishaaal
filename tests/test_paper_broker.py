from billionaire.execution.paper_broker import PaperBroker
from billionaire.models import (
    Exchange,
    Instrument,
    OrderRequest,
    OrderStatus,
    OrderType,
    ProductType,
    Segment,
    Side,
)


def _inst() -> Instrument:
    return Instrument(
        instrument_token=12345,
        tradingsymbol="TEST",
        exchange=Exchange.NSE,
        segment=Segment.EQUITY,
        lot_size=1,
    )


def test_market_order_fills_at_ltp():
    pb = PaperBroker()
    pb.on_ltp(12345, 100.0)
    req = OrderRequest(
        instrument=_inst(),
        side=Side.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        product=ProductType.MIS,
    )
    order = pb.place_order(req)
    assert order.status == OrderStatus.COMPLETE
    assert order.filled_qty == 10
    assert order.avg_price > 0
    positions = pb.positions()
    assert len(positions) == 1 and positions[0].quantity == 10


def test_limit_order_fills_when_price_touches():
    pb = PaperBroker()
    pb.on_ltp(12345, 100.0)
    req = OrderRequest(
        instrument=_inst(),
        side=Side.BUY,
        quantity=5,
        order_type=OrderType.LIMIT,
        limit_price=99.0,
        product=ProductType.MIS,
    )
    order = pb.place_order(req)
    assert order.status == OrderStatus.OPEN
    pb.on_ltp(12345, 98.5)  # crosses limit
    assert pb._orders[order.order_id].status == OrderStatus.COMPLETE


def test_position_closes_on_opposite_fill():
    pb = PaperBroker()
    pb.on_ltp(12345, 100.0)
    inst = _inst()
    pb.place_order(OrderRequest(instrument=inst, side=Side.BUY, quantity=10, order_type=OrderType.MARKET))
    pb.place_order(OrderRequest(instrument=inst, side=Side.SELL, quantity=10, order_type=OrderType.MARKET))
    assert len(pb.positions()) == 0
