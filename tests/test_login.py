import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest
from patchright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout


def cookie(name, domain):
    return {"name": name, "domain": domain}


@pytest.fixture
def login_flow(boj_config, monkeypatch):
    from bojtools import login

    selectors = {
        'form#login_form input[name="login_user_id"]': SimpleNamespace(
            wait_for=AsyncMock(), fill=AsyncMock()
        ),
        'form#login_form input[name="auto_login"]': SimpleNamespace(check=AsyncMock()),
        'form#login_form input[name="login_password"]': SimpleNamespace(fill=AsyncMock()),
        'form#login_form button[type="submit"]': SimpleNamespace(click=AsyncMock()),
    }
    sso_button = SimpleNamespace(click=AsyncMock(), evaluate=AsyncMock(return_value=True))
    approval_link = SimpleNamespace(click=AsyncMock(), is_visible=AsyncMock(return_value=False))
    approval_button = SimpleNamespace(click=AsyncMock(), is_visible=AsyncMock(return_value=True))
    context = SimpleNamespace(cookies=AsyncMock(), storage_state=AsyncMock())
    page = SimpleNamespace(
        url="https://www.acmicpc.net/login",
        goto=AsyncMock(return_value=SimpleNamespace(headers={})),
        get_by_role=Mock(side_effect=lambda role, *, name, exact: {
            ("button", "BOJ로 로그인"): sso_button,
            ("button", "로그인"): approval_button,
            ("link", "로그인"): approval_link,
        }[(role, name)]),
        locator=Mock(side_effect=selectors.__getitem__),
        evaluate=AsyncMock(return_value="test browser"),
        is_closed=Mock(return_value=False),
        context=context,
    )
    opened = Mock()
    closed = Mock()

    @asynccontextmanager
    async def browser_page(**kwargs):
        opened(**kwargs)
        try:
            yield page
        finally:
            closed()

    monkeypatch.setattr(login, "browser_page", browser_page)
    monkeypatch.setattr("builtins.input", Mock(return_value="test-user"))
    monkeypatch.setattr(login, "getpass", Mock(return_value="test-password"))
    return SimpleNamespace(
        login=login,
        page=page,
        context=context,
        opened=opened,
        closed=closed,
        sso_button=sso_button,
        approval_link=approval_link,
        approval_button=approval_button,
        username=selectors['form#login_form input[name="login_user_id"]'],
        checkbox=selectors['form#login_form input[name="auto_login"]'],
        password=selectors['form#login_form input[name="login_password"]'],
        login_button=selectors['form#login_form button[type="submit"]'],
    )


def test_start_runs_login_coroutine(login_flow, monkeypatch):
    login = login_flow.login
    handler = AsyncMock()
    monkeypatch.setattr(login, "async_login", handler)
    args = object()

    login.start(args)

    handler.assert_awaited_once_with(args)


