from . import config
from . import _http
from .ui import *
from .util import *
from aiohttp import ClientError
from lxml import etree, html
from urllib.parse import quote_plus
import nodriver as uc
import re
import time
import random
import asyncio

ws_url = 'wss://ws-ap1.pusher.com/app/a2cb611847131e062b32?protocol=7&client=js&version=4.2.2&flash=false'


def submit(args):
    uc.loop().run_until_complete(async_submit(args))
#    return asyncio.run(async_submit(args))

async def async_submit(args):
    global pid, ext, filename
    pid = guess_pid(args)
    if not pid:
        print("[!] Invalid problem ID")
        return
    if args.input:
        filename = args.input
    else:
        filename = select_source_code(pid)

    if not filename:
        print("[!] Failed to select a file : {}".format(filename))
        return

    if not filename:
        print("[!] Failed to select a file : {}".format(filename))
        return

    ext = path.splitext(filename)[1].lstrip('.')
    lang = [x['lang_id'] for x in config.conf['lang'] if x['ext'] == ext]
    if not lang or not lang[0] in config.lang_ids:
        print("[!] Unknown file extension")
        return

    lang_id = config.lang_ids[lang[0]]
    if not path.isfile(filename):
        print("[!] File not found : {}".format(filename))
        return

    url = f'https://www.acmicpc.net/submit/{pid}'
    submit_form = {
        'problem_id': str(pid),
        'language': str(lang_id),
        'code_open': config.conf['code_open'],
    }
    await async_nodriver_submit(url, submit_form, pid)


async def is_tab_opened(tab):
    try:
        isopen = await asyncio.wait_for(tab.evaluate(expression="true"), timeout=1)
        return True
    except (ConnectionRefusedError, ConnectionError, AttributeError, asyncio.TimeoutError):
        return False


async def async_nodriver_submit(url, submit_form, pid):
    global _evt
    _evt = None
    source_code = open(filename, 'r').read()
    source_code = source_code.replace('\t', ' ' * config.conf['tab_width'])
    browser = await uc.start(headless=False,
                             browser_executable_path=config.conf['browser'],
                             browser_args=config.conf['browser_args'],
                             lang=config.conf['locale'],)
    await browser.cookies.load(config.conf['browser_cookies'])
#    tab = browser.main_tab
#    tab.add_handler(uc.cdp.network.ResponseReceived, resp_handler)

    tab = await browser.get(url)
    await asyncio.sleep(1)
    await tab
#    await tab.select('#content')
#    await tab.scroll_down(30)
    while True:
        await asyncio.sleep(0.25)
        for i in range(20):
            try:
                btn = await tab.select("#submit_button", timeout = 1)
                attr = btn.attributes
                break
            except (uc.core.connection.ProtocolException, TimeoutError):
                pass
        visible = True
        for i in range(0, len(attr), 2):
            if attr[i] == 'style' and attr[i+1] == 'display: none;':
                visible = False
                break
        if visible: break

    element = await tab.select("div.CodeMirror.cm-s-default div textarea")
    source_code = source_code.replace('\n', '\r')
    await element.send_keys(source_code)
    [await tab.send(uc.cdp.input_.dispatch_key_event("rawKeyDown", windows_virtual_key_code=46)) for i in range(100)]
#    js = "(item) => { item.dispatchEvent(new KeyboardEvent('keydown', {keyCode: 13, bubbles: true})); }"
#    await element.apply(js)
    #element = await tab.select("#cf-chl-widget-n5woi") # submit, "#submit_form > div:nth-child(7) > div > div"

    await tab.sleep(5)
    await btn.click()
    await tab
    await asyncio.sleep(1)
    for i in range(10):
        try:
            await tab.wait_for('#status-table, .alert-body', timeout=1)
            break
        except (uc.core.connection.ProtocolException, TimeoutError):
            pass
#    elems = await tab.select_all('#status-table > tbody:nth-child(2) > tr')
#    sids = []
#    for elem in elems:
#        attr = elem.attributes
#        for i in range(0, len(attr), 2):
#            if attr[i] == 'id':
#                sid = attr[i+1].split('-')[1]
#                sids.append(sid)
#    sid = sids[0]

