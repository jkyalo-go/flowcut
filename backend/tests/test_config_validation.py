import importlib

import pytest


def _reload_config():
    import config
    return importlib.reload(config)


def _set_env(monkeypatch, **kwargs):
    for k, v in kwargs.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)


def test_development_env_allows_defaults(monkeypatch):
    _set_env(monkeypatch, APP_ENV="development", SECRET_KEY="")
    config = _reload_config()
    config.validate_production_config()


def test_production_requires_secret_key(monkeypatch):
    _set_env(monkeypatch, APP_ENV="production", SECRET_KEY="")
    config = _reload_config()
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        config.validate_production_config()


def test_production_rejects_dev_secret_key(monkeypatch):
    _set_env(monkeypatch, APP_ENV="production", SECRET_KEY="dev-secret-key-change-in-prod")
    config = _reload_config()
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        config.validate_production_config()


def test_production_rejects_dev_login_enabled(monkeypatch):
    _set_env(
        monkeypatch,
        APP_ENV="production",
        SECRET_KEY="a" * 32,
        ENABLE_DEV_LOGIN="true",
        DATABASE_URL="postgresql://user:pw@host/db",
    )
    config = _reload_config()
    with pytest.raises(RuntimeError, match="ENABLE_DEV_LOGIN"):
        config.validate_production_config()


def test_production_rejects_sqlite(monkeypatch):
    _set_env(
        monkeypatch,
        APP_ENV="production",
        SECRET_KEY="a" * 32,
        ENABLE_DEV_LOGIN="false",
        DATABASE_URL="sqlite:///./prod.db",
    )
    config = _reload_config()
    with pytest.raises(RuntimeError, match="SQLite"):
        config.validate_production_config()


def test_production_ok_with_strong_config(monkeypatch):
    _set_env(
        monkeypatch,
        APP_ENV="production",
        SECRET_KEY="a" * 32,
        ENABLE_DEV_LOGIN="false",
        DATABASE_URL="postgresql://user:pw@host/db",
    )
    config = _reload_config()
    config.validate_production_config()
