import asyncio
import json
from getpass import getpass
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import parse_qs, urlsplit

from patchright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout

from . import _http
from . import config
from ._browser import browser_page
from .ui import GREEN


def start(args):
    asyncio.run(async_login(args))


def _write_state(filename, state):
    destination = Path(filename)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = NamedTemporaryFile(
        mode='w', encoding='utf-8', dir=destination.parent, delete=False
    )
    temporary_path = Path(temporary.name)
    try:
        with temporary:
            json.dump(state, temporary)
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)


async def _save_state(page, solved_handle):
    browser_state = await page.context.storage_state()
    # Older HTTP clients interpret expires=-1 as an already expired cookie.
    cookies = [dict(cookie) for cookie in browser_state['cookies']]
    for cookie in cookies:
        if cookie.get('expires', 0) < 0:
            del cookie['expires']
    state = {
        'cookies': cookies,
        'user_agent': await page.evaluate('navigator.userAgent'),
        'solved_handle': solved_handle,
    }
    if config.browser_state_path:
        _write_state(config.browser_state_path, browser_state)
    _write_state(config.state_path, state)
    config.state = state


async def async_login(args):
    print("Sign in acmicpc.net and solved.ac")
    username = input("Username: ")
    password = getpass("Password: ")
    async with browser_page(headless=config.conf['headless_login'], restore=False) as page:
        print('Complete any browser verification to finish signing in.')
        await page.goto('https://solved.ac/ko/login', wait_until='domcontentloaded')
        try:
            boj_button = page.get_by_role('button', name='BOJ로 로그인', exact=True)
            deadline = asyncio.get_running_loop().time() + 30
            # The server-rendered button is visible before React attaches its handler.
            while not await boj_button.evaluate(
                "button => typeof button.onclick === 'function'", isolated_context=False,
            ):
                if asyncio.get_running_loop().time() >= deadline:
                    raise PlaywrightTimeout('The BOJ login button is not ready')
                await asyncio.sleep(0.1)
            await boj_button.click(timeout=30_000)
        except PlaywrightTimeout as error:
            raise RuntimeError('Could not activate the BOJ login button on solved.ac') from error

        username_field = page.locator('form#login_form input[name="login_user_id"]')
        await username_field.wait_for(timeout=60_000)
        url = urlsplit(page.url)
        if url.scheme != 'https' or url.hostname not in ('acmicpc.net', 'www.acmicpc.net'):
            raise RuntimeError('BOJ login did not open on acmicpc.net')
        await page.locator('form#login_form input[name="auto_login"]').check()
        await username_field.fill(username)
        try:
            await page.locator('form#login_form input[name="login_password"]').fill(password)
        except PlaywrightError:
            raise RuntimeError('Could not fill the BOJ password field') from None
        await page.locator('form#login_form button[type="submit"]').click()

        deadline = asyncio.get_running_loop().time() + 300
        sso_submitted = False
        while True:
            if page.is_closed():
                raise RuntimeError('The browser was closed before solved.ac sign-in completed')
            cookies = await page.context.cookies()
            if any(c['name'] == 'solvedacToken' and c['domain'].lstrip('.') == 'solved.ac' for c in cookies):
                break
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError('Solved.ac login did not complete within 300 seconds')
            url = urlsplit(page.url)
            if (not sso_submitted and url.scheme == 'https'
                    and url.hostname in ('acmicpc.net', 'www.acmicpc.net') and url.path == '/sso'):
                redirect = parse_qs(url.query).get('redirect', [''])[0]
                if redirect not in ('https://solved.ac/auth/boj/callback', 'https:/solved.ac/auth/boj/callback'):
                    raise RuntimeError('BOJ SSO did not target the solved.ac callback')
                for role in ('link', 'button'):
                    approval = page.get_by_role(role, name='로그인', exact=True)
                    if await approval.is_visible():
                        await approval.click(timeout=30_000)
                        sso_submitted = True
                        break
            await asyncio.sleep(1)

        await _save_state(page, config.conf['solved_handle'] or username)
        print(GREEN("LOGIN SUCCESSFUL"))


async def refresh_cookie(url):
    print("[+] refresh cookies")
    async with browser_page(headless=True, restore=True) as page:
        response = await page.goto(url, wait_until='domcontentloaded')
        if response is not None:
            _http._require_no_browser_challenge(response.headers)
        solved_handle = getattr(config, 'state', {}).get('solved_handle', '')
        await _save_state(page, solved_handle)

    await _http.close_session()
    _http.cookie_jar = None
    await _http.open_session(force=True)
