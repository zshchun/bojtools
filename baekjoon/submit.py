from . import config
from . import _http
from . import ui
from .util import *
from lxml import etree, html
from urllib.parse import quote_plus
import asyncio
import aiohttp

def submit(args):
    return asyncio.run(async_submit(args))

async def async_submit(args):
    pid = guess_pid(args)
    if not pid:
        print("[!] Invalid problem ID")
        return
    if args.input:
        filename = args.input
    else:
        filename = select_source_code(pid)

    submit_form = {
        'problem_id': str(pid),
        'language': str(config.conf['lang_id']),
        'code_open': config.conf['code_open'],
    }
    if not path.isfile(filename):
        print("[!] File not found : {}".format(filename))
        return
    ui.green("[+] Submit {}".format(filename))
    await _http.open_boj()
    try:
        url = 'https://www.acmicpc.net/submit/' + str(pid)
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
            ui.bwhite(alert)
            return
        js = doc.xpath('.//script[@type="text/javascript" and not(@src)]')
        for lines in js:
            for l in lines.text.splitlines():
                if l.find('solution_ids') != -1:
                    sids = ''.join([c for c in l if c in '0123456789,'])
                    sid = sids.split(',')[0]
        print("Waiting")
        ws_url = 'wss://ws-ap1.pusher.com/app/a2cb611847131e062b32?protocol=7&client=js&version=4.2.2&flash=false'
        await _http.websockets(ws_url, display_submit_result, sid=sid)
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
        msg += "{:s}\n{:6d}KB {:6d}ms".format(ui.setcolor("green", "Accepted"), data['memory'], data['time'])
    elif result == 5:
        msg += ui.setcolor('red', "Wrong Output Format")
    elif result == 6:
        msg += ui.setcolor('red', "Wrong Answer")
    elif result == 7:
        msg += ui.setcolor('red', "Time Limit Exceed")
    elif result == 8:
        msg += ui.setcolor('blue', "Memory Limit Exceed")
    elif result == 8:
        msg += ui.setcolor('blue', "Output Limit Exceed")
    elif result == 10:
        msg += ui.setcolor('blue', "Runtime Error")
    elif result == 11:
        msg += ui.setcolor('blue', "Compile Error")
    ui.redraw(msg)
