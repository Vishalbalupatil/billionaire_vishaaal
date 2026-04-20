
import pytest


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch, tmp_path):
    """Force every test to use an isolated sqlite file."""
    db_file = tmp_path / "billionaire_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("APP_MODE", "paper")
    # clear cached settings/db
    from billionaire.config import settings as _settings_mod
    from billionaire.storage import database as _db_mod

    _settings_mod.get_settings.cache_clear()
    _db_mod.get_database.cache_clear()
    yield
    _settings_mod.get_settings.cache_clear()
    _db_mod.get_database.cache_clear()


@pytest.fixture
def tmp_env(tmp_path):
    return tmp_path
