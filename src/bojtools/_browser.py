import json
from contextlib import asynccontextmanager

from patchright.async_api import async_playwright

from . import config
from .constants import CLOUDFLARE_COOKIE_NAMES


def _saved_storage_state():
    if not config.browser_state_path:
        return None
    try:
        with open(config.browser_state_path, encoding='utf-8') as saved:
            state = json.load(saved)
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError,
            UnicodeDecodeError, json.JSONDecodeError):
        return None
    if (isinstance(state, dict)
            and isinstance(state.get('cookies'), list)
            and isinstance(state.get('origins'), list)):
        return state
    return None


def _login_cookies():
    cookies = []
    for saved in getattr(config, 'state', {}).get('cookies', []):
        fields = ('name', 'value', 'domain', 'path')
        if not isinstance(saved, dict) or any(not isinstance(saved.get(field), str) for field in fields):
            continue
        if saved['domain'].lstrip('.').lower() not in ('acmicpc.net', 'www.acmicpc.net', 'solved.ac'):
            continue
        if saved['name'].lower() in CLOUDFLARE_COOKIE_NAMES:
            continue
        cookie = {field: saved[field] for field in fields}
        for flag in ('httpOnly', 'secure'):
            if isinstance(saved.get(flag), bool):
                cookie[flag] = saved[flag]
        if saved.get('sameSite') in ('Strict', 'Lax', 'None'):
            cookie['sameSite'] = saved['sameSite']
        if isinstance(saved.get('expires'), (int, float)) and saved['expires'] > 0:
            cookie['expires'] = saved['expires']
        cookies.append(cookie)
    return cookies


@asynccontextmanager
async def browser_page(*, headless, restore=False):
    storage_state = _saved_storage_state() if restore else None
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=headless,
            executable_path=config.conf['browser'] or None,
            args=config.conf['browser_args'],
        )
        try:
            context = await browser.new_context(
                locale=config.conf['locale'],
                storage_state=storage_state,
            )
            try:
                if restore and storage_state is None:
                    cookies = _login_cookies()
                    if cookies:
                        await context.add_cookies(cookies)
                yield await context.new_page()
            finally:
                await context.close()
        finally:
            await browser.close()
