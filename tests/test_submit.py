import asyncio
from argparse import Namespace
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest
from aiohttp import ClientError
from patchright.async_api import TimeoutError as PlaywrightTimeoutError


@pytest.fixture
def submit_module(boj_config):
    from bojtools import submit

    return submit


def test_submit_runs_submit_coroutine(submit_module, monkeypatch):
    handler = AsyncMock()
    monkeypatch.setattr(submit_module, "async_submit", handler)
    args = object()

    submit_module.submit(args)

    handler.assert_awaited_once_with(args)


@pytest.mark.parametrize(
    ("pid", "filename", "message"),
    [
        (None, "main.py", "Invalid problem ID"),
        (1000, None, "Failed to select a file"),
        (1000, "main.txt", "Unknown file extension"),
        (1000, "missing.py", "File not found"),
    ],
)
def test_async_submit_rejects_bad_input(
    submit_module, monkeypatch, tmp_path, capsys, pid, filename, message
):
    monkeypatch.setattr(submit_module, "guess_pid", lambda args: pid)
    monkeypatch.setattr(submit_module, "select_source_code", Mock(return_value=None))
    submit_in_browser = AsyncMock()
    monkeypatch.setattr(submit_module, "async_playwright_submit", submit_in_browser)
    filename = str(tmp_path / filename) if filename else None

    asyncio.run(submit_module.async_submit(Namespace(pid=pid, input=filename)))

    submit_in_browser.assert_not_awaited()
    assert message in capsys.readouterr().out


@pytest.mark.parametrize("explicit_filename", [True, False])
@pytest.mark.parametrize(("extension", "language_id"), [("py", 28), ("rs", 113), ("java", 93), ("go", 12)])
def test_async_submit_dispatches_normalized_problem_and_source(
    submit_module, monkeypatch, tmp_path, explicit_filename, extension, language_id
):
    source = tmp_path / f"main.{extension}"
    source.write_text("print(42)\n")
    select_source = Mock(return_value=str(source))
    submit_in_browser = AsyncMock()
    monkeypatch.setattr(submit_module, "select_source_code", select_source)
    monkeypatch.setattr(submit_module, "async_playwright_submit", submit_in_browser)
    args = Namespace(pid=1000, input=str(source) if explicit_filename else None)

    asyncio.run(submit_module.async_submit(args))

    if explicit_filename:
        select_source.assert_not_called()
    else:
        select_source.assert_called_once_with(1000)
    submit_in_browser.assert_awaited_once_with(
        "https://www.acmicpc.net/submit/1000", str(source), 1000, language_id
    )


def status_page(result_code, *, status="Accepted", problem_id=1000):
    return f"""
        <table id="status-table">
            <tr id="solution-42">
                <td><a href="/problem/{problem_id}">Problem</a></td>
                <td class="result"><span>{status}</span></td>
            </tr>
        </table>
        <script>let unrelated = [42, 99];</script>
        <script>let solution_ids = [ [99, 4], [ 42, {result_code} ], ];</script>
    """


@pytest.fixture
def status_session(submit_module, monkeypatch):
    session = SimpleNamespace(open=AsyncMock(), websocket=AsyncMock())
    monkeypatch.setattr(submit_module._http, "open_session", session.open)
    monkeypatch.setattr(submit_module._http, "websockets", session.websocket)
    return session


def test_wait_for_status_prints_existing_final_result(submit_module, status_session, capsys):
    assert asyncio.run(submit_module.wait_for_status(status_page(4), 1000)) is True

    assert "42 : Accepted" in capsys.readouterr().out
    status_session.open.assert_not_awaited()
    status_session.websocket.assert_not_awaited()


def test_wait_for_status_recovers_final_result_after_pending_page(submit_module, monkeypatch, capsys):
    pending = SimpleNamespace(
        ok=True, json=AsyncMock(return_value={"solution_id": "42", "result": "3", "progress": "15"}),
        dispose=AsyncMock(),
    )
    final = SimpleNamespace(
        ok=True, json=AsyncMock(return_value={"solution_id": "42", "result": "4", "memory": "100", "time": "2"}),
        dispose=AsyncMock(),
    )
    post = AsyncMock(side_effect=[pending, final])
    page = SimpleNamespace(url="https://acmicpc.net/status", request=SimpleNamespace(post=post), is_closed=lambda: False)
    update = Mock()
    monkeypatch.setattr(submit_module.boj, "set_problem_status", update)
    monkeypatch.setattr(submit_module.asyncio, "sleep", AsyncMock())

    assert asyncio.run(submit_module.wait_for_status(status_page(3), 1000, page)) is True

    output = capsys.readouterr().out
    assert "Waiting" in output and "15%" in output and "Accepted" in output
    assert post.await_count == 2
    assert post.await_args.args == ("https://acmicpc.net/status/ajax",)
    assert post.await_args.kwargs["form"] == {"solution_id": "42"}
    pending.dispose.assert_awaited_once()
    final.dispose.assert_awaited_once()
    update.assert_called_once_with(1000, submit_module.STATUS_AC)


