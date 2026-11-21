import asyncio
import json
from argparse import Namespace
from unittest.mock import AsyncMock

import pytest
from lxml import html


@pytest.fixture
def solved_module(boj_config):
    from bojtools import solved

    return solved


@pytest.fixture
def api_item():
    return {
        "level": 6,
        "titles": [
            {"language": "en", "title": "Addition"},
            {"language": "ko-KR", "title": "덧셈"},
        ],
        "problemId": "1000",
        "solvedUserCount": 1200,
    }


@pytest.fixture
def detail_page():
    return """
    <html><main>
      <div>
        <span><img alt="Bronze V" /></span>
        <a href="https://www.acmicpc.net/problem/1000">
          <span data-problem-title="true">A+B</span>
        </a>
      </div>
      <div><p>푼 사람</p><p>1,234</p></div>
    </main></html>
    """


@pytest.fixture
def request_mocks(solved_module, monkeypatch):
    http = solved_module._http
    for name in ("open_session", "async_get", "close_session"):
        monkeypatch.setattr(http, name, AsyncMock())
    return http


def test_extract_problem_from_html_preserves_nested_title(solved_module):
    row = html.fromstring("""
    <tr>
      <td><img alt="Silver V"><span>1000</span></td>
      <td><span class="__Latex__">A<b>+</b>B</span></td>
      <td><div>1,200</div></td><td><div>1.25</div></td>
    </tr>
    """)

    assert solved_module.extract_problem_from_html(row) == {
        "level": "Silver V", "pid": 1000, "title": "A+B",
        "solved_count": 1200, "avg_try": 1.25,
    }


def test_extract_problem_prefers_korean_title(solved_module, api_item):
    assert solved_module.extract_problem(api_item) == {
        "level": "Silver V", "pid": 1000, "title": "덧셈",
        "solved_count": 1200, "avg_try": None,
    }


@pytest.mark.parametrize(("titles", "expected"), [
    ([{"language": "en", "title": "Addition"}], "Addition"),
    ([], "1000"),
])
def test_extract_problem_title_fallback(solved_module, api_item, titles, expected):
    assert solved_module.extract_problem(dict(api_item, titles=titles))["title"] == expected


@pytest.mark.parametrize(("level", "label"), [
    (1, "Bronze V"), ("5", "Bronze I"), (6, "Silver V"), (30, "Ruby I"),
])
def test_lvnum_to_string(solved_module, level, label):
    assert solved_module.lvnum_to_string(level) == label


def test_extract_problem_detail(solved_module, detail_page):
    assert solved_module.extract_problem_detail(detail_page, 1000) == {
        "pid": 1000, "title": "A+B", "level": "Bronze V",
        "solved_count": 1234, "avg_try": None,
    }
    no_count = detail_page.replace("1,234", "unknown")
    assert solved_module.extract_problem_detail(no_count, 1000)["solved_count"] is None


def test_extract_problem_detail_rejects_empty_or_mismatched_page(solved_module, detail_page):
    with pytest.raises(RuntimeError, match="empty problem page"):
        solved_module.extract_problem_detail(" ", 1000)
    with pytest.raises(RuntimeError, match="recognizable problem page for 1001"):
        solved_module.extract_problem_detail(detail_page, 1001)


def test_solved_headers_requires_login_cookie(solved_module, monkeypatch):
    monkeypatch.setattr(solved_module.config, "state", {"cookies": []}, raising=False)
    with pytest.raises(ValueError, match="boj login"):
        solved_module.solved_headers()

    monkeypatch.setattr(solved_module.config, "state", {"cookies": [{"name": "solvedacToken"}]})
    assert solved_module.solved_headers() == solved_module._http.json_headers


def test_unsolved_filter_prefers_config_and_falls_back_to_state(solved_module, monkeypatch):
    monkeypatch.setattr(solved_module.config, "state", {"solved_handle": "cached"}, raising=False)
    monkeypatch.setitem(solved_module.config.conf, "solved_handle", "configured")
    assert solved_module.unsolved_filter() == "-@configured"

    monkeypatch.setitem(solved_module.config.conf, "solved_handle", "")
    assert solved_module.unsolved_filter() == "-@cached"

    monkeypatch.setattr(solved_module.config, "state", {})
    with pytest.raises(ValueError, match="Set solved_handle"):
        solved_module.unsolved_filter()


@pytest.mark.parametrize(("response", "message"), [
    ("<html>Bad Request</html>", "non-JSON response"),
    ('{"error":{"code":"INVALID","message":"Bad request"}}', "INVALID: Bad request"),
    ('{"diagnostics":[{"message":"Invalid filter"}]}', "search query: Invalid filter"),
])
def test_async_get_solved_reports_service_errors(
    solved_module, request_mocks, monkeypatch, response, message,
):
    monkeypatch.setattr(solved_module.config, "state", {"cookies": [{"name": "solvedacToken"}]}, raising=False)
    request_mocks.async_get.return_value = response
    url = solved_module.SOLVED_V4_PROBS
    params = {"q": "*1..5", "page": 1}

    with pytest.raises(RuntimeError, match=message):
        asyncio.run(solved_module.async_get_solved(url, params))

    request_mocks.async_get.assert_awaited_once_with(url, params, solved_module._http.json_headers)


