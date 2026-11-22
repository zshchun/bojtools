import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from patchright.async_api import Error as PlaywrightError


@pytest.fixture
def browser_flow(boj_config, monkeypatch):
    from bojtools import _browser

    context = SimpleNamespace(new_page=AsyncMock(), add_cookies=AsyncMock(), close=AsyncMock())
    browser = SimpleNamespace(new_context=AsyncMock(return_value=context), close=AsyncMock())
    launch = AsyncMock(return_value=browser)
    driver = MagicMock()
    driver.__aenter__.return_value = SimpleNamespace(chromium=SimpleNamespace(launch=launch))
    monkeypatch.setattr(_browser, "async_playwright", lambda: driver)
    return SimpleNamespace(module=_browser, launch=launch, browser=browser, context=context, driver=driver)


def test_browser_opens_fresh_context_and_releases_resources(boj_config, browser_flow):
    snapshot = Path(boj_config.browser_state_path)
    snapshot.parent.mkdir(exist_ok=True)
    snapshot.write_text(
        json.dumps({"cookies": [], "origins": []}), encoding="utf-8"
    )
    boj_config.conf["browser"] = None

    async def open_page():
        async with browser_flow.module.browser_page(headless=False) as page:
            assert page is browser_flow.context.new_page.return_value
            raise RuntimeError("synthetic failure after launch")

    with pytest.raises(RuntimeError, match="synthetic failure"):
        asyncio.run(open_page())
    browser_flow.launch.assert_awaited_once_with(
        headless=False, executable_path=None, args=boj_config.conf["browser_args"]
    )
    browser_flow.browser.new_context.assert_awaited_once_with(
        locale=boj_config.conf["locale"], storage_state=None
    )
    browser_flow.context.add_cookies.assert_not_awaited()
    browser_flow.context.close.assert_awaited_once_with()
    browser_flow.browser.close.assert_awaited_once_with()
    browser_flow.driver.__aexit__.assert_awaited_once()


def test_browser_restores_saved_snapshot(boj_config, browser_flow):
    state = {"cookies": [], "origins": [{"origin": "https://example.test", "localStorage": []}]}
    Path(boj_config.browser_state_path).write_text(json.dumps(state), encoding="utf-8")

    async def open_page():
        async with browser_flow.module.browser_page(headless=True, restore=True):
            pass

    asyncio.run(open_page())
    browser_flow.launch.assert_awaited_once_with(
        headless=True, executable_path=boj_config.conf["browser"], args=boj_config.conf["browser_args"]
    )
    browser_flow.browser.new_context.assert_awaited_once_with(
        locale=boj_config.conf["locale"], storage_state=state
    )
    browser_flow.context.add_cookies.assert_not_awaited()


@pytest.mark.parametrize("snapshot", [None, b"{invalid json", b"{}"])
def test_browser_restores_login_cookies_from_json(boj_config, browser_flow, snapshot):
    if snapshot is not None:
        Path(boj_config.browser_state_path).write_bytes(snapshot)
    login = {
        "name": "login", "value": "synthetic", "domain": ".acmicpc.net", "path": "/",
        "expires": -1, "httpOnly": True, "secure": True, "sameSite": "Lax", "size": 8,
    }
    boj_config.state = {
        "cookies": [
            login,
            dict(login, name="cf_clearance"),
            dict(login, domain="other.example"),
        ]
    }

    async def open_page():
        async with browser_flow.module.browser_page(headless=True, restore=True):
            pass

    asyncio.run(open_page())
    expected = {key: value for key, value in login.items() if key not in ("expires", "size")}
    browser_flow.context.add_cookies.assert_awaited_once_with([expected])


def test_browser_allows_disabled_snapshot(boj_config, browser_flow):
    boj_config.browser_state_path = None

    assert browser_flow.module._saved_storage_state() is None


def test_browser_closes_when_context_creation_fails(browser_flow):
    browser_flow.browser.new_context.side_effect = PlaywrightError("context creation failed")

    async def open_page():
        async with browser_flow.module.browser_page(headless=True):
            pytest.fail("A page was returned after context creation failed")

    with pytest.raises(PlaywrightError, match="context creation failed"):
        asyncio.run(open_page())
    browser_flow.browser.close.assert_awaited_once_with()
