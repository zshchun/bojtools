from . import config
from . import boj
from .ui import *
from .constants import *
from http.cookies import Morsel
from datetime import datetime, timezone
from os import path
import asyncio
import aiohttp
import json
import time

default_headers = {
    'Accept': '*/*',
    'Accept-Encoding': 'gzip',
    'Accept-Language': config.conf['locale'],
    'User-Agent': config.conf['user_agent'],
    }

tokens = {}
boj_session = None
solved_session = None
prev_req_time = None
req_delay = 0.300
cookie_jar = None

def add_header(newhdr, headers=default_headers):
    headers.update(newhdr)
    return headers

def get(url, headers=None):
    global prev_req_time
    resp = asyncio.run(async_get(url, headers))
    prev_req_time = time.time()
    if resp:
        return resp[0]
    else:
        return None

def post(url, data, headers=None):
    global prev_req_time
    resp = asyncio.run(async_post(url, data, headers))
    prev_req_time = time.time()
    if resp:
        return resp[0]
    else:
        return None

def GET(url, headers=None):
    return {'method':async_get, 'url':url, 'headers':headers}

def POST(url, data, headers=None):
    return {'method':async_post, 'url':url, 'data':data, 'headers':headers}

def wait_req_delay():
    if not prev_req_time:
        return
    if time.time() < prev_req_time + req_delay:
        time.sleep(prev_req_time + req_delay - time.time())

async def async_get(url, headers=None):
    if headers == None: headers = default_headers
    if url.startswith(BOJ_HOST):
        session = boj_session
    elif url.startswith(SOLVED_HOST):
        session = solved_session
    else:
        print("[!] URLs must contain {} or {}".format(BOJ_HOST, SOLVED_HOST))
        return None
    result = None
    wait_req_delay()
    async with session.get(url, headers=headers) as response:
        return await response.text()

async def async_post(url, data, headers=None):
    if headers == None: headers = default_headers
    if url.startswith(BOJ_HOST):
        session = boj_session
    elif url.startswith(SOLVED_HOST):
        session = solved_session
    else:
        print("[!] URLs must contain {} or {}".format(BOJ_HOST, SOLVED_HOST))
        return None
    session = boj_session
    result = None
    wait_req_delay()
    async with session.post(url, headers=headers, data=data) as response:
        return await response.text()

def urlsopen(urls):
    return asyncio.run(async_urlsopen(urls))

async def async_urlsopen(urls):
    tasks = []
    for u in urls:
        if u['method'] == async_get:
            tasks += [async_get(u['url'], u['headers'])]
        elif u['method'] == async_post:
            tasks += [async_post(u['url'], u['data'], u['headers'])]
    return await asyncio.gather(*tasks)


async def set_cookie():
    global cookie_jar
    cookie_jar = aiohttp.CookieJar()
    if not hasattr(config, 'state') or not 'cookies' in config.state:
        print(YELLOW("Please log in first. ") + WHITE("(boj login)"))
        return
    for c in config.state['cookies']:
        morsel = Morsel()
        morsel.set(c['name'], c['value'], c['value'])
        morsel['path'] = c['path']
        morsel['domain'] = c['domain']
        if 'expires' in c:
            t = datetime.fromtimestamp(c['expires'], tz=timezone.utc)
            morsel['expires'] = t.strftime("%a, %d %b %Y %H:%M:%S GMT")
        if 'secure' in c:
            morsel['secure'] = c['secure']
        if 'httpOnly' in c:
            morsel['httponly'] = c['httpOnly']
        if 'sameSite' in c and c['sameSite']:
            morsel['samesite'] = c['sameSite']
        cookie_jar.update_cookies({morsel.key : morsel})


async def open_boj():
    global boj_session, cookie_jar
    if cookie_jar == None:
        await set_cookie()
    if boj_session == None:
        boj_session = await aiohttp.ClientSession(cookie_jar=cookie_jar).__aenter__()

async def open_solved():
    global solved_session, cookie_jar
    if cookie_jar == None:
        await set_cookie()
    if solved_session == None:
        solved_session = await aiohttp.ClientSession(cookie_jar=cookie_jar).__aenter__()

async def close_boj():
    global boj_session
    await boj_session.__aexit__(None, None, None)
    boj_session = None

async def close_solved():
    global solved_session
    await solved_session.__aexit__(None, None, None)
    solved_session = None

async def websockets(url, callback, pid=None, sid=None):
    async with boj_session.ws_connect(url) as ws:
        result = 0
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                js = json.loads(msg.data)
                if js['event'] == 'pusher:connection_established' and sid:
                    req_js = {'event':'pusher:subscribe', \
                        'data':{'channel': 'solution-'+str(sid)}}
                    await ws.send_str(json.dumps(req_js))
                elif js['event'] == 'update':
                    data = json.loads(js['data'])
                    await callback(data)
                    if data['result'] == 4:
                        boj.set_problem_status(pid, STATUS_AC)
                        break
                    elif data['result'] > 3:
                        boj.set_problem_status(pid, STATUS_WA)
                        break
                elif js['event'] == 'pusher_internal:subscription_succeeded':
                    continue
            else:
                break;
