from . import config
from . import _http
from .ui import *
from http import cookiejar
from getpass import getpass
from os import path
from urllib.parse import urlsplit
import nodriver as uc
import asyncio
import json
import time

def start(args):
    uc.loop().run_until_complete(async_login(args))
    #return asyncio.run(async_login(args))

async def async_login(args):
    print("Sign in acmicpc.net and solved.ac")
    username = input("Username: ")
    password = getpass("Password: ")
    browser = await uc.start(headless=config.conf['headless_login'],
                             cookie=None,
#                             user_data_dir=config.conf['browser_dir'],
                             browser_executable_path=config.conf['browser'],
                             browser_args=config.conf['browser_args'],
                             lang=config.conf['locale'],)
    try:
        tab = await browser.get('https://solved.ac/ko/login')
        await tab
        boj_button = await tab.find('BOJ로 로그인', timeout=30)
        if not boj_button:
            raise RuntimeError('Could not find the BOJ login button on solved.ac')
        await boj_button.click()

        username_elem = await tab.wait_for('form#login_form input[name="login_user_id"]', timeout=60)
        if urlsplit(tab.url).hostname not in ('acmicpc.net', 'www.acmicpc.net'):
            raise RuntimeError('BOJ login did not open on acmicpc.net')
        checkbox = await tab.select('form#login_form input[name="auto_login"]')
        await checkbox.click()
        await username_elem.send_keys(username)
        passwd_elem = await tab.select('form#login_form input[name="login_password"]')
        await passwd_elem.send_keys(password)
        login_btn = await tab.select('form#login_form button[type="submit"]')
        await login_btn.click()

        print('Complete any browser verification to finish signing in.')
        deadline = asyncio.get_running_loop().time() + 300
        while True:
            cookies = await browser.cookies.get_all()
            if any(c.name == 'solvedacToken' and c.domain.lstrip('.') == 'solved.ac' for c in cookies):
                break
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError('Solved.ac login did not complete within 300 seconds')
            await asyncio.sleep(1)

        state = {
            'cookies': [c.to_json() for c in cookies],
            'user_agent': await tab.evaluate('navigator.userAgent'),
            'solved_handle': config.conf['solved_handle'] or username,
        }
        await browser.cookies.save(config.conf['browser_cookies'])
        with open(config.state_path, 'w') as f:
            json.dump(state, f)
        config.state = state
        print(GREEN("LOGIN SUCCESSFUL"))
    finally:
        for t in browser.tabs:
            await t.close()


async def refresh_cookie(url):
    print("[+] refresh cookies");
    browser = await uc.start(
        headless=True,
        cookie=None,
        browser_executable_path=config.conf['browser'],
        browser_args=config.conf['browser_args'],
        lang=config.conf['locale'],
    )
    if config.conf.get('browser_cookies') and path.isfile(config.conf['browser_cookies']):
        try:
            await browser.cookies.load(config.conf['browser_cookies'])
        except AttributeError as exc:
            if not str(exc).endswith("has no attribute 'same_party'"):
                raise
            print('[+] Resetting outdated browser cookies. Run `boj login` if you need to sign in again.')
            await browser.cookies.clear()
    tab = await browser.get(url)
    await tab
    state = {'solved_handle': getattr(config, 'state', {}).get('solved_handle', '')}
    cookies = await tab.send(uc.cdp.network.get_all_cookies())
    cookies = [c.to_json() for c in cookies]
    ua = await tab.evaluate('navigator.userAgent')
    state['cookies'] = cookies
    state['user_agent'] = ua
    await browser.cookies.save(config.conf['browser_cookies'])
    with open(config.state_path, 'w') as f:
        json.dump(state, f)
    config.state = state

    await _http.close_session()
    _http.cookie_jar = None
    await _http.open_session(force=True)

    for t in browser.tabs:
        await t.close()
