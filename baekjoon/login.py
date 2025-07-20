from . import config
from .ui import *
from http import cookiejar
from getpass import getpass
import nodriver as uc
import asyncio
import json
import time

def start(args):
    uc.loop().run_until_complete(async_login(args))
    #return asyncio.run(async_login(args))

async def async_login(args):
    print("Sign in acmicpc.net and solve.ac")
    username = input("Username: ")
    password = getpass("Password: ")
    browser = await uc.start(headless=config.conf['headless_login'],
                             cookie=cookiejar.CookieJar(),
#                             user_data_dir=config.conf['browser_dir'],
                             browser_executable_path=config.conf['browser'],
                             browser_args=config.conf['browser_args'],
                             lang=config.conf['locale'],)
    #login_url = 'https://www.acmicpc.net/login'
    #redirect_url = 'https://solved.ac/**'
    login_url = 'https://solved.ac/login'
    tab = await browser.get(login_url)
    await tab
    time.sleep(1);
    checkbox = await tab.select('div.col-md-6:nth-child(1) > label:nth-child(1) > input:nth-child(1)')
    await checkbox.click()
    username_elem = await tab.select('div.input-group:nth-child(2) > input:nth-child(2)')
    await username_elem.send_keys(username)
    passwd_elem = await tab.select('div.input-group:nth-child(3) > input:nth-child(2)')
    await passwd_elem.send_keys(password)
    time.sleep(1);
    login_btn = await tab.select('#submit_button')
    await login_btn.click()

    for i in range(120):
        try:
            time.sleep(1)
            await tab
            selector = "#login_form > div:nth-child(4) > div:nth-child(2) > a"
            element = await tab.select(selector)
            break
        except TimeoutError:
            pass
    await element.click()


    selector = "#__next"
    time.sleep(1)
    for i in range(5):
        try:
            await tab.wait_for(selector, timeout=1)
            break
        except TimeoutError:
            pass
    state = {}
    #cookies = await browser.cookies.get_all(requests_cookie_format=False)
    cookies = await tab.send(uc.cdp.network.get_all_cookies())
    cookies = [c.to_json() for c in cookies]
    ua = await tab.evaluate('navigator.userAgent')
    state['cookies'] = cookies
    state['user_agent'] = ua
    await browser.cookies.save(config.conf['browser_cookies'])

    with open(config.state_path, 'w') as f:
        json.dump(state, f)
    print(GREEN("LOGIN SUCCESSFUL"))

    for t in browser.tabs:
        await t.close()

