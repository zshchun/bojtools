import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, call

import pytest
from yarl import URL


@pytest.fixture
def http(boj_config, monkeypatch):
    from bojtools import _http

    monkeypatch.setattr(_http, 'session', None)
    monkeypatch.setattr(_http, 'cookie_jar', None)
    monkeypatch.setattr(_http, 'prev_req_time', None)
    monkeypatch.setattr(
        _http.login,
        'refresh_cookie',
        AsyncMock(side_effect=AssertionError('Unexpected browser refresh')),
    )
    return _http


def _async_context(value):
    context = MagicMock()
    context.__aenter__.return_value = value
    return context


def _http_response(status, body, headers=None):
    return _async_context(SimpleNamespace(status=status, text=AsyncMock(return_value=body), headers=headers or {}))


def test_add_header_updates_supplied_headers(http):
    headers = {'Accept': 'text/html'}

    result = http.add_header({'Accept': 'application/json', 'X-Test': 'value'}, headers)

    assert result is headers
    assert headers == {'Accept': 'application/json', 'X-Test': 'value'}


def test_request_descriptors(http):
    url = http.BOJ_HOST + '/problem/1000'
    data = {'source': 'example'}
    headers = {'Accept': 'text/html'}

    assert http.GET(url, headers) == {'method': http.async_get, 'url': url, 'headers': headers}
    assert http.POST(url, data, headers) == {
        'method': http.async_post,
        'url': url,
        'data': data,
        'headers': headers,
    }


@pytest.mark.parametrize('method', ['get', 'post'])
def test_sync_request_wrappers_forward_arguments_and_record_time(http, monkeypatch, method):
    request = AsyncMock(return_value='')
    monkeypatch.setattr(http, f'async_{method}', request)
    monkeypatch.setattr(http, 'time', SimpleNamespace(time=lambda: 50.0))
    url = http.SOLVED_HOST + '/api/v4/problems'
    params = {'page': 2}
    headers = {'Accept': 'application/json'}

    if method == 'get':
        assert http.get(url, params, headers) is None
        request.assert_awaited_once_with(url, params, headers)
    else:
        data = {'field': 'example'}
        assert http.post(url, params, data, headers) is None
        request.assert_awaited_once_with(url, params, data, headers)
    assert http.prev_req_time == 50.0


def test_urlsopen_returns_get_responses_in_input_order(http, monkeypatch):
    urls = [http.BOJ_HOST + '/problem/1000', http.BOJ_HOST + '/problem/1001']
    request = AsyncMock(side_effect=['first body', 'second body'])
    monkeypatch.setattr(http, 'async_get', request)

    assert http.urlsopen([http.GET(url) for url in urls]) == ['first body', 'second body']
    assert [args[0] for args, _ in request.await_args_list] == urls


@pytest.mark.parametrize('previous_time,expected_delay', [(None, None), (9.5, 0.25), (9.0, None)])
def test_wait_req_delay(http, monkeypatch, previous_time, expected_delay):
    sleep = Mock()
    monkeypatch.setattr(http, 'prev_req_time', previous_time)
    monkeypatch.setattr(http, 'time', SimpleNamespace(time=lambda: 10.0, sleep=sleep))

    http.wait_req_delay()

    if expected_delay is None:
        sleep.assert_not_called()
    else:
        sleep.assert_called_once_with(expected_delay)


@pytest.mark.parametrize(('host', 'status'), [('BOJ_HOST', 200), ('BOJ_HOST', 400), ('SOLVED_HOST', 403)])
def test_async_get_returns_body_without_refresh(http, monkeypatch, host, status):
    url = getattr(http, host) + '/example'
    params = {'page': 2}
    response = _http_response(status, '<html>example response</html>')
    session = SimpleNamespace(get=Mock(return_value=response))
    monkeypatch.setattr(http, 'session', session)

    result = asyncio.run(http.async_get(url, params))

    assert result == '<html>example response</html>'
    session.get.assert_called_once_with(url, params=params, headers=http.default_headers)
    http.login.refresh_cookie.assert_not_awaited()
    response.__aexit__.assert_awaited_once()


