from . import boj
from . import _http
from . import config
from .constants import *
from lxml import etree, html
import sqlite3
import asyncio

levels = ('b', 's', 'g', 'p', 'd', 'r')

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
    if   args.bronze:   level = 'b'
    elif args.silver:   level = 's'
    elif args.gold:     level = 'g'
    elif args.platinum: level = 'p'
    elif args.diamond:  level = 'd'
    elif args.ruby:     level = 'r'
    else: return
    asyncio.run(async_pick_random(level))

def save_solved_list(tr):
    cur = config.db.cursor()
    for t in tr:
        prob = extract_problem(t)
        cur.execute('INSERT or REPLACE INTO solved (pid, title, solved_count, avg_try, level, solved) VALUES (?, ?, ?, ?, ?, ?)', (prob['pid'], prob['title'], prob['solved_count'], prob['avg_try'], prob['level'], False))
    config.db.commit()

async def async_pick_random(level):
    if not level in levels: return
    await _http.open_solved()
    try:
        lv_num_start = 5
        lv_num_end = 1
        lv_range = "{}{:d}..{}{:d}".format(level, lv_num_start, level, lv_num_end)
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