def test_wait_for_status_stops_polling_when_endpoint_does_not_respond(submit_module, monkeypatch, capsys):
    post = AsyncMock(side_effect=PlaywrightTimeoutError("no response"))
    page = SimpleNamespace(url="https://acmicpc.net/status", request=SimpleNamespace(post=post), is_closed=lambda: False)
    monkeypatch.setattr(submit_module, "JUDGING_TIMEOUT", 0.01)

    assert asyncio.run(submit_module.wait_for_status(status_page(3), 1000, page)) is False

    post.assert_awaited()
    assert "No final judging result" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ('<div class="alert-body alert">Submission <b>rejected</b></div>', "Submission rejected"),
        ("", "Could not identify the submission"),
        (status_page(3, problem_id=1001), "Could not identify the submission"),
        (status_page(4, status=""), "Could not identify the submission"),
        (status_page(3).replace("[ 42, 3 ]", "[ 43, 3 ]"), "Could not identify the submission"),
    ],
)
def test_wait_for_status_reports_unusable_page(
    submit_module, status_session, capsys, response, message
):
    assert asyncio.run(submit_module.wait_for_status(response, 1000)) is False

    assert message in capsys.readouterr().out
    status_session.open.assert_not_awaited()
    status_session.websocket.assert_not_awaited()


@pytest.mark.parametrize(
    ("result", "details", "expected"),
    [
        (1, {}, "Prepare"),
        (2, {}, "Ready"),
        (3, {}, "0%"),
        (3, {"progress": 37}, "37%"),
        (4, {"memory": 128, "time": 42}, "Accepted"),
        (5, {}, "Wrong Output Format"),
        (6, {}, "Wrong Answer"),
        (7, {}, "Time Limit Exceed"),
        (8, {}, "Memory Limit Exceed"),
        (10, {}, "Runtime Error"),
        (11, {}, "Compile Error"),
    ],
)
def test_display_submit_result_formats_judge_update(submit_module, monkeypatch, result, details, expected):
    redraw = Mock()
    monkeypatch.setattr(submit_module, "redraw", redraw)

    asyncio.run(submit_module.display_submit_result({"solution_id": 42, "result": result, **details}))

    redraw.assert_called_once()
    message = redraw.call_args.args[0]
    assert "42 :" in message
    assert expected in message
    if result == 4:
        assert "128KB" in message
        assert "42ms" in message


@pytest.fixture
def browser_submission(submit_module, monkeypatch, tmp_path):
    url = "https://www.acmicpc.net/submit/1000"
    source = tmp_path / "main.py"
    source.write_text("def example():\n\tpass\n")
    button = SimpleNamespace(wait_for=AsyncMock(), click=AsyncMock())
    language = SimpleNamespace(select_option=AsyncMock(), evaluate=AsyncMock())
    editor = SimpleNamespace(wait_for=AsyncMock(), evaluate=AsyncMock())
    result = SimpleNamespace(wait_for=AsyncMock())
    locators = {
        "#submit_button": button,
        'select[name="language"], select[name="language_id"], select#language': language,
        "div.CodeMirror": editor,
        "#status-table:visible, .alert-body:visible": SimpleNamespace(first=result),
    }
    page = SimpleNamespace(
        goto=AsyncMock(),
        wait_for_load_state=AsyncMock(),
        locator=Mock(side_effect=locators.__getitem__),
        content=AsyncMock(return_value="<html></html>"),
        wait_for_event=AsyncMock(),
        closed=False,
        url=url,
    )
    page.is_closed = lambda: page.closed
    page_exited = Mock()

    @asynccontextmanager
    async def open_page(**options):
        try:
            yield page
        finally:
            page_exited()

    browser_page = Mock(side_effect=open_page)
    wait_for_result = AsyncMock()
    close_session = AsyncMock()
    monkeypatch.setattr(submit_module, "browser_page", browser_page)
    monkeypatch.setattr(submit_module, "wait_for_status", wait_for_result)
    monkeypatch.setattr(submit_module._http, "close_session", close_session)
    return SimpleNamespace(
        url=url, source=str(source), browser_page=browser_page, page=page, page_exited=page_exited,
        button=button, language=language, editor=editor, result=result, wait_for_result=wait_for_result,
        close_session=close_session,
    )