@pytest.mark.parametrize("configured_handle", ["", "test-handle"])
def test_login_polls_for_solved_cookie_and_persists_state(
    login_flow, boj_config, monkeypatch, capsys, configured_handle
):
    login = login_flow.login
    old_browser = Path(boj_config.conf["browser_cookies"])
    old_browser.write_bytes(b"\x80\x04legacy artifact")
    old_state = Path(boj_config.conf["state_path"])
    old_state.write_text('{"solved_handle": "legacy"}', encoding="utf-8")
    token = cookie("solvedacToken", ".solved.ac")
    other_token = cookie("solvedacToken", "example.test")
    login_flow.context.cookies.side_effect = [[other_token], [token]]
    browser_state = {"cookies": [token], "origins": [{"origin": "https://solved.ac", "localStorage": []}]}
    login_flow.context.storage_state.return_value = browser_state
    sleep = AsyncMock()
    monkeypatch.setattr(login, "asyncio", SimpleNamespace(get_running_loop=asyncio.get_running_loop, sleep=sleep))
    boj_config.conf["solved_handle"] = configured_handle

    asyncio.run(login.async_login(None))

    login_flow.opened.assert_called_once_with(headless=False, restore=False)
    login_flow.page.goto.assert_awaited_once_with("https://solved.ac/ko/login", wait_until="domcontentloaded")
    login_flow.page.get_by_role.assert_called_once_with("button", name="BOJ로 로그인", exact=True)
    login_flow.sso_button.click.assert_awaited_once_with(timeout=30_000)
    login_flow.username.wait_for.assert_awaited_once_with(timeout=60_000)
    assert login_flow.page.locator.call_args_list == [
        call('form#login_form input[name="login_user_id"]'),
        call('form#login_form input[name="auto_login"]'),
        call('form#login_form input[name="login_password"]'),
        call('form#login_form button[type="submit"]'),
    ]
    login_flow.checkbox.check.assert_awaited_once_with()
    login_flow.username.fill.assert_awaited_once_with("test-user")
    login_flow.password.fill.assert_awaited_once_with("test-password")
    login_flow.login_button.click.assert_awaited_once_with()
    sleep.assert_awaited_once_with(1)
    expected = {
        "cookies": [token],
        "user_agent": "test browser",
        "solved_handle": configured_handle or "test-user",
    }
    assert json.loads(Path(boj_config.state_path).read_text(encoding="utf-8")) == expected
    assert boj_config.state == expected
    saved_browser_state = Path(boj_config.browser_state_path)
    assert json.loads(saved_browser_state.read_text(encoding="utf-8")) == browser_state
    assert old_browser.read_bytes() == b"\x80\x04legacy artifact"
    assert old_state == Path(boj_config.state_path)
    assert json.loads(old_state.read_text(encoding="utf-8")) == expected
    login_flow.context.storage_state.assert_awaited_once_with()
    login_flow.closed.assert_called_once_with()
    assert "LOGIN SUCCESSFUL" in capsys.readouterr().out


def test_shared_state_preserves_session_cookies_for_old_http_clients(login_flow, boj_config):
    session_cookie = {
        "name": "session", "value": "synthetic", "domain": "www.acmicpc.net", "path": "/",
        "expires": -1,
    }
    persistent_cookie = dict(session_cookie, name="persistent", expires=2145916800)
    browser_state = {"cookies": [session_cookie, persistent_cookie], "origins": []}
    login_flow.context.storage_state.return_value = browser_state

    asyncio.run(login_flow.login._save_state(login_flow.page, "test-user"))

    saved = json.loads(Path(boj_config.state_path).read_text(encoding="utf-8"))
    assert saved["cookies"] == [
        {key: value for key, value in session_cookie.items() if key != "expires"}, persistent_cookie,
    ]
    assert boj_config.state == saved
    assert session_cookie["expires"] == -1
    assert json.loads(Path(boj_config.browser_state_path).read_text(encoding="utf-8")) == browser_state


def test_login_waits_for_solved_button_handler_before_clicking(login_flow, monkeypatch):
    login = login_flow.login
    login_flow.sso_button.evaluate.side_effect = [False, False, True]
    token = cookie("solvedacToken", ".solved.ac")
    login_flow.context.cookies.return_value = [token]
    login_flow.context.storage_state.return_value = {"cookies": [token], "origins": []}

    async def wait_for_handler(delay):
        assert delay == 0.1
        login_flow.sso_button.click.assert_not_awaited()

    sleep = AsyncMock(side_effect=wait_for_handler)
    monkeypatch.setattr(login, "asyncio", SimpleNamespace(get_running_loop=asyncio.get_running_loop, sleep=sleep))

    asyncio.run(login.async_login(None))

    assert sleep.await_count == 2
    assert login_flow.sso_button.evaluate.await_args_list == [
        call("button => typeof button.onclick === 'function'", isolated_context=False)
    ] * 3
    login_flow.sso_button.click.assert_awaited_once_with(timeout=30_000)


