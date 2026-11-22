import asyncio
import re
from os import path
from urllib.parse import urlsplit

from aiohttp import ClientError
from lxml import html
from patchright.async_api import Error as PlaywrightError
from patchright.async_api import TimeoutError as PlaywrightTimeoutError

from . import _http, config
from ._browser import browser_page
from .constants import BOJ_HOST
from .ui import BLUE, BWHITE, GREEN, RED, redraw
from .util import guess_pid, select_source_code

ws_url = 'wss://ws-ap1.pusher.com/app/a2cb611847131e062b32?protocol=7&client=js&version=4.2.2&flash=false'


def submit(args):
    return asyncio.run(async_submit(args))


async def async_submit(args):
    pid = guess_pid(args)
    if not pid:
        print("[!] Invalid problem ID")
        return

    filename = args.input or select_source_code(pid)
    if not filename:
        print("[!] Failed to select a file : {}".format(filename))
        return

    ext = path.splitext(filename)[1].lstrip('.')
    lang = [x['lang_id'] for x in config.conf['lang'] if x['ext'] == ext]
    if not lang or lang[0] not in config.lang_ids:
        print("[!] Unknown file extension")
        return

    if not path.isfile(filename):
        print("[!] File not found : {}".format(filename))
        return

    await async_playwright_submit(f'{BOJ_HOST}/submit/{pid}', filename, pid)


async def async_playwright_submit(url, filename, pid):
    with open(filename, 'r') as source:
        source_code = source.read().replace('\t', ' ' * config.conf['tab_width'])

    async with browser_page(headless=False, restore=True) as page:
        finished = False
        try:
            print('Complete any browser verification if prompted.')
            await page.goto(url, wait_until='domcontentloaded')
            button = page.locator('#submit_button')
            await button.wait_for(state='visible', timeout=300_000)
            destination = urlsplit(page.url)
            if (destination.scheme != 'https'
                    or destination.hostname not in ('acmicpc.net', 'www.acmicpc.net')
                    or destination.port not in (None, 443)
                    or destination.path != urlsplit(url).path):
                print('[!] The submission page opened on an unexpected site.')
                return

            # CodeMirror's editor API updates the document used by the normal form submit.
            editor = page.locator('div.CodeMirror')
            await editor.wait_for(state='visible', timeout=10_000)
            # The page attaches CodeMirror in its main JavaScript context.
            await editor.evaluate(
                '(element, source) => element.CodeMirror.setValue(source)', source_code,
                isolated_context=False,
            )
            await button.click(timeout=300_000)
            result = page.locator('#status-table:visible, .alert-body:visible').first
            await result.wait_for(state='visible', timeout=10_000)
            finished = await _wait_for_result(page, await page.content(), pid)
        except PlaywrightError:
            if not page.is_closed():
                print('[!] Could not complete the BOJ submission in the browser.')
        except (ClientError, asyncio.TimeoutError, TimeoutError) as error:
            print(f'[!] Could not receive the BOJ judging result: {error}')

        if not page.is_closed():
            if not finished:
                print('[!] Check the BOJ page and close the tab when done.')
            try:
                await page.wait_for_event('close', timeout=10_000 if finished else 0)
            except PlaywrightTimeoutError:
                pass


async def _wait_for_result(page, content, pid):
    if page.is_closed():
        return False

    async def wait_for_close():
        # The page may close before this scheduled task starts listening.
        if not page.is_closed():
            await page.wait_for_event('close', timeout=0)

    result = asyncio.create_task(wait_for_status(content, pid))
    tab_closed = asyncio.create_task(wait_for_close())
    try:
        done, _ = await asyncio.wait((result, tab_closed), return_when=asyncio.FIRST_COMPLETED)
        return result.result() if result in done else False
    finally:
        for task in (result, tab_closed):
            if not task.done():
                task.cancel()
        await asyncio.gather(result, tab_closed, return_exceptions=True)
        await _http.close_session()


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
