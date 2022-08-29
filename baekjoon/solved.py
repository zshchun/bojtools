from . import boj
from . import _http
from . import config
from .constants import *
from lxml import etree, html
import sqlite3
import asyncio

levels = ('b', 's', 'g', 'p', 'd', 'r')
level_nums = ('5', '4', '3', '2', '1')

def extract_problem(tr):
    td = tr.xpath('.//td')
    prob = {}
    prob['level'] = td[0].xpath('.//img[@alt]')[0].get('alt')
    prob['pid'] = int(td[0].xpath('.//span[not(@class)]')[0].text)
    prob['title'] = ''.join(td[1].xpath(".//span[@class='__Latex__']")[0].itertext()).strip()
    prob['solved_count'] = int(td[2].xpath('.//div')[0].text.replace(',',''))
    prob['avg_try'] = float(td[3].xpath('.//div')[0].text)
    return prob

def pick_random(args):
    lv_start = str(args.level_start)[:2]
    if not lv_start[0] in levels or (len(lv_start) == 2 and not lv_start[1] in level_nums):
        print("[!] Failed to parse problem level")
        return
    if 'level_end' in args and args.level_end:
        lv_end = str(args.level_end)[:2]
        if not lv_end[0] in levels or (len(lv_end) == 2 and not lv_end[1] in level_nums):
            print("[!] Failed to parse problem level")
            return
    else:
        lv_end = lv_start[0]

    if len(lv_start) == 1: lv_start += '5'
    if len(lv_end) == 1: lv_end += '1'
    asyncio.run(async_pick_random(lv_start, lv_end))

def save_solved_list(tr):
    cur = config.db.cursor()
    for t in tr:
        prob = extract_problem(t)
        cur.execute('INSERT or REPLACE INTO solved (pid, title, solved_count, avg_try, level, solved) VALUES (?, ?, ?, ?, ?, ?)', (prob['pid'], prob['title'], prob['solved_count'], prob['avg_try'], prob['level'], False))
    config.db.commit()

def get_cached_level(pid):
    cur = config.db.cursor()
    q = cur.execute(f'''SELECT pid, title, solved_count, avg_try, level, solved FROM solved WHERE pid={pid}''').fetchone()
    if not q: return {}
    info = {'pid':q[0], 'title':q[1], 'solved_count':q[2], 'avg_try':q[3], 'level':q[4], 'solved':q[5]}
    return info

def get_problem_level(pid):
    asyncio.run(async_get_problem_level(pid))

async def async_get_problem_level(pid):
    await _http.open_solved()
    try:
        url = SOLVED_HOST + '/search?query=' + str(pid)
        resp = await _http.async_get(url)
        doc = html.fromstring(resp)
        tr = doc.xpath(".//table[@style='min-width:800px' and @class]//tr")
        save_solved_list(tr[1:])
        return get_cached_level(pid)
    finally:
        await _http.close_solved()

async def async_pick_random(lv_start, lv_end):
    await _http.open_solved()
    try:
        lv_range = "{}..{}".format(lv_start, lv_end)
        print('[+] Random pick', lv_range)
        page = 1
        url = '{}/search?query=*{}~@$me&sort=random&direction=asc&page={:d}'.format(SOLVED_HOST, lv_range, page)
        resp = await _http.async_get(url)
        doc = html.fromstring(resp)
        tr = doc.xpath(".//table[@style='min-width:800px' and @class]//tr")
        save_solved_list(tr[1:])
        prob = extract_problem(tr[1])
        await boj.async_pick(prob['pid'])
    finally:
        await _http.close_solved()
