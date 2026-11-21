import asyncio
import base64
import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def boj_module(boj_config):
    from bojtools import boj

    return boj


@pytest.fixture
def cached_problem(boj_module):
    problem = {
        "pid": 1000,
        "title": "Addition",
        "info": {
            "시간": "1초",
            "메모리": "128 MB",
            "제출": "10",
            "정답": "7",
            "맞힌 사람": "6",
            "정답 비율": "70%",
        },
        "desc": "Add two integers.",
        "input": "Two integers",
        "output": "Their sum",
        "constraints": "-10 to 10",
        "hint": "Use addition",
        "lang": None,
        "spoiler": "",
        "samples": [{"in": "1 2\n", "out": "3\n"}],
        "solved": boj_module.STATUS_NONE,
    }
    boj_module.save_problem_cache(problem)
    return problem


@pytest.fixture
def problem_page(cached_problem):
    table = cached_problem["info"]
    headings = "".join(f"<th>{key}</th>" for key in table)
    values = "".join(f"<td>{value}</td>" for value in table.values())
    return f"""
    <html><body>
      <h1><span id="problem_title">Addition</span></h1>
      <span class="problem-label problem-label-ac"></span>
      <table id="problem-info"><tr>{headings}</tr><tr>{values}</tr></table>
      <div id="problem_description">Add <b>two</b> integers.</div>
      <div id="problem_input">Two integers</div>
      <div id="problem_output">Their sum</div>
      <div id="problem_limit">-10 to 10</div>
      <div id="problem_hint">Use addition</div>
      <a class="spoiler-link">Arithmetic</a>
      <pre class="sampledata" id="sample-output-1">3</pre>
      <pre class="sampledata" id="sample-input-1">1 2</pre>
      <pre class="sampledata" id="sample-input-2">3 4</pre>
      <pre class="sampledata" id="sample-output-2">7</pre>
    </body></html>
    """


@pytest.fixture
def request_mocks(boj_module, monkeypatch):
    http = boj_module._http
    for name in ("open_session", "async_get", "close_session"):
        monkeypatch.setattr(http, name, AsyncMock())
    return http


def test_problem_cache_round_trips_and_replaces(boj_module, cached_problem):
    assert boj_module.get_cached_problem(1001) == []
    assert boj_module.get_cached_problem(1000) == cached_problem

    updated = dict(cached_problem, title="New title")
    boj_module.save_problem_cache(updated)

    assert boj_module.get_cached_problem(1000) == updated


def test_set_problem_status_accepts_only_supported_values(boj_module, cached_problem):
    boj_module.set_problem_status(1000, boj_module.STATUS_AC)
    boj_module.set_problem_status(1000, 99)
    boj_module.set_problem_status(None, boj_module.STATUS_WA)

    assert boj_module.get_cached_problem(1000)["solved"] == boj_module.STATUS_AC


def test_pick_dispatches_and_generates(boj_module, monkeypatch):
    fetch = AsyncMock()
    generate = Mock()
    monkeypatch.setattr(boj_module, "async_pick", fetch)
    monkeypatch.setattr(boj_module, "generate_code", generate)
    monkeypatch.setitem(boj_module.config.conf, "auto_generate", True)
    args = Namespace(pid=1000, force=True)

    boj_module.pick(args, silent=True)

    fetch.assert_awaited_once_with(1000, force=True, silent=True)
    generate.assert_called_once_with(args)


def test_generate_code_preserves_existing_source(boj_module, monkeypatch, tmp_path, capsys):
    template = tmp_path / "template.py"
    template.write_text("print(3)\n", encoding="utf-8")
    monkeypatch.setitem(boj_module.config.conf, "template", str(template))
    args = Namespace(pid=1000)
    target = Path(boj_module.config.conf["code_dir"]) / "1000" / "1000.py"

    boj_module.generate_code(args)
    assert target.read_text(encoding="utf-8") == "print(3)\n"

    target.write_text("print(7)\n", encoding="utf-8")
    boj_module.generate_code(args)
    assert target.read_text(encoding="utf-8") == "print(7)\n"
    assert "File exists" in capsys.readouterr().out


def test_async_pick_uses_cache_and_writes_samples(boj_module, cached_problem, request_mocks, capsys):
    asyncio.run(boj_module.async_pick(1000))

    request_mocks.open_session.assert_not_awaited()
    request_mocks.async_get.assert_not_awaited()
    assert "Addition" in capsys.readouterr().out
    directory = Path(boj_module.config.conf["code_dir"]) / "1000"
    assert (directory / "in1.txt").read_text(encoding="utf-8") == "1 2\n"
    assert (directory / "ans1.txt").read_text(encoding="utf-8") == "3\n"


