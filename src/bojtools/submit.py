import asyncio
import re
from os import path
from urllib.parse import urlsplit

from aiohttp import ClientError
from lxml import html
from patchright.async_api import Error as PlaywrightError
from patchright.async_api import TimeoutError as PlaywrightTimeoutError

from . import _http, boj, config
from ._browser import browser_page
from .constants import BOJ_HOST, STATUS_AC, STATUS_WA
from .ui import BLUE, BWHITE, GREEN, RED, redraw
from .util import guess_pid, select_source_code

JUDGING_TIMEOUT = 60


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

    await async_playwright_submit(f'{BOJ_HOST}/submit/{pid}', filename, pid, config.lang_ids[lang[0]])


async def async_playwright_submit(url, filename, pid, language_id=None):
    with open(filename, 'r') as source:
        source_code = source.read().replace('\t', ' ' * config.conf['tab_width'])

    async with browser_page(headless=False, restore=True) as page:
        finished = False
        try:
            print('Complete any browser verification if prompted.')
            await page.goto(url, wait_until='domcontentloaded')
            button = page.locator('#submit_button')
            await button.wait_for(state='visible', timeout=300_000)
            await page.wait_for_load_state('load')
            destination = urlsplit(page.url)
            if (destination.scheme != 'https'
                    or destination.hostname not in ('acmicpc.net', 'www.acmicpc.net')
                    or destination.port not in (None, 443)
                    or destination.path != urlsplit(url).path):
                print('[!] The submission page opened on an unexpected site.')
                return

            if language_id is not None:
                language = page.locator('select[name="language"], select[name="language_id"], select#language')
                try:
                    # Chosen hides the native select that supplies the submitted value.
                    await language.select_option(value=str(language_id), force=True, timeout=10_000)
                except PlaywrightTimeoutError:
                    print(f'[!] Could not select BOJ language ID {language_id}. Check the language list on the page.')
                    await page.wait_for_event('close', timeout=0)
                    return
                await language.evaluate(
                    """element => {
                        if (element.classList.contains('chosen-select')) {
                            window.jQuery?.(element).trigger('chosen:updated');
                        }
                    }""",
                    isolated_context=False,
                )

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

    result = asyncio.create_task(wait_for_status(content, pid, page))
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


async def wait_for_status(resp, pid, page=None):
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
            return await _poll_judging_result(page, pid, sid)
    print('[!] Could not identify the submission on the BOJ page.')
    return False


async def _poll_judging_result(page, pid, sid):
    destination = urlsplit(page.url)
    if (destination.scheme != 'https'
            or destination.hostname not in ('acmicpc.net', 'www.acmicpc.net')
            or destination.port not in (None, 443)):
        print('[!] The judging page opened on an unexpected site.')
        return False
    origin = f'https://{destination.hostname}'
    loop = asyncio.get_running_loop()
    deadline = loop.time() + JUDGING_TIMEOUT
    previous = None
    while not page.is_closed():
        remaining = deadline - loop.time()
        if remaining <= 0:
            print(f'[!] No final judging result received within {JUDGING_TIMEOUT} seconds.')
            return False
        try:
            response = await page.request.post(
                f'{origin}/status/ajax', form={'solution_id': sid},
                headers={'X-Requested-With': 'XMLHttpRequest', 'Referer': f'{origin}/status'},
                max_redirects=0, timeout=min(5, remaining) * 1000,
            )
            try:
                data = await response.json() if response.ok else None
            finally:
                await response.dispose()
        except (PlaywrightError, ValueError):
            data = None
        if (isinstance(data, dict) and not data.get('error')
                and str(data.get('solution_id')) == sid and str(data.get('result')).isdecimal()):
            result = int(data['result'])
            progress = (result, data.get('progress'))
            if progress != previous:
                await display_submit_result({**data, 'solution_id': int(sid), 'result': result})
                previous = progress
            if result >= 4:
                boj.set_problem_status(pid, STATUS_AC if result == 4 else STATUS_WA)
                return True
        await asyncio.sleep(min(2, max(0, deadline - loop.time())))
    return False


async def display_submit_result(data):
    result = data['result']
    msg = "{:8d} : ".format(data['solution_id'])
    if result == 1:
        msg += "Prepare    "
    elif result == 2:
        msg += "Ready      "
    elif result == 3:
        if str(data.get('progress')).isdecimal():
            msg += "{:3d}%     ".format(int(data['progress']))
        else:
            msg += "  0%     "
    elif result == 4:
        msg += GREEN("Accepted")
        if all(str(data.get(field)).isdecimal() for field in ('memory', 'time')):
            msg += "\n{:6d}KB {:6d}ms".format(int(data['memory']), int(data['time']))
    elif result == 5:
        msg += RED("Wrong Output Format")
    elif result == 6:
        msg += RED("Wrong Answer")
    elif result == 7:
        msg += RED("Time Limit Exceed")
    elif result == 8:
        msg += BLUE("Memory Limit Exceed")
    elif result == 9:
        msg += BLUE("Output Limit Exceed")
    elif result == 10:
        msg += BLUE("Runtime Error")
    elif result == 11:
        msg += BLUE("Compile Error")
    else:
        msg += data.get('result_name') or f'Result {result}'
    if result >= 4:
        print()
    redraw(msg)