@pytest.mark.parametrize("available", [True, False])
def test_browser_selects_configured_runtime_before_submit(submit_module, browser_submission, available):
    flow = browser_submission
    flow.wait_for_result.return_value = True

    async def wait_for_load(*args):
        flow.button.wait_for.assert_awaited_once()
        flow.language.select_option.assert_not_awaited()
        flow.editor.evaluate.assert_not_awaited()
        flow.button.click.assert_not_awaited()

    async def select_option(**kwargs):
        flow.page.wait_for_load_state.assert_awaited_once_with("load")
        flow.editor.evaluate.assert_not_awaited()
        flow.button.click.assert_not_awaited()
        if not available:
            raise PlaywrightTimeoutError("No such option")

    flow.page.wait_for_load_state.side_effect = wait_for_load
    flow.language.select_option.side_effect = select_option
    asyncio.run(submit_module.async_playwright_submit(flow.url, flow.source, 1000, 113))

    flow.language.select_option.assert_awaited_once_with(value="113", force=True, timeout=10_000)
    if available:
        flow.language.evaluate.assert_awaited_once()
        assert "chosen:updated" in flow.language.evaluate.await_args.args[0]
        assert flow.language.evaluate.await_args.kwargs == {"isolated_context": False}
        flow.editor.evaluate.assert_awaited_once()
        flow.button.click.assert_awaited_once()
    else:
        flow.language.evaluate.assert_not_awaited()
        flow.editor.evaluate.assert_not_awaited()
        flow.button.click.assert_not_awaited()
        flow.page.wait_for_event.assert_awaited_once_with("close", timeout=0)


@pytest.mark.parametrize("outcome", [True, False, ClientError, TimeoutError])
def test_browser_submission_retains_tab_for_inspection_only_when_needed(
    submit_module, boj_config, browser_submission, capsys, outcome
):
    flow = browser_submission
    if isinstance(outcome, type):
        flow.wait_for_result.side_effect = outcome
    else:
        flow.wait_for_result.return_value = outcome

    async def wait_for_close(event, *, timeout):
        assert event == "close"
        if flow.page.wait_for_event.await_count == 1:
            assert timeout == 0  # While the status and browser close compete.
            await asyncio.Future()
        else:
            assert flow.page.wait_for_event.await_count == 2
            if timeout == 10_000:
                raise PlaywrightTimeoutError("grace period elapsed")
            assert timeout == 0
            flow.page.closed = True

    flow.page.wait_for_event.side_effect = wait_for_close
    asyncio.run(submit_module.async_playwright_submit(flow.url, flow.source, 1000))

    flow.browser_page.assert_called_once_with(headless=False, restore=True)
    flow.page.goto.assert_awaited_once_with(flow.url, wait_until="domcontentloaded")
    flow.button.wait_for.assert_awaited_once_with(state="visible", timeout=300_000)
    flow.editor.wait_for.assert_awaited_once_with(state="visible", timeout=10_000)
    indentation = " " * boj_config.conf["tab_width"]
    flow.editor.evaluate.assert_awaited_once_with(
        "(element, source) => element.CodeMirror.setValue(source)",
        f"def example():\n{indentation}pass\n",
        isolated_context=False,
    )
    flow.button.click.assert_awaited_once_with(timeout=300_000)
    flow.result.wait_for.assert_awaited_once_with(state="visible", timeout=10_000)
    flow.wait_for_result.assert_awaited_once_with("<html></html>", 1000, flow.page)
    flow.close_session.assert_awaited_once()
    flow.page_exited.assert_called_once()
    stdout = capsys.readouterr().out
    assert "Complete any browser verification" in stdout
    assert flow.page.wait_for_event.await_args_list == [
        call("close", timeout=0), call("close", timeout=10_000 if outcome is True else 0),
    ]
    if outcome is True:
        assert "close the tab when done" not in stdout
    else:
        assert flow.page.closed
        assert "close the tab when done" in stdout
    if isinstance(outcome, type):
        assert "Could not receive the BOJ judging result" in stdout