def test_login_reports_button_that_never_becomes_ready(login_flow, monkeypatch):
    times = iter([0, 30])
    timing = SimpleNamespace(get_running_loop=lambda: SimpleNamespace(time=lambda: next(times)), sleep=AsyncMock())
    monkeypatch.setattr(login_flow.login, "asyncio", timing)
    login_flow.sso_button.evaluate.return_value = False

    with pytest.raises(RuntimeError, match="Could not activate the BOJ login button"):
        asyncio.run(login_flow.login.async_login(None))

    login_flow.sso_button.click.assert_not_awaited()
    login_flow.username.fill.assert_not_awaited()
    login_flow.closed.assert_called_once_with()


@pytest.mark.parametrize("host", ["acmicpc.net", "www.acmicpc.net"])
@pytest.mark.parametrize("redirect", ["https://solved.ac/auth/boj/callback", "https:/solved.ac/auth/boj/callback"])
@pytest.mark.parametrize("role", ["link", "button"])
def test_login_approves_solved_sso_once_after_control_appears(login_flow, monkeypatch, host, redirect, role):
    login = login_flow.login
    token = cookie("solvedacToken", ".solved.ac")
    login_flow.context.cookies.side_effect = [[], [], [], [token]]
    login_flow.context.storage_state.return_value = {"cookies": [token], "origins": []}
    approval = getattr(login_flow, "approval_" + role)
    other = login_flow.approval_button if role == "link" else login_flow.approval_link
    approval.is_visible.side_effect = [False, True]
    other.is_visible.return_value = False

    async def show_approval():
        login_flow.page.url = f"https://{host}/sso?sso=synthetic&sig=synthetic&redirect={redirect}"

    login_flow.login_button.click.side_effect = show_approval
    monkeypatch.setattr(login, "asyncio", SimpleNamespace(get_running_loop=asyncio.get_running_loop, sleep=AsyncMock()))

    asyncio.run(login.async_login(None))

    assert approval.is_visible.await_count == 2
    approval.click.assert_awaited_once_with(timeout=30_000)
    other.click.assert_not_awaited()
    assert login_flow.page.get_by_role.call_args_list == [
        call("button", name="BOJ로 로그인", exact=True),
        call("link", name="로그인", exact=True),
        call("button", name="로그인", exact=True),
        call("link", name="로그인", exact=True),
    ] + ([call("button", name="로그인", exact=True)] if role == "button" else [])
    login_flow.context.storage_state.assert_awaited_once_with()


@pytest.mark.parametrize("url", [
    "https://acmicpc.net.example.test/sso",
    "http://acmicpc.net/sso",
    "https://acmicpc.net/login",
])
def test_login_does_not_click_sso_approval_on_other_pages(login_flow, monkeypatch, url):
    token = cookie("solvedacToken", ".solved.ac")
    login_flow.context.cookies.side_effect = [[], [token]]
    login_flow.context.storage_state.return_value = {"cookies": [token], "origins": []}

    async def navigate():
        login_flow.page.url = url

    login_flow.login_button.click.side_effect = navigate
    monkeypatch.setattr(login_flow.login, "asyncio", SimpleNamespace(get_running_loop=asyncio.get_running_loop, sleep=AsyncMock()))

    asyncio.run(login_flow.login.async_login(None))

    login_flow.approval_button.click.assert_not_awaited()
    login_flow.approval_button.is_visible.assert_not_awaited()
    login_flow.approval_link.click.assert_not_awaited()
    login_flow.approval_link.is_visible.assert_not_awaited()


def test_login_rejects_sso_approval_for_another_service(login_flow):
    login_flow.context.cookies.return_value = []

    async def navigate():
        login_flow.page.url = "https://acmicpc.net/sso?redirect=https://example.test/callback"

    login_flow.login_button.click.side_effect = navigate

    with pytest.raises(RuntimeError, match="BOJ SSO did not target the solved.ac callback"):
        asyncio.run(login_flow.login.async_login(None))

    login_flow.approval_button.click.assert_not_awaited()
    login_flow.approval_link.click.assert_not_awaited()
    login_flow.context.storage_state.assert_not_awaited()
    login_flow.closed.assert_called_once_with()


