from . import config
from . import _http
from .ui import *
from .util import *
from lxml import etree, html
from urllib.parse import quote_plus
import nodriver as uc
import time
import random
import asyncio
import aiohttp

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

    url = 'https://www.acmicpc.net/submit/' + str(pid)
    submit_form = {
        'problem_id': str(pid),
        'language': str(lang_id),
        'code_open': config.conf['code_open'],
    }
    await async_nodriver_submit(url, submit_form, pid)
    #await async_aiohttp_submit(url, submit_form, pid)


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
    await tab.scroll_down(30)

    element = await tab.select("div.CodeMirror.cm-s-default div textarea")
    source_code = source_code.replace('\n', '\r')
    await element.send_keys(source_code)
#    js = "(item) => { item.dispatchEvent(new KeyboardEvent('keydown', {keyCode: 13, bubbles: true})); }"
#    await element.apply(js)
    #element = await tab.select("#cf-chl-widget-n5woi") # submit, "#submit_form > div:nth-child(7) > div > div"
    while True:
        time.sleep(0.25)
        btn = await tab.select("#submit_button")
        attr = btn.attributes
        visible = True
        for i in range(0, len(attr), 2):
            if attr[i] == 'style' and attr[i+1] == 'display: none;':
                visible = False
                break
        if visible: break

    await tab.sleep(10)
    await btn.click()
    await tab
    await tab.sleep(10)
    time.sleep(2)
    for i in range(3):
        try:
            await tab.wait_for('div.col-md-12:nth-child(6)', timeout = 1)
            break
        except TimeoutError:
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

    html = await tab.get_content()
    await wait_for_status(html, pid)
    await _http.close_boj()
    time.sleep(10)

    for t in browser.tabs:
        await t.close()
    browser.stop()

#    if _evt.response.status != 200:
#        raise Exception("The submit request failed")
#    body, b64 = await tab.send(uc.cdp.network.get_response_body(_evt.request_id))


async def resp_handler(event: uc.cdp.network.ResponseReceived):
    global _evt
    #if event.response.encoded_data_length > 0:
    _evt = event


async def async_aiohttp_submit(submit_form, pid):
    print(GREEN("[+] Submit {} ({}, {})".format(filename, lang[0], lang_id)))
    await _http.open_boj()
    try:
        resp = await _http.async_get(url)
        doc = html.fromstring(resp)
        csrf = doc.xpath('.//input[@type="hidden" and @name="csrf_key"]')[0].get("value")
        form = aiohttp.FormData()
        for k, v in submit_form.items():
            form.add_field(k, v)
        form.add_field('csrf_key', csrf)
        tab_width = config.conf['tab_width']
        source_code = open(filename, 'r').read()
        source_code = source_code.replace('\t', ' ' * tab_width)
        form.add_field('source', source_code)
        resp = await _http.async_post(url, form)
        await wait_for_status(resp, pid)
    finally:
        await _http.close_boj()


async def wait_for_status(resp, pid):
    doc = html.fromstring(resp)
    alert = doc.xpath('.//div[@class="alert-body"]')[0].text
    if alert:
        print(BWHITE(alert))
        return
# #status-table > tbody:nth-child(2)
#solution-95183678
# xpath /html/body/div[2]/div[2]/div[3]/div[6]/div/table/tbody
    js = doc.xpath('.//script[@type="text/javascript" and not(@src)]')
    for lines in js:
        for l in lines.text.splitlines():
            if l.find('solution_ids') != -1:
                sids = ''.join([c for c in l if c in '0123456789,'])
                sid = sids.split(',')[0]
    print("Waiting")
    await _http.open_boj()
    await _http.websockets(ws_url, display_submit_result, pid=pid, sid=sid)


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
