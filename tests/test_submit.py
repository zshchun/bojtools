import asyncio
from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call, mock_open

import pytest
from aiohttp import ClientError


class SubmitTab(SimpleNamespace):
    def __await__(self):
        return iter(())


@pytest.fixture
def submit_module(boj_config, monkeypatch):
    from bojtools import submit

    for name in ("pid", "ext", "filename", "_evt"):
        monkeypatch.setattr(submit, name, None, raising=False)
    return submit


def test_submit_runs_submit_coroutine(submit_module, monkeypatch):
    handler = AsyncMock()
    monkeypatch.setattr(submit_module, "async_submit", handler)
    monkeypatch.setattr(submit_module.uc, "loop", lambda: SimpleNamespace(run_until_complete=asyncio.run))
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
    monkeypatch.setattr(submit_module, "async_nodriver_submit", submit_in_browser)
    filename = str(tmp_path / filename) if filename else None

    asyncio.run(submit_module.async_submit(Namespace(pid=pid, input=filename)))

    submit_in_browser.assert_not_awaited()
    assert message in capsys.readouterr().out


@pytest.mark.parametrize("explicit_filename", [True, False])
def test_async_submit_dispatches_normalized_problem_and_language(
    submit_module, boj_config, monkeypatch, tmp_path, explicit_filename
):
    source = tmp_path / "main.py"
    source.write_text("print(42)\n")
    select_source = Mock(return_value=str(source))
    submit_in_browser = AsyncMock()
    monkeypatch.setattr(submit_module, "select_source_code", select_source)
    monkeypatch.setattr(submit_module, "async_nodriver_submit", submit_in_browser)
    args = Namespace(pid=1000, input=str(source) if explicit_filename else None)

    asyncio.run(submit_module.async_submit(args))

    if explicit_filename:
        select_source.assert_not_called()
    else:
        select_source.assert_called_once_with(1000)
    submit_in_browser.assert_awaited_once_with(
        "https://www.acmicpc.net/submit/1000",
        {"problem_id": "1000", "language": "28", "code_open": boj_config.conf["code_open"]},
        1000,
    )


@pytest.mark.parametrize("error", [None, ConnectionError, AttributeError, TimeoutError])
def test_is_tab_opened_detects_evaluation_failure(submit_module, error):
    evaluate = AsyncMock(side_effect=error)

    assert asyncio.run(submit_module.is_tab_opened(SimpleNamespace(evaluate=evaluate))) is (error is None)
    evaluate.assert_awaited_once_with(expression="true")


def test_response_handler_records_event(submit_module):
    event = object()

    asyncio.run(submit_module.resp_handler(event))

    assert submit_module._evt is event


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


def test_wait_for_status_subscribes_for_pending_result(submit_module, status_session, capsys):
    assert asyncio.run(submit_module.wait_for_status(status_page(3), 1000)) is True

    assert "Waiting" in capsys.readouterr().out
    status_session.open.assert_awaited_once()
    status_session.websocket.assert_awaited_once_with(
        submit_module.ws_url, submit_module.display_submit_result, pid=1000, sid="42"
    )


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


@pytest.mark.parametrize("outcome", [True, False, ClientError, TimeoutError])
def test_browser_submission_retains_tab_for_inspection_only_when_needed(
    submit_module, boj_config, monkeypatch, capsys, outcome
):
    source = mock_open(read_data="def example():\n\tpass\n")
    submit_module.filename = "main.py"
    monkeypatch.setattr(submit_module, "open", source, raising=False)
    button = SimpleNamespace(attributes=[], click=AsyncMock())
    editor = SimpleNamespace(send_keys=AsyncMock())
    tab = SubmitTab(
        select=AsyncMock(side_effect=[button, editor]),
        send=AsyncMock(),
        sleep=AsyncMock(),
        wait_for=AsyncMock(),
        get_content=AsyncMock(return_value="<html></html>"),
        close=AsyncMock(),
        closed=False,
    )
    other_tab = SimpleNamespace(close=AsyncMock(), closed=False)
    browser = SimpleNamespace(
        get=AsyncMock(return_value=tab),
        tabs=[tab, other_tab],
        cookies=SimpleNamespace(load=AsyncMock()),
    )
    start = AsyncMock(return_value=browser)
    wait_for_result = (
        AsyncMock(side_effect=outcome) if isinstance(outcome, type) else AsyncMock(return_value=outcome)
    )
    close_session = AsyncMock()

    async def wait(_delay):
        assert sleep.await_count <= 4, "Submission exceeded the expected number of waits"
        if close_session.await_count and outcome is not True:
            # Once result handling ends, simulate the user closing the tab on the first poll.
            tab.close.assert_not_awaited()
            tab.closed = True

    sleep = AsyncMock(side_effect=wait)
    monkeypatch.setattr(submit_module.uc, "start", start)
    monkeypatch.setattr(submit_module, "wait_for_status", wait_for_result)
    monkeypatch.setattr(submit_module._http, "close_session", close_session)
    monkeypatch.setattr(submit_module, "asyncio", SimpleNamespace(sleep=sleep, TimeoutError=TimeoutError))
    url = "https://www.acmicpc.net/submit/1000"

    asyncio.run(submit_module.async_nodriver_submit(url, {}, 1000))

    assert start.await_args.kwargs["headless"] is False
    source.assert_called_once_with("main.py", "r")
    browser.cookies.load.assert_awaited_once_with(boj_config.conf["browser_cookies"])
    browser.get.assert_awaited_once_with(url)
    assert tab.select.await_args_list == [
        call("#submit_button", timeout=1),
        call("div.CodeMirror.cm-s-default div textarea"),
    ]
    tab.wait_for.assert_awaited_once_with("#status-table, .alert-body", timeout=1)
    indentation = " " * boj_config.conf["tab_width"]
    editor.send_keys.assert_awaited_once_with(f"def example():\r{indentation}pass\r")
    button.click.assert_awaited_once()
    wait_for_result.assert_awaited_once_with("<html></html>", 1000)
    close_session.assert_awaited_once()
    other_tab.close.assert_awaited_once()
    stdout = capsys.readouterr().out
    if outcome is True:
        assert call(10) in sleep.await_args_list
        assert "close the tab when done" not in stdout
        tab.close.assert_awaited_once()
    else:
        assert tab.closed
        assert "close the tab when done" in stdout
        tab.close.assert_not_awaited()
    if isinstance(outcome, type):
        assert "Could not receive the BOJ judging result" in stdout