@pytest.mark.parametrize(
    ("scenario", "message"),
    [
        ("missing-button", "Could not activate the BOJ login button"),
        ("wrong-host", "BOJ login did not open on acmicpc.net"),
    ],
)
def test_login_rejects_unexpected_page_and_closes_browser(login_flow, scenario, message):
    if scenario == "missing-button":
        login_flow.sso_button.click.side_effect = PlaywrightTimeout("Missing button")
    else:
        login_flow.page.url = "https://acmicpc.net.example.test/login"

    with pytest.raises(RuntimeError, match=message):
        asyncio.run(login_flow.login.async_login(None))

    login_flow.username.fill.assert_not_awaited()
    login_flow.password.fill.assert_not_awaited()
    login_flow.context.storage_state.assert_not_awaited()
    login_flow.closed.assert_called_once_with()


def test_login_does_not_expose_password_in_error(login_flow):
    login_flow.password.fill.side_effect = PlaywrightError("test-password")
    with pytest.raises(RuntimeError, match="Could not fill the BOJ password field") as error:
        asyncio.run(login_flow.login.async_login(None))
    assert error.value.__suppress_context__
    login_flow.closed.assert_called_once_with()


def test_login_closes_browser_when_cookie_never_arrives(login_flow, monkeypatch):
    times = iter([0, 0, 300])
    sleep = AsyncMock()
    timing = SimpleNamespace(get_running_loop=lambda: SimpleNamespace(time=lambda: next(times)), sleep=sleep)
    monkeypatch.setattr(login_flow.login, "asyncio", timing)
    login_flow.context.cookies.return_value = []

    with pytest.raises(TimeoutError, match="within 300 seconds"):
        asyncio.run(login_flow.login.async_login(None))

    sleep.assert_not_awaited()
    login_flow.context.storage_state.assert_not_awaited()
    login_flow.closed.assert_called_once_with()


def test_refresh_cookie_rebuilds_http_session(login_flow, boj_config, monkeypatch):
    login = login_flow.login
    context = login_flow.context
    browser_state = {"cookies": [cookie("sample", "acmicpc.net")], "origins": []}
    context.storage_state.return_value = browser_state
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
    url = "https://www.acmicpc.net/problem/1000"

    asyncio.run(login.refresh_cookie(url))

    login_flow.opened.assert_called_once_with(headless=True, restore=True)
    login_flow.page.goto.assert_awaited_once_with(url, wait_until="domcontentloaded")
    expected = {
        "cookies": [{"name": "sample", "domain": "acmicpc.net"}],
        "user_agent": "test browser",
        "solved_handle": "existing-handle",
    }
    assert json.loads(Path(boj_config.state_path).read_text(encoding="utf-8")) == expected
    assert json.loads(Path(boj_config.browser_state_path).read_text(encoding="utf-8")) == browser_state
    assert boj_config.state == expected
    assert session_calls == ["close", "open"]
    context.storage_state.assert_awaited_once_with()
    login_flow.closed.assert_called_once_with()


def test_refresh_cookie_stops_at_browser_verification(login_flow, monkeypatch):
    login = login_flow.login
    login_flow.page.goto.return_value = SimpleNamespace(headers={"cf-mitigated": "challenge"})
    close_session = AsyncMock()
    open_session = AsyncMock()
    monkeypatch.setattr(login._http, "close_session", close_session)
    monkeypatch.setattr(login._http, "open_session", open_session)

    with pytest.raises(RuntimeError, match="Browser verification required"):
        asyncio.run(login.refresh_cookie("https://www.acmicpc.net/problem/1000"))

    login_flow.context.storage_state.assert_not_awaited()
    close_session.assert_not_awaited()
    open_session.assert_not_awaited()
    login_flow.closed.assert_called_once_with()
