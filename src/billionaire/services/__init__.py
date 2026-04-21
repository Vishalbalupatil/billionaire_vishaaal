"""Application-level services. Thin glue between pure-logic modules
(:mod:`billionaire.strategy`, :mod:`billionaire.backtest`) and the API /
CLI layers. Keeping I/O-laden orchestration here keeps the API surface
clean and the strategy modules testable in isolation.
"""
