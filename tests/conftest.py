import importlib
import os
from copy import deepcopy

import pytest


def _normalized_path(filename):
    return os.path.normcase(os.path.normpath(filename))


@pytest.fixture(scope="session")
def _config_module(tmp_path_factory):
    # config.py loads at import time. Redirect its initial filesystem access
    # before any test imports a module that depends on it.
    root = tmp_path_factory.mktemp("boj-config")
    (root / ".boj").mkdir()
    user_config_dir = _normalized_path(os.environ["HOME"] + "/.boj")
    user_config_file = os.path.join(user_config_dir, "config.toml")
    original_expanduser = os.path.expanduser
    original_isfile = os.path.isfile
    original_isdir = os.path.isdir

    def expanduser(filename):
        if isinstance(filename, str) and filename.startswith("~/"):
            return str(root / filename[2:])
        return original_expanduser(filename)

    def isfile(filename):
        if _normalized_path(filename) == user_config_file:
            return False
        if filename == "/usr/bin/chromium":
            return True
        return original_isfile(filename)

    def isdir(filename):
        return _normalized_path(filename) == user_config_dir or original_isdir(filename)

    with pytest.MonkeyPatch.context() as bootstrap:
        bootstrap.setattr(os.path, "expanduser", expanduser)
        bootstrap.setattr(os.path, "isfile", isfile)
        bootstrap.setattr(os.path, "isdir", isdir)
        bootstrap.setattr("platform.system", lambda: "Linux")
        config = importlib.import_module("bojtools.config")

    config.db.close()
    return config


@pytest.fixture
def boj_config(_config_module, monkeypatch, tmp_path):
    config = _config_module
    defaults = deepcopy(config.DEFAULT_CONFIG)
    defaults.update(
        cache_dir=str(tmp_path / "cache"),
        code_dir=str(tmp_path / "code"),
        database=str(tmp_path / "cache.db"),
        template=str(tmp_path / "template.cpp"),
        state_path=str(tmp_path / "state.json"),
        browser_cookies=str(tmp_path / "cookies"),
        browser=str(tmp_path / "chromium"),
        # The initial load mutates the default list in place.
        browser_args=[],
    )
    monkeypatch.setattr(config, "DEFAULT_CONFIG", defaults)
    monkeypatch.setattr(config, "base_dir", str(tmp_path))
    monkeypatch.setattr(config, "config_path", str(tmp_path / "config.toml"))
    monkeypatch.setattr(config, "conf", {})
    monkeypatch.setattr(config, "state", {}, raising=False)
    monkeypatch.setattr(config, "state_path", defaults["state_path"])
    monkeypatch.setattr(config, "db", None)
    config.load_config()
    try:
        yield config
    finally:
        if config.db is not None:
            config.db.close()
