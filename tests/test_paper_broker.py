"""Tests for the paper trading broker."""

from ai_trader.broker.paper import PaperBroker
from ai_trader.models.domain import (
    Exchange,
    Instrument,
    OrderRequest,
    OrderStatus,
    Side,
)


def _nifty_instrument() -> Instrument:
    return Instrument(
        instrument_token=256265,
        tradingsymbol="NIFTY22000CE",
        exchange=Exchange.NFO,
    )


def test_paper_buy_and_sell():
    broker = PaperBroker(initial_capital=100000)
    inst = _nifty_instrument()
    broker.set_price("NIFTY22000CE", 200.0)

    # Buy
    buy_req = OrderRequest(instrument=inst, side=Side.BUY, quantity=25)
    buy_order = broker.place_order(buy_req)
    assert buy_order.status == OrderStatus.COMPLETE
    assert buy_order.filled_qty == 25

    # Check position
    positions = broker.positions()
    assert len(positions) == 1
    assert positions[0].quantity == 25

    # Sell
    broker.set_price("NIFTY22000CE", 220.0)
    sell_req = OrderRequest(instrument=inst, side=Side.SELL, quantity=25)
    sell_order = broker.place_order(sell_req)
    assert sell_order.status == OrderStatus.COMPLETE

    # Position should be closed
    positions = broker.positions()
    assert len(positions) == 0

    # Should have made profit
    assert broker.pnl > 0


def test_paper_reject_no_price():
    broker = PaperBroker()
    inst = _nifty_instrument()
    req = OrderRequest(instrument=inst, side=Side.BUY, quantity=25)
    order = broker.place_order(req)
    assert order.status == OrderStatus.REJECTED


def test_paper_margins():
    broker = PaperBroker(initial_capital=500000)
    margins = broker.margins()
    assert margins["equity"]["available"]["live_balance"] == 500000
