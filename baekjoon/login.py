from . import config
from . import _http
from .ui import *
from .util import *
from urllib.parse import quote_plus
import asyncio
import json
from playwright.async_api import async_playwright

def start(args):
    return asyncio.run(async_login(args))

async def async_login(args):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
#       login_url = 'https://www.acmicpc.net/login'
        login_url = 'https://solved.ac/login?prev=%2F'
        redirect_url = 'https://solved.ac/**'
        selector = "#login_form > div:nth-child(4) > div:nth-child(2) > a"
        await page.goto(login_url)
        await page.wait_for_selector(selector, timeout=300000)
        await page.click(selector)
        await page.wait_for_url(redirect_url, timeout=30000)
        solved_cookies = await context.cookies()

        with open(config.cookie_path, 'w') as f:
            json.dump(solved_cookies, f)
        print(GREEN("LOGIN SUCCESS"))
        await browser.close()