def test_async_pick_refreshes_cache_and_archives_html(
    boj_module, cached_problem, problem_page, request_mocks,
):
    request_mocks.async_get.return_value = problem_page

    asyncio.run(boj_module.async_pick(1000, force=True, silent=True, save_raw=True))

    request_mocks.open_session.assert_awaited_once_with()
    request_mocks.async_get.assert_awaited_once_with(f"{boj_module.BOJ_HOST}/problem/1000")
    request_mocks.close_session.assert_awaited_once_with()
    problem = boj_module.get_cached_problem(1000)
    assert problem["solved"] == boj_module.STATUS_AC
    assert problem["desc"] == "Add two integers."
    assert problem["info"] == cached_problem["info"]
    assert problem["spoiler"] == "Arithmetic"
    assert problem["samples"] == [{"in": "1 2", "out": "3"}, {"in": "3 4", "out": "7"}]
    directory = Path(boj_module.config.conf["code_dir"])
    assert (directory / "1000.raw").read_text(encoding="utf-8") == problem_page
    assert (directory / "1000" / "in2.txt").read_text(encoding="utf-8") == "3 4"
    assert (directory / "1000" / "ans2.txt").read_text(encoding="utf-8") == "7"


def test_async_pick_rejects_unrecognized_page_and_closes_session(boj_module, request_mocks):
    request_mocks.async_get.return_value = "<html><title>Bad Request</title></html>"

    with pytest.raises(IndexError):
        asyncio.run(boj_module.async_pick(1001, silent=True))

    request_mocks.close_session.assert_awaited_once_with()
    assert boj_module.get_cached_problem(1001) == []


def test_show_problem_displays_translated_text_and_samples(boj_module, cached_problem, capsys):
    translations = [{
        "problem_lang_tcode": "en",
        "title": "Translated title",
        "description": "<p>Translated description</p>",
        "input": "<p>Translated input</p>",
        "output": "<p>Translated output</p>",
        "hint": "<p>Translated hint</p>",
    }]
    encoded = base64.b64encode(json.dumps(translations).encode()).decode()
    problem = dict(cached_problem, lang=encoded)

    boj_module.show_problem(problem)

    output = capsys.readouterr().out
    for text in ("Translated title", "Translated description", "Translated input",
                 "Translated output", "Translated hint", "Samples:", "1 2"):
        assert text in output


def test_problem_info_reports_cached_metadata(boj_module, cached_problem, monkeypatch, capsys):
    boj_module.set_problem_status(1000, boj_module.STATUS_WA)
    cached_level = Mock(return_value={"level": "Bronze V"})
    fetch_level = Mock()
    monkeypatch.setattr(boj_module.solved, "get_cached_level", cached_level)
    monkeypatch.setattr(boj_module.solved, "get_problem_level", fetch_level)

    boj_module.problem_info(Namespace(pid=1000, level=True))

    cached_level.assert_called_once_with(1000)
    fetch_level.assert_not_called()
    output = capsys.readouterr().out
    assert "Wrong answer" in output
    assert "BOJ 1000 Addition (Bronze V)" in output
    assert f"{boj_module.BOJ_HOST}/problem/1000" in output


def test_archive_skips_cached_problem_and_reports_failed_fetch(boj_module, cached_problem, monkeypatch, capsys):
    fetch = AsyncMock(side_effect=RuntimeError("unavailable"))
    monkeypatch.setattr(boj_module, "async_pick", fetch)
    monkeypatch.setattr(boj_module, "time", SimpleNamespace(sleep=Mock()))

    boj_module.archive_prob(Namespace(prob_start=1000, prob_end=1001, force=False))

    fetch.assert_awaited_once_with(1001, force=False, silent=True, save_raw=True)
    assert "Failed to archive : 1001" in capsys.readouterr().out


def test_drop_testcases_handles_empty_sample_values(boj_module):
    problem = {"pid": 1000, "samples": [{"in": None, "out": ""}]}

    boj_module.drop_testcases(problem)

    directory = Path(boj_module.config.conf["code_dir"]) / "1000"
    assert (directory / "in1.txt").read_bytes() == b""
    assert (directory / "ans1.txt").read_bytes() == b""


@pytest.mark.parametrize("already_cached", [False, True], ids=["download", "cache"])
def test_view_solutions_opens_selected_source(
    boj_module, request_mocks, monkeypatch, already_cached,
):
    status = """
    <html><table id="status-table"><tbody><tr id="solution-42">
      <td>42</td><td>sample-user</td><td>1000</td><td>Accepted</td>
      <td>1000<span class="KB-unit"></span></td><td>2<span class="ms-unit"></span></td>
      <td><a href="/source/42">C++</a></td><td></td><td></td>
    </tr></tbody></table></html>
    """
    source = "int main() {}"
    cache = Path(boj_module.config.conf["cache_dir"]) / "1000" / "42.cpp"
    if already_cached:
        cache.parent.mkdir(parents=True)
        cache.write_text(source, encoding="utf-8")
        request_mocks.async_get.side_effect = [status]
    else:
        request_mocks.async_get.side_effect = [
            status, f'<html><textarea name="source">{source}</textarea></html>',
        ]
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    pager = Mock()
    monkeypatch.setattr(boj_module, "system", pager)

    boj_module.view_solutions(Namespace(pid=1000))

    assert cache.read_text(encoding="utf-8") == source
    pager.assert_called_once_with(f'{boj_module.config.conf["pager"]} "{cache}"')
    if not already_cached:
        request_mocks.async_get.assert_awaited_with(f"{boj_module.BOJ_HOST}/source/42")
    request_mocks.close_session.assert_awaited_once_with()
