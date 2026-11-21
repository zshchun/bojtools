import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest


class LoginTab(SimpleNamespace):
    def __await__(self):
        return iter(())


def cookie(name, domain):
    return SimpleNamespace(
        name=name,
        domain=domain,
        to_json=Mock(return_value={"name": name, "domain": domain}),
    )


@pytest.fixture
def login_flow(boj_config, monkeypatch):
    from bojtools import login

    controls = [SimpleNamespace(click=AsyncMock(), send_keys=AsyncMock()) for _ in range(4)]
    boj_button, checkbox, password, login_button = controls
    username = SimpleNamespace(send_keys=AsyncMock())
    tab = LoginTab(
        url="https://www.acmicpc.net/login",
        find=AsyncMock(return_value=boj_button),
        wait_for=AsyncMock(return_value=username),
        select=AsyncMock(side_effect=[checkbox, password, login_button]),
        evaluate=AsyncMock(return_value="test browser"),
        close=AsyncMock(),
        send=AsyncMock(),
    )
    browser = SimpleNamespace(
        get=AsyncMock(return_value=tab),
        tabs=[tab, SimpleNamespace(close=AsyncMock())],
        cookies=SimpleNamespace(
            get_all=AsyncMock(),
            load=AsyncMock(),
            save=AsyncMock(),
            clear=AsyncMock(),
        ),
    )
    start = AsyncMock(return_value=browser)
    monkeypatch.setattr(login.uc, "start", start)
    monkeypatch.setattr("builtins.input", Mock(return_value="test-user"))
    monkeypatch.setattr(login, "getpass", Mock(return_value="test-password"))
    return SimpleNamespace(
        login=login,
        browser=browser,
        tab=tab,
        start=start,
        username=username,
        password=password,
        login_button=login_button,
    )


def test_start_runs_login_coroutine(login_flow, monkeypatch):
    login = login_flow.login
    handler = AsyncMock()
    monkeypatch.setattr(login, "async_login", handler)
    monkeypatch.setattr(login.uc, "loop", lambda: SimpleNamespace(run_until_complete=asyncio.run))
    args = object()

    login.start(args)

    handler.assert_awaited_once_with(args)


@pytest.mark.parametrize("configured_handle", ["", "test-handle"])
def test_login_polls_for_solved_cookie_and_persists_state(
    login_flow, boj_config, monkeypatch, capsys, configured_handle
):
    login = login_flow.login
    token = cookie("solvedacToken", ".solved.ac")
    other_token = cookie("solvedacToken", "example.test")
    login_flow.browser.cookies.get_all.side_effect = [[other_token], [token]]
    sleep = AsyncMock()
    monkeypatch.setattr(login, "asyncio", SimpleNamespace(get_running_loop=asyncio.get_running_loop, sleep=sleep))
    boj_config.conf["solved_handle"] = configured_handle

    asyncio.run(login.async_login(None))

    login_flow.browser.get.assert_awaited_once_with("https://solved.ac/ko/login")
    login_flow.tab.find.assert_awaited_once_with("BOJ로 로그인", timeout=30)
    login_flow.tab.wait_for.assert_awaited_once_with(
        'form#login_form input[name="login_user_id"]', timeout=60
    )
    assert login_flow.tab.select.await_args_list == [
        call('form#login_form input[name="auto_login"]'),
        call('form#login_form input[name="login_password"]'),
        call('form#login_form button[type="submit"]'),
    ]
    login_flow.username.send_keys.assert_awaited_once_with("test-user")
    login_flow.password.send_keys.assert_awaited_once_with("test-password")
    login_flow.login_button.click.assert_awaited_once()
    sleep.assert_awaited_once_with(1)
    expected = {
        "cookies": [{"name": "solvedacToken", "domain": ".solved.ac"}],
        "user_agent": "test browser",
        "solved_handle": configured_handle or "test-user",
    }
    assert json.loads(Path(boj_config.state_path).read_text()) == expected
    assert boj_config.state == expected
    login_flow.browser.cookies.save.assert_awaited_once_with(boj_config.conf["browser_cookies"])
    for tab in login_flow.browser.tabs:
        tab.close.assert_awaited_once()
    assert "LOGIN SUCCESSFUL" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("scenario", "message"),
    [
        ("missing-button", "Could not find the BOJ login button"),
        ("wrong-host", "BOJ login did not open on acmicpc.net"),
    ],
)
def test_login_rejects_unexpected_page_and_closes_tabs(login_flow, scenario, message):
    if scenario == "missing-button":
        login_flow.tab.find.return_value = None
    else:
        login_flow.tab.url = "https://acmicpc.net.example.test/login"

    with pytest.raises(RuntimeError, match=message):
        asyncio.run(login_flow.login.async_login(None))

    login_flow.username.send_keys.assert_not_awaited()
    login_flow.password.send_keys.assert_not_awaited()
    login_flow.browser.cookies.save.assert_not_awaited()
    for tab in login_flow.browser.tabs:
        tab.close.assert_awaited_once()


