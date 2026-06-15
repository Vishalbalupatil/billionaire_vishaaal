"""Shared test fixtures."""

import os

# Force paper mode for tests
os.environ.setdefault("TRADING_MODE", "paper")
os.environ.setdefault("KITE_API_KEY", "test_key")
os.environ.setdefault("KITE_API_SECRET", "test_secret")
