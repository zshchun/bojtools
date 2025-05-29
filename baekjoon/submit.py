from . import config
from . import _http
from .ui import *
from .util import *
from lxml import etree, html
from urllib.parse import quote_plus
from playwright.async_api import async_playwright
import asyncio
import aiohttp

def submit(args):
    return asyncio.run(async_submit(args))

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
    await async_playwright_submit(url, submit_form)
    #await async_aiohttp_submit(url, submit_form)


async def async_playwright_submit(url, submit_form):
    source_code = open(filename, 'r').read()
    source_code = source_code.replace('\t', ' ' * config.conf['tab_width'])
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=config.state)
        page = await context.new_page()
        response = await page.goto(url)
        print(response.status)
        if response.headers.get("content-type", "").startswith("application/json"):
            print(await response.json())
        else:
            print(await response.text())
        await page.fill("div.CodeMirror.cm-s-default div textarea", source_code)
        await page.click("#submit_button")
        #await browser.close()


async def async_aiohttp_submit(submit_form):
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
        doc = html.fromstring(resp)
        alert = doc.xpath('.//div[@class="alert-body"]')[0].text
        if alert:
            print(BWHITE(alert))
            return
        js = doc.xpath('.//script[@type="text/javascript" and not(@src)]')
        for lines in js:
            for l in lines.text.splitlines():
                if l.find('solution_ids') != -1:
                    sids = ''.join([c for c in l if c in '0123456789,'])
                    sid = sids.split(',')[0]
        print("Waiting")
        ws_url = 'wss://ws-ap1.pusher.com/app/a2cb611847131e062b32?protocol=7&client=js&version=4.2.2&flash=false'
        await _http.websockets(ws_url, display_submit_result, pid=pid, sid=sid)
    finally:
        await _http.close_boj()

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