def test_pick_random_builds_query_for_reversed_bounds(solved_module, monkeypatch):
    search = AsyncMock()
    monkeypatch.setattr(solved_module, "async_query_solvedac", search)
    monkeypatch.setitem(solved_module.config.conf, "solved_handle", "sample")
    args = Namespace(level_start="g1", level_end="b5", solved_count=50, list=True)

    solved_module.pick_random(args)

    search.assert_awaited_once_with(
        solved_module.SOLVED_V4_PROBS,
        {"q": "(*1..15) (-@sample) (s#50..)", "page": 1, "sort": "random"},
        True,
        rand=True,
    )


def test_pick_class_builds_essential_query_without_login_filter(solved_module, monkeypatch):
    search = AsyncMock()
    monkeypatch.setattr(solved_module, "async_query_solvedac", search)

    solved_module.pick_class(Namespace(level=3, essential=True, all=True, list=False))

    search.assert_awaited_once_with(
        solved_module.SOLVED_V4_PROBS,
        {"q": "solvable:true in_class_essentials:3", "page": 1, "sort": "random"},
        False,
        rand=True,
    )


@pytest.mark.parametrize(("command", "args", "message"), [
    ("pick_random", Namespace(level_start="unknown", level_end="b5"), "Failed to parse problem level"),
    ("pick_class", Namespace(level=11), "Out of class range"),
])
def test_pick_rejects_invalid_range(solved_module, monkeypatch, capsys, command, args, message):
    search = AsyncMock()
    monkeypatch.setattr(solved_module, "async_query_solvedac", search)

    getattr(solved_module, command)(args)

    search.assert_not_awaited()
    assert message in capsys.readouterr().out


def test_solved_cache_replaces_rows(solved_module, api_item):
    problem = solved_module.extract_problem(api_item)
    assert solved_module.get_cached_level(1000) == {}

    solved_module.save_solved_list([problem])
    assert solved_module.get_cached_level(1000) == problem

    updated = dict(problem, solved_count=1300)
    solved_module.save_solved_list([updated])
    assert solved_module.get_cached_level(1000) == updated


def test_get_problem_level_fetches_detail_and_saves_cache(solved_module, request_mocks, detail_page):
    request_mocks.async_get.return_value = detail_page

    problem = solved_module.get_problem_level(1000)

    request_mocks.async_get.assert_awaited_once_with(f"{solved_module.SOLVED_HOST}/ko/p/1000")
    request_mocks.close_session.assert_awaited_once_with()
    assert problem == solved_module.get_cached_level(1000)
    assert problem["level"] == "Bronze V"


def test_get_problem_level_does_not_cache_invalid_detail(solved_module, request_mocks):
    request_mocks.async_get.return_value = "<html>Unavailable</html>"

    with pytest.raises(RuntimeError, match="recognizable problem page"):
        solved_module.get_problem_level(1000)

    assert solved_module.get_cached_level(1000) == {}
    request_mocks.close_session.assert_awaited_once_with()


@pytest.mark.parametrize("listing", [True, False], ids=["list", "pick"])
def test_async_query_solvedac_caches_results_and_dispatches(
    solved_module, request_mocks, api_item, monkeypatch, capsys, listing,
):
    second = dict(api_item, problemId=1001, titles=[{"language": "en", "title": "Second"}])
    request_mocks.async_get.return_value = json.dumps({"problems": [api_item, second], "total": 2})
    monkeypatch.setattr(solved_module.config, "state", {"cookies": [{"name": "solvedacToken"}]}, raising=False)
    monkeypatch.setattr(solved_module, "randrange", lambda count: 1)
    pick = AsyncMock()
    monkeypatch.setattr(solved_module.boj, "async_pick", pick)
    params = {"q": "*1..10", "page": 1}

    asyncio.run(solved_module.async_query_solvedac(solved_module.SOLVED_V4_PROBS, params, listing, rand=True))

    assert solved_module.get_cached_level(1000)["title"] == "덧셈"
    assert solved_module.get_cached_level(1001)["title"] == "Second"
    request_mocks.open_session.assert_awaited_once_with()
    request_mocks.close_session.assert_awaited_once_with()
    if listing:
        pick.assert_not_awaited()
        output = capsys.readouterr().out
        assert "1000] 덧셈" in output
        assert "1001] Second" in output
    else:
        pick.assert_awaited_once_with(1001)


def test_async_query_solvedac_closes_session_on_empty_list(
    solved_module, request_mocks, monkeypatch, capsys,
):
    search = AsyncMock(return_value={"problems": [], "total": 0})
    monkeypatch.setattr(solved_module, "async_get_solved", search)

    asyncio.run(solved_module.async_query_solvedac(solved_module.SOLVED_V4_PROBS, {}))

    request_mocks.close_session.assert_awaited_once_with()
    assert "List is empty" in capsys.readouterr().out