def test_async_get_retries_boj_403_once_after_session_refresh(http, monkeypatch):
    url = http.BOJ_HOST + '/problem/1000'
    params = {'view': 'sample'}
    headers = {'Accept': 'text/html'}
    first_response = _http_response(403, 'first response')
    second_response = _http_response(403, 'still forbidden')
    before_refresh = SimpleNamespace(get=Mock(return_value=first_response))
    after_refresh = SimpleNamespace(get=Mock(return_value=second_response))
    monkeypatch.setattr(http, 'session', before_refresh)

    async def refresh(url):
        first_response.__aexit__.assert_awaited_once()
        monkeypatch.setattr(http, 'session', after_refresh)

    refresh_cookie = AsyncMock(side_effect=refresh)
    sleep = AsyncMock()
    monkeypatch.setattr(http.login, 'refresh_cookie', refresh_cookie)
    monkeypatch.setattr(http, 'asyncio', SimpleNamespace(sleep=sleep))

    result = asyncio.run(http.async_get(url, params, headers))

    assert result == 'still forbidden'
    refresh_cookie.assert_awaited_once_with(url)
    sleep.assert_awaited_once_with(1)
    before_refresh.get.assert_called_once_with(url, params=params, headers=headers)
    after_refresh.get.assert_called_once_with(url, params=params, headers=headers)
    second_response.__aexit__.assert_awaited_once()


@pytest.mark.parametrize('method', ['get', 'post'])
def test_http_browser_verification_is_reported_without_refresh(http, monkeypatch, method):
    url = http.BOJ_HOST + '/problem/1000'
    response = _http_response(403, 'verify in browser', {'cf-mitigated': 'challenge'})
    request = Mock(return_value=response)
    monkeypatch.setattr(http, 'session', SimpleNamespace(**{method: request}))

    with pytest.raises(RuntimeError, match='Browser verification required'):
        asyncio.run(getattr(http, f'async_{method}')(url))

    request.assert_called_once()
    http.login.refresh_cookie.assert_not_awaited()
    response.__aexit__.assert_awaited_once()


def test_async_post_forwards_form_and_returns_response_body(http, monkeypatch):
    url = http.SOLVED_HOST + '/example'
    data = {'name': 'sample'}
    params = {'page': 1}
    response = _http_response(400, 'invalid form')
    session = SimpleNamespace(post=Mock(return_value=response))
    monkeypatch.setattr(http, 'session', session)

    result = asyncio.run(http.async_post(url, params=params, data=data))

    assert result == 'invalid form'
    session.post.assert_called_once_with(url, params=params, headers=http.default_headers, data=data)
    response.__aexit__.assert_awaited_once()


@pytest.mark.parametrize('method', ['get', 'post'])
def test_http_rejects_unsupported_host_before_request(http, monkeypatch, method):
    session = Mock()
    monkeypatch.setattr(http, 'session', session)

    with pytest.raises(Exception, match='URLs must contain'):
        asyncio.run(getattr(http, f'async_{method}')('https://example.invalid/'))

    assert session.mock_calls == []


def test_set_cookie_without_login_initializes_empty_jar(http, boj_config, monkeypatch, capsys):
    monkeypatch.delattr(boj_config, 'state', raising=False)

    asyncio.run(http.set_cookie())

    assert list(http.cookie_jar) == []
    assert 'Please log in first.' in capsys.readouterr().out


def test_set_cookie_restores_synthetic_browser_cookie_attributes(http, boj_config, monkeypatch):
    monkeypatch.setattr(
        boj_config,
        'state',
        {
            'cookies': [
                {
                    'name': 'example_session',
                    'value': 'test-value',
                    'path': '/example',
                    'domain': '.acmicpc.net',
                    'expires': 2145916800,
                    'secure': True,
                    'httpOnly': True,
                    'sameSite': 'Lax',
                }
            ]
        },
        raising=False,
    )

    asyncio.run(http.set_cookie())

    cookie, = list(http.cookie_jar)
    assert (cookie.key, cookie.value) == ('example_session', 'test-value')
    assert cookie['domain'] == 'acmicpc.net'
    assert cookie['path'] == '/example'
    assert cookie['expires'] == 'Fri, 01 Jan 2038 00:00:00 GMT'
    assert cookie['secure'] is True
    assert cookie['httponly'] is True
    assert cookie['samesite'] == 'Lax'


def test_set_cookie_keeps_host_session_cookie_and_skips_protection_cookies(http, boj_config):
    def cookie(name, domain, expires=-1):
        return {'name': name, 'value': 'test', 'domain': domain, 'path': '/', 'expires': expires}

    boj_config.state['cookies'] = [
        cookie('example_session', 'www.acmicpc.net'),
        cookie('cf_clearance', '.acmicpc.net', expires=2145916800),
        cookie('__cf_bm', '.acmicpc.net'),
        cookie('unrelated', 'example.invalid'),
    ]
    asyncio.run(http.set_cookie())

    saved, = list(http.cookie_jar)
    assert saved.key == 'example_session'
    assert not saved['expires']
    assert 'example_session' in http.cookie_jar.filter_cookies(URL('https://www.acmicpc.net/'))
    assert not http.cookie_jar.filter_cookies(URL('https://sub.www.acmicpc.net/'))


