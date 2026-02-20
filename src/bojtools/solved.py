from . import boj
from . import _http
from . import config
from .constants import *
from lxml import etree, html
from urllib import parse
from random import randrange
import sqlite3
import asyncio
import json
import time

levels = ('b', 's', 'g', 'p', 'd', 'r')
level_nums = ('5', '4', '3', '2', '1')
level_classes = ( 'Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond', 'Ruby' )
level_roman = ( 'V', 'IV', 'III', 'II', 'I' )
level_table = {
    'b' : [1, 5], 's' : [6, 10], 'g' : [11, 15], 'p' : [16, 20], 'd' : [21, 25], 'r' : [26, 30],
    'b5' : [1], 'b4' : [2], 'b3' : [3], 'b2' : [4], 'b1' : [5],
    's5' : [6], 's4' : [7], 's3' : [8], 's2' : [9], 's1' : [10],
    'g5' : [11], 'g4' : [12], 'g3' : [13], 'g2' : [14], 'g1' : [15],
    'p5' : [16], 'p4' : [17], 'p3' : [18], 'p2' : [19], 'p1' : [20],
    'd5' : [21], 'd4' : [22], 'd3' : [23], 'd2' : [24], 'd1' : [25],
    'r5' : [26], 'r4' : [27], 'r3' : [28], 'r2' : [29], 'r1' : [30],
}

def extract_problem_from_html(tr):
    td = tr.xpath('.//td')
    prob = {}
    prob['level'] = td[0].xpath('.//img[@alt]')[0].get('alt')
    prob['pid'] = int(td[0].xpath('.//span[not(@class)]')[0].text)
    prob['title'] = ''.join(td[1].xpath(".//span[@class='__Latex__']")[0].itertext()).strip()
    prob['solved_count'] = int(td[2].xpath('.//div')[0].text.replace(',',''))
    prob['avg_try'] = float(td[3].xpath('.//div')[0].text)
    return prob

def extract_problem(item):
    prob = {}
    prob['level'] = lvnum_to_string(item['level'])
    prob['title'] = item['titleKo']
    prob['pid'] = int(item['problemId'])
    prob['solved_count'] = item['acceptedUserCount']
    prob['avg_try'] = item['averageTries']
    return prob

def lvnum_to_string(lv):
    if type(lv) == type(str()):
        lv = int(lv)
    level_name = level_classes[(lv-1)//5] + " " + level_roman[(lv-1)%5]
    return level_name


def pick_random(args):
    lv_start = str(args.level_start)
    lv_end = str(args.level_end)
    if not lv_start in level_table or not lv_end in level_table:
        print("[!] Failed to parse problem level")
        return
    lv_start = level_table[lv_start][0];
    lv_end = level_table[lv_end][-1];
    if lv_start > lv_end:
        t = lv_start
        lv_start = lv_end
        lv_end = t
    lv_range = "{}..{} ({:d}..{:d})".format(args.level_start, args.level_end, lv_start, lv_end)
#    lv_start = str(args.level_start)[:2]
#    if not lv_start[0] in levels or (len(lv_start) == 2 and not lv_start[1] in level_nums):
#        print("[!] Failed to parse problem level")
#        return
#    if 'level_end' in args and args.level_end:
#        lv_end = str(args.level_end)[:2]
#        if not lv_end[0] in levels or (len(lv_end) == 2 and not lv_end[1] in level_nums):
#            print("[!] Failed to parse problem level")
#            return
#    else:
#        lv_end = lv_start[0]

    print('[+] Random pick', lv_range)
    page = 1
    solved_count = ''
    if 'solved_count' in args and args.solved_count:
        solved_count = f'+(s#{args.solved_count}..)'
    #query = parse.quote_plus(query)
    not_solved = '+(-@$me)'
    url = f'{SOLVED_HOST}/api/v3/search/problem?query=' + \
          f'(*{lv_start:d}..{lv_end:d}){not_solved}{solved_count}' + \
          f'&page={page:d}&sort=random&direction=asc'
    asyncio.run(async_query_solvedac(url, args.list, rand=True))


def pick_class(args):
    level = args.level
    if level < 1 or level > 10:
        print("[!] Out of class range")
        return
    print('[+] Pick class', level)
    not_solved = '+(-@$me)'
    essential = ''
    if args.essential:
        essential = '_essentials'
    url = f'{SOLVED_HOST}/api/v3/search/problem?query=solvable:true{not_solved}+in_class{essential}:{level}&page=1'
    asyncio.run(async_query_solvedac(url, args.list, rand=True))


def save_solved_list(probs):
    cur = config.db.cursor()
    for prob in probs:
        cur.execute('INSERT or REPLACE INTO solved (pid, title, solved_count, avg_try, level) VALUES (?, ?, ?, ?, ?)', (prob['pid'], prob['title'], prob['solved_count'], prob['avg_try'], prob['level']))
    config.db.commit()


def get_cached_level(pid):
    cur = config.db.cursor()
    q = cur.execute(f'''SELECT pid, title, solved_count, avg_try, level FROM solved WHERE pid={pid}''').fetchone()
    if not q: return {}
    info = { 'pid':q[0], 'title':q[1], 'solved_count':q[2], 'avg_try':q[3], 'level':q[4] }
    return info


def get_problem_level(pid):
    return asyncio.run(async_get_problem_level(pid))


async def async_get_problem_level(pid):
    await _http.open_solved()
    try:
        url = f'{SOLVED_HOST}/api/v3/search/problem?query=({pid})&page=1'
        resp = await _http.async_get(url, _http.json_headers)
        page = json.loads(resp)
        items = page['items']
        probs = []
        for i in items:
            probs += [extract_problem(i)]
        save_solved_list(probs)
        return get_cached_level(pid)
    finally:
        await _http.close_solved()

async def async_query_solvedac(url, listing=False, rand=False):
    await _http.open_solved()
    try:
        resp = await _http.async_get(url, _http.json_headers)
        page = json.loads(resp)
        items = page['items']
        probs = []
        for i in items:
            probs += [extract_problem(i)]
#        tr = doc.xpath(".//table[@style='min-width:800px' and @class]//tr")
#        probs = []
#        for t in tr[1:]:
#            probs += [extract_problem_from_html(t)]
        if len(probs) == 0:
            print("[!] List is empty")
            return
        save_solved_list(probs)
        if listing:
            for prob in probs:
                print("[{:5d}] {}".format(prob['pid'], prob['title']))
        else:
            prob_idx = 0
            if rand:
                prob_idx = randrange(len(probs))
            await boj.async_pick(probs[prob_idx]['pid'])
    finally:
        await _http.close_solved()
