import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("system", ["Unknown", "Linux"])
def test_find_browser_path_returns_none_without_supported_candidate(boj_config, monkeypatch, system):
    monkeypatch.setattr(boj_config.platform, "system", lambda: system)
    monkeypatch.setattr(boj_config.path, "isfile", lambda filename: False)

    assert boj_config.find_browser_path() is None


def test_find_browser_path_uses_first_available_candidate(boj_config, monkeypatch, tmp_path):
    missing = tmp_path / "missing"
    browser = tmp_path / "chromium"
    browser.touch()
    monkeypatch.setattr(boj_config.platform, "system", lambda: "TestOS")
    monkeypatch.setitem(boj_config.def_browser_path, "TestOS", [str(missing), str(browser)])

    assert boj_config.find_browser_path() == str(browser)


def test_config_starts_with_one_copy_of_each_browser_flag(boj_config):
    assert boj_config.conf["browser_args"] == boj_config.def_browser_args


def test_load_config_merges_defaults_and_restores_state(boj_config):
    saved_state = {"user_agent": "Synthetic browser", "solved_handle": "test-user"}
    state_path = Path(boj_config.conf["state_path"])
    state_path.write_text(json.dumps(saved_state), encoding="utf-8")
    Path(boj_config.config_path).write_text(
        'locale = "en-US"\nbrowser_args = ["--test-argument"]\n', encoding="utf-8"
    )
    boj_config.db.execute("INSERT INTO boj (pid, title) VALUES (1000, 'Example')")
    boj_config.db.commit()
    boj_config.db.close()

    boj_config.load_config()

    assert boj_config.conf["locale"] == "en-US"
    assert boj_config.conf["browser_args"] == ["--test-argument", *boj_config.def_browser_args]
    assert boj_config.conf["user_agent"] == "Synthetic browser"
    assert boj_config.state == saved_state
    assert Path(boj_config.state_path) == state_path
    assert boj_config.db.execute("SELECT title FROM boj WHERE pid = 1000").fetchone() == ("Example",)


@pytest.mark.parametrize("saved", [True, False])
def test_load_config_uses_configured_state_path(boj_config, tmp_path, saved):
    state_path = tmp_path / "custom-state.json"
    browser_path = tmp_path / "custom-cookies"
    if saved:
        state_path.write_text('{"solved_handle": "current"}', encoding="utf-8")
    Path(boj_config.config_path).write_text(
        f"state_path = {json.dumps(str(state_path))}\n"
        f"browser_cookies = {json.dumps(str(browser_path))}\n",
        encoding="utf-8",
    )
    boj_config.db.close()

    boj_config.load_config()

    assert boj_config.state == ({"solved_handle": "current"} if saved else {})
    assert Path(boj_config.state_path) == state_path
    assert Path(boj_config.browser_state_path) == tmp_path / "custom-cookies_v2"
    from bojtools.login import _write_state

    _write_state(boj_config.state_path, {"solved_handle": "updated"})
    boj_config.db.close()
    boj_config.load_config()
    assert boj_config.state == {"solved_handle": "updated"}


def test_browser_path_cannot_overwrite_configured_state(boj_config, tmp_path):
    state_path = tmp_path / "cookies_v2"
    browser_path = tmp_path / "cookies"
    state_path.write_text('{"solved_handle": "old"}', encoding="utf-8")
    Path(boj_config.config_path).write_text(
        f"state_path = {json.dumps(str(state_path))}\n"
        f"browser_cookies = {json.dumps(str(browser_path))}\n",
        encoding="utf-8",
    )
    boj_config.db.close()

    boj_config.load_config()

    assert boj_config.state == {"solved_handle": "old"}
    assert Path(boj_config.browser_state_path) == tmp_path / "cookies_v2_2"
    assert Path(boj_config.state_path) == state_path


def test_shared_state_path_preserves_nested_browser_file(boj_config, tmp_path):
    from bojtools.login import _write_state

    state_path = tmp_path / "state.json"
    browser_path = tmp_path / "playwright" / "state.json" / "cookies"
    state_path.write_text('{"solved_handle": "old"}', encoding="utf-8")
    browser_path.parent.mkdir(parents=True)
    browser_path.write_bytes(b"legacy browser snapshot")
    Path(boj_config.config_path).write_text(
        f"state_path = {json.dumps(str(state_path))}\n"
        f"browser_cookies = {json.dumps(str(browser_path))}\n",
        encoding="utf-8",
    )
    boj_config.db.close()

    boj_config.load_config()

    assert boj_config.state == {"solved_handle": "old"}
    assert Path(boj_config.state_path) == state_path
    _write_state(boj_config.state_path, {"solved_handle": "new"})
    assert json.loads(Path(boj_config.state_path).read_text()) == {"solved_handle": "new"}
    assert json.loads(state_path.read_text()) == {"solved_handle": "new"}
    assert browser_path.read_bytes() == b"legacy browser snapshot"


def test_browser_path_skips_existing_directory(boj_config, tmp_path):
    from bojtools.login import _write_state

    (tmp_path / "cookies_v2").mkdir()
    boj_config.db.close()
    boj_config.load_config()

    assert Path(boj_config.browser_state_path) == tmp_path / "cookies_v2_2"
    _write_state(boj_config.browser_state_path, {"cookies": [], "origins": []})
    assert (tmp_path / "cookies_v2").is_dir()


def test_disabled_browser_snapshot_keeps_shared_state(boj_config):
    Path(boj_config.config_path).write_text('browser_cookies = ""\n', encoding="utf-8")
    boj_config.db.close()
    boj_config.load_config()

    assert boj_config.browser_state_path is None
    assert Path(boj_config.state_path) == Path(boj_config.conf["state_path"])


def test_load_config_allows_playwright_default_browser(boj_config, monkeypatch):
    Path(boj_config.config_path).write_text('browser = ""\n', encoding="utf-8")
    monkeypatch.setattr(boj_config, "find_browser_path", lambda: None)
    boj_config.db.close()

    boj_config.load_config()

    assert boj_config.conf["browser"] is None