@pytest.mark.parametrize("during_load", [False, True])
def test_submission_timeout_leaves_browser_available(submit_module, browser_submission, capsys, during_load):
    flow = browser_submission
    wait = flow.page.wait_for_load_state if during_load else flow.button.wait_for
    wait.side_effect = PlaywrightTimeoutError("form readiness timed out")

    asyncio.run(submit_module.async_playwright_submit(flow.url, flow.source, 1000))

    flow.editor.evaluate.assert_not_awaited()
    flow.button.click.assert_not_awaited()
    flow.wait_for_result.assert_not_awaited()
    flow.close_session.assert_not_awaited()
    flow.page.wait_for_event.assert_awaited_once_with("close", timeout=0)
    flow.page_exited.assert_called_once()
    stdout = capsys.readouterr().out
    assert "Could not complete the BOJ submission" in stdout
    assert "close the tab when done" in stdout


@pytest.mark.parametrize("redirect", [
    "https://acmicpc.net/submit/1000",
    "https://acmicpc.net:443/submit/1000",
    "https://www.acmicpc.net:443/submit/1000",
])
def test_canonical_boj_redirect_submits(submit_module, browser_submission, redirect):
    flow = browser_submission
    flow.page.url = redirect
    flow.wait_for_result.return_value = True

    async def wait_for_close(event, *, timeout):
        if timeout == 0:
            await asyncio.Future()
        raise PlaywrightTimeoutError("grace period elapsed")

    flow.page.wait_for_event.side_effect = wait_for_close
    asyncio.run(submit_module.async_playwright_submit(flow.url, flow.source, 1000))

    flow.editor.evaluate.assert_awaited_once()
    flow.button.click.assert_awaited_once_with(timeout=300_000)
    flow.wait_for_result.assert_awaited_once_with("<html></html>", 1000, flow.page)
    flow.page_exited.assert_called_once()


@pytest.mark.parametrize("redirect", [
    "https://example.invalid/submit/1000",
    "https://acmicpc.net.example.invalid/submit/1000",
    "http://acmicpc.net/submit/1000",
    "https://acmicpc.net:8443/submit/1000",
    "https://www.acmicpc.net/submit/1001",
    "https://www.acmicpc.net/login",
])
def test_unexpected_redirect_does_not_fill_editor(submit_module, browser_submission, capsys, redirect):
    flow = browser_submission
    flow.page.url = redirect

    asyncio.run(submit_module.async_playwright_submit(flow.url, flow.source, 1000))

    flow.editor.evaluate.assert_not_awaited()
    flow.button.click.assert_not_awaited()
    flow.page_exited.assert_called_once()
    assert "unexpected site" in capsys.readouterr().out


def test_browser_close_before_waiter_starts_cancels_judging(submit_module, browser_submission):
    flow = browser_submission
    cancelled = Mock()

    async def wait_for_result(*args):
        try:
            await asyncio.Future()
        finally:
            cancelled()

    async def run():
        close_listener = None

        async def wait_for_close(event, *, timeout):
            nonlocal close_listener
            close_listener = asyncio.get_running_loop().create_future()
            await close_listener

        def close_page():
            flow.page.closed = True
            if close_listener is not None:
                close_listener.set_result(None)

        flow.wait_for_result.side_effect = wait_for_result
        flow.page.wait_for_event.side_effect = wait_for_close

        async def close_during_result_wait():
            asyncio.get_running_loop().call_soon(close_page)
            return await submit_module._wait_for_result(flow.page, "<html></html>", 1000)

        return await asyncio.wait_for(close_during_result_wait(), timeout=1)

    assert asyncio.run(run()) is False
    assert flow.page.closed
    cancelled.assert_called_once()
    flow.close_session.assert_awaited_once()


def test_browser_close_cancels_pending_judging_result(submit_module, browser_submission):
    flow = browser_submission
    cancelled = Mock()

    async def submit_and_close():
        judging_started = asyncio.Event()

        async def wait_for_result(*args):
            judging_started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled()

        async def wait_for_close(event, *, timeout):
            assert event == "close"
            assert timeout == 0
            await judging_started.wait()
            flow.page.closed = True

        flow.wait_for_result.side_effect = wait_for_result
        flow.page.wait_for_event.side_effect = wait_for_close
        await asyncio.wait_for(submit_module.async_playwright_submit(flow.url, flow.source, 1000), timeout=1)

    asyncio.run(submit_and_close())

    cancelled.assert_called_once()
    flow.page.wait_for_event.assert_awaited_once()
    flow.close_session.assert_awaited_once()
    flow.page_exited.assert_called_once()
