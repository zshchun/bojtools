from . import config
from .ui import *
from http import cookiejar
import nodriver as uc
import asyncio
import json

def start(args):
    uc.loop().run_until_complete(async_login(args))
    #return asyncio.run(async_login(args))

async def async_login(args):
    browser = await uc.start(headless=False,
                             cookie=cookiejar.CookieJar(),
                             user_data_dir=config.conf['browser_dir'],
                             browser_executable_path=config.conf['browser'],
                             browser_args=config.conf['browser_args'],
                             lang=config.conf['locale'],)
    #login_url = 'https://www.acmicpc.net/login'
    login_url = 'https://solved.ac/login'
    redirect_url = 'https://solved.ac/**'
    tab = browser.main_tab
    ua = await tab.evaluate('navigator.userAgent')
    tab = await browser.get(login_url)

    selector = "#login_form > div:nth-child(4) > div:nth-child(2) > a"
    element = await tab.select(selector)
    #element = await tab.wait_for(selector, timeout=10)
    await element.click()

    state = {}
    #cookies = await browser.cookies.get_all(requests_cookie_format=False)
    cookies = await tab.send(uc.cdp.network.get_all_cookies())
    cookies = [c.to_json() for c in cookies]
    state['cookies'] = cookies
    state['user_agent'] = ua

    with open(config.state_path, 'w') as f:
        json.dump(state, f)
    print(GREEN("LOGIN SUCCESSFUL"))

    for t in browser.tabs:
        await t.close()