def test_login_closes_tabs_when_cookie_never_arrives(login_flow, monkeypatch):
    times = iter([0, 300])
    sleep = AsyncMock()
    timing = SimpleNamespace(get_running_loop=lambda: SimpleNamespace(time=lambda: next(times)), sleep=sleep)
    monkeypatch.setattr(login_flow.login, "asyncio", timing)
    login_flow.browser.cookies.get_all.return_value = []

    with pytest.raises(TimeoutError, match="within 300 seconds"):
        asyncio.run(login_flow.login.async_login(None))

    sleep.assert_not_awaited()
    login_flow.browser.cookies.save.assert_not_awaited()
    for tab in login_flow.browser.tabs:
        tab.close.assert_awaited_once()


@pytest.mark.parametrize("cookie_file", ["missing", "valid", "outdated"])
def test_refresh_cookie_rebuilds_http_session(
    login_flow, boj_config, monkeypatch, tmp_path, cookie_file
):
    login = login_flow.login
    browser = login_flow.browser
    cookie_path = tmp_path / "browser-cookies"
    boj_config.conf["browser_cookies"] = str(cookie_path)
    if cookie_file != "missing":
        cookie_path.touch()
    if cookie_file == "outdated":
        browser.cookies.load.side_effect = AttributeError("Cookie has no attribute 'same_party'")
    monkeypatch.setattr(boj_config, "state", {"solved_handle": "existing-handle"}, raising=False)
    monkeypatch.setattr(login._http, "cookie_jar", object())
    session_calls = []

    async def close_session():
        session_calls.append("close")

    async def open_session(*, force):
        assert force is True
        assert login._http.cookie_jar is None
        session_calls.append("open")

    monkeypatch.setattr(login._http, "close_session", close_session)
    monkeypatch.setattr(login._http, "open_session", open_session)
    get_cookies_command = Mock(return_value=object())
    monkeypatch.setattr(login.uc.cdp.network, "get_all_cookies", get_cookies_command)
    login_flow.tab.send.return_value = [cookie("sample", "acmicpc.net")]
    url = "https://www.acmicpc.net/problem/1000"

    asyncio.run(login.refresh_cookie(url))

    assert login_flow.start.await_args.kwargs["headless"] is True
    browser.get.assert_awaited_once_with(url)
    login_flow.tab.send.assert_awaited_once_with(get_cookies_command.return_value)
    if cookie_file == "missing":
        browser.cookies.load.assert_not_awaited()
    else:
        browser.cookies.load.assert_awaited_once_with(str(cookie_path))
    assert browser.cookies.clear.await_count == int(cookie_file == "outdated")
    expected = {
        "cookies": [{"name": "sample", "domain": "acmicpc.net"}],
        "user_agent": "test browser",
        "solved_handle": "existing-handle",
    }
    assert json.loads(Path(boj_config.state_path).read_text()) == expected
    assert boj_config.state == expected
    assert session_calls == ["close", "open"]
    browser.cookies.save.assert_awaited_once_with(str(cookie_path))
    for tab in browser.tabs:
        tab.close.assert_awaited_once()


def test_refresh_cookie_propagates_unexpected_cookie_error(login_flow, boj_config, tmp_path):
    cookie_path = tmp_path / "browser-cookies"
    cookie_path.touch()
    boj_config.conf["browser_cookies"] = str(cookie_path)
    browser = login_flow.browser
    browser.cookies.load.side_effect = AttributeError("invalid cookie storage")

    with pytest.raises(AttributeError, match="invalid cookie storage"):
        asyncio.run(login_flow.login.refresh_cookie("https://www.acmicpc.net/problem/1000"))

    browser.cookies.clear.assert_not_awaited()
    browser.cookies.save.assert_not_awaited()
    browser.get.assert_not_awaited()