def test_open_session_reuses_client_and_cookie_jar_until_close(http, monkeypatch):
    cookie_jar = object()
    first = _async_context(None)
    second = _async_context(None)
    first.__aenter__.return_value = first
    second.__aenter__.return_value = second
    client_session = Mock(side_effect=[first, second])

    async def set_cookie():
        monkeypatch.setattr(http, 'cookie_jar', cookie_jar)

    initialize_cookie = AsyncMock(side_effect=set_cookie)
    monkeypatch.setattr(http, 'set_cookie', initialize_cookie)
    monkeypatch.setattr(http, 'aiohttp', SimpleNamespace(ClientSession=client_session))

    async def check_session_lifecycle():
        await http.open_session()
        assert http.session is first
        await http.open_session()
        assert http.session is first
        client_session.assert_called_once_with(cookie_jar=cookie_jar)

        await http.close_session()
        assert http.session is None
        await http.close_session()
        first.__aexit__.assert_awaited_once_with(None, None, None)

        await http.open_session()
        assert http.session is second
        await http.close_session()
        second.__aexit__.assert_awaited_once_with(None, None, None)

    asyncio.run(check_session_lifecycle())

    initialize_cookie.assert_awaited_once_with()
    assert client_session.call_args_list == [call(cookie_jar=cookie_jar), call(cookie_jar=cookie_jar)]


def _ws_event(http, event, data=None):
    payload = {'event': event}
    if data is not None:
        payload['data'] = json.dumps(data)
    return SimpleNamespace(type=http.aiohttp.WSMsgType.TEXT, data=json.dumps(payload))


@pytest.mark.parametrize(('result', 'cache_status'), [(4, 'STATUS_AC'), (6, 'STATUS_WA')])
def test_websocket_subscribes_and_updates_problem_on_final_result(http, monkeypatch, result, cache_status):
    sid, pid = 123, 1000
    loading = {'result': 2}
    final = {'result': result}
    ws = MagicMock(send_str=AsyncMock())
    ws.__aiter__.return_value = [
        _ws_event(http, 'pusher:connection_established'),
        _ws_event(http, 'pusher_internal:subscription_succeeded'),
        _ws_event(http, 'update', loading),
        _ws_event(http, 'update', final),
        _ws_event(http, 'update', {'result': 99}),
    ]
    connection = _async_context(ws)
    monkeypatch.setattr(http, 'session', SimpleNamespace(ws_connect=Mock(return_value=connection)))
    update_status = Mock()
    monkeypatch.setattr(http.boj, 'set_problem_status', update_status)
    callback = AsyncMock()
    url = 'wss://example.invalid/status'

    asyncio.run(http.websockets(url, callback, pid=pid, sid=sid))

    http.session.ws_connect.assert_called_once_with(url)
    ws.send_str.assert_awaited_once()
    assert json.loads(ws.send_str.await_args.args[0]) == {
        'event': 'pusher:subscribe',
        'data': {'channel': 'solution-123'},
    }
    assert callback.await_args_list == [call(loading), call(final)]
    update_status.assert_called_once_with(pid, getattr(http, cache_status))
    connection.__aexit__.assert_awaited_once()


def test_websocket_stops_on_non_text_frame_without_updating_problem(http, monkeypatch):
    ws = MagicMock(send_str=AsyncMock())
    ws.__aiter__.return_value = [
        _ws_event(http, 'pusher:connection_established'),
        SimpleNamespace(type=http.aiohttp.WSMsgType.CLOSE),
        _ws_event(http, 'update', {'result': 4}),
    ]
    connection = _async_context(ws)
    monkeypatch.setattr(http, 'session', SimpleNamespace(ws_connect=Mock(return_value=connection)))
    update_status = Mock()
    monkeypatch.setattr(http.boj, 'set_problem_status', update_status)
    callback = AsyncMock()

    asyncio.run(http.websockets('wss://example.invalid/status', callback))

    ws.send_str.assert_not_awaited()
    callback.assert_not_awaited()
    update_status.assert_not_called()
    connection.__aexit__.assert_awaited_once()