#    while await is_tab_opened(tab):
#        print(browser._process)
#        print(browser.connection)
#        time.sleep(0.5)
#    for t in browser.tabs:
#        if hasattr(t, 'close'):
#            await t.close()
#    browser.stop()
#    if not await is_tab_opened(tab):
#        return

    try:
        finished = await wait_for_status(await tab.get_content(), pid)
    except (ClientError, asyncio.TimeoutError) as error:
        print(f'[!] Could not receive the BOJ judging result: {error}')
        finished = False
    finally:
        await _http.close_session()
    if finished:
        await asyncio.sleep(10)
    elif not tab.closed:
        print('[!] Check the BOJ page and close the tab when done.')
        while not tab.closed:
            await asyncio.sleep(0.5)

    for t in browser.tabs:
        if not t.closed:
            await t.close()
#    browser.stop()

#    if _evt.response.status != 200:
#        raise Exception("The submit request failed")
#    body, b64 = await tab.send(uc.cdp.network.get_response_body(_evt.request_id))


async def resp_handler(event: uc.cdp.network.ResponseReceived):
    global _evt
    #if event.response.encoded_data_length > 0:
    _evt = event


# async def async_aiohttp_submit(url, params, submit_form, pid):
#     # print(GREEN("[+] Submit {} ({}, {})".format(filename, lang[0], lang_id)))
#     await _http.open_boj()
#     try:
#         resp = await _http.async_get(url, params)
#         doc = html.fromstring(resp)
#         csrf = doc.xpath('.//input[@type="hidden" and @name="csrf_key"]')[0].get("value")
#         form = aiohttp.FormData()
#         for k, v in submit_form.items():
#             form.add_field(k, v)
#         form.add_field('csrf_key', csrf)
#         tab_width = config.conf['tab_width']
#         source_code = open(filename, 'r').read()
#         source_code = source_code.replace('\t', ' ' * tab_width)
#         form.add_field('source', source_code)
#         resp = await _http.async_post(url, params, form)
#         await wait_for_status(resp, pid)
#     finally:
#         await _http.close_boj()


async def wait_for_status(resp, pid):
    doc = html.fromstring(resp or '<html></html>')
    alert = doc.xpath('normalize-space(//*[contains(concat(" ", normalize-space(@class), " "), " alert-body ")])')
    if alert:
        print(BWHITE(alert))
        return False

    rows = doc.xpath('//*[@id="status-table"]//tr[starts-with(@id, "solution-")]')
    if rows and rows[0].xpath('.//a[@href=$problem_url]', problem_url=f'/problem/{pid}'):
        row = rows[0]
        sid = row.get('id').split('-', 1)[1]
        for script in doc.xpath('//script[not(@src)]/text()'):
            ids = re.search(r'\bsolution_ids\s*=\s*\[([^;]*)\]\s*;', script)
            if not ids:
                continue
            result = re.search(rf'\[\s*{re.escape(sid)}\s*,\s*(\d+)\s*\]', ids[1])
            if not result:
                continue
            if int(result[1]) >= 4:
                status = row.xpath('normalize-space(./td[@class="result"])')
                if status:
                    print(f'{sid} : {status}')
                    return True
                break
            print('Waiting')
            await _http.open_session()
            await _http.websockets(ws_url, display_submit_result, pid=pid, sid=sid)
            return True
    print('[!] Could not identify the submission on the BOJ page.')
    return False


async def display_submit_result(data):
    result = data['result']
    msg = "{:8d} : ".format(data['solution_id'])
    if result == 1:
        msg += "Prepare    "
    elif result == 2:
        msg += "Ready      "
    elif result == 3:
        if 'progress' in data:
            msg += "{:3d}%     ".format(data['progress'])
        else:
            msg += "  0%     "
    elif result == 4:
        msg += "{:s}\n{:6d}KB {:6d}ms".format(GREEN("Accepted"), data['memory'], data['time'])
    elif result == 5:
        msg += RED("Wrong Output Format")
    elif result == 6:
        msg += RED("Wrong Answer")
    elif result == 7:
        msg += RED("Time Limit Exceed")
    elif result == 8:
        msg += BLUE("Memory Limit Exceed")
    elif result == 8:
        msg += BLUE("Output Limit Exceed")
    elif result == 10:
        msg += BLUE("Runtime Error")
    elif result == 11:
        msg += BLUE("Compile Error")
    if result >= 4:
        print()
    redraw(msg)
