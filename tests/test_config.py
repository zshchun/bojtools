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
    Path(boj_config.state_path).write_text(json.dumps(saved_state), encoding="utf-8")
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
    assert boj_config.db.execute("SELECT title FROM boj WHERE pid = 1000").fetchone() == ("Example",)


def test_load_config_rejects_missing_browser(boj_config, monkeypatch):
    Path(boj_config.config_path).write_text('browser = ""\n', encoding="utf-8")
    monkeypatch.setattr(boj_config, "find_browser_path", lambda: None)

    with pytest.raises(Exception, match="Failed to detect browser environment"):
        boj_config.load_config()
