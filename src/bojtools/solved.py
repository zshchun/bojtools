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
    titles = item['titles']
    prob['title'] = next((title['title'] for title in titles if title['language'] in ('ko', 'ko-KR')),
                         titles[0]['title'] if titles else str(item['problemId']))
    prob['pid'] = int(item['problemId'])
    prob['solved_count'] = item['solvedUserCount']
    prob['avg_try'] = None
    return prob


def extract_problem_detail(page, pid):
    if not page.strip():
        raise RuntimeError('solved.ac returned an empty problem page')
    doc = html.fromstring(page)
    titles = doc.xpath('//main//*[@data-problem-title]')
    levels = doc.xpath('//main//*[@data-problem-title]/ancestor::a[1]/../span/img/@alt')
    solved_counts = doc.xpath('//main//p[normalize-space()="푼 사람"]/following-sibling::p[1]/text()')
    expected_path = f'/problem/{pid}'
    boj_links = {f'https://{host}{expected_path}' for host in ('acmicpc.net', 'www.acmicpc.net')}
    if not titles or not levels or not boj_links.intersection(doc.xpath('//main//a/@href')):
        raise RuntimeError(f'solved.ac did not return a recognizable problem page for {pid}')
    solved_count = solved_counts[0].replace(',', '').strip() if solved_counts else ''
    return {
        'pid': pid,
        'title': titles[0].text_content().strip(),
        'level': levels[0].strip(),
        'solved_count': int(solved_count) if solved_count.isdecimal() else None,
        'avg_try': None,
    }


def solved_headers():
    if not any(cookie.get('name') == 'solvedacToken'
               for cookie in getattr(config, 'state', {}).get('cookies', [])):
        raise ValueError('Log in to solved.ac with boj login first')
    return _http.json_headers


def unsolved_filter():
    handle = config.conf['solved_handle']
    if not handle and hasattr(config, 'state'):
        handle = config.state.get('solved_handle', '')
    if not handle:
        raise ValueError('Set solved_handle in ~/.boj/config.toml (or run boj login again)')
    return f'-@{handle}'


async def async_get_solved(url, params):
    resp = await _http.async_get(url, params, solved_headers())
    try:
        page = json.loads(resp)
    except json.JSONDecodeError as error:
        raise RuntimeError('solved.ac returned a non-JSON response; refresh the browser login cookies') from error
    if 'error' in page:
        raise RuntimeError(f"solved.ac API: {page['error']['code']}: {page['error']['message']}")
    if page.get('diagnostics'):
        messages = ', '.join(diagnostic['message'] for diagnostic in page['diagnostics'])
        raise RuntimeError(f'solved.ac search query: {messages}')
    return page

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
    solved_count = ''
    if 'solved_count' in args and args.solved_count:
        solved_count = f' (s#{args.solved_count}..)'
    #query = parse.quote_plus(query)
    url = SOLVED_V4_PROBS
    query = f'(*{lv_start:d}..{lv_end:d}) ({unsolved_filter()}){solved_count}'
    params = {'q': query, 'page': 1, 'sort': 'random'}
    asyncio.run(async_query_solvedac(url, params, args.list, rand=True))

def pick_class(args):
    level = args.level
    if level < 1 or level > 10:
        print("[!] Out of class range")
        return
    print('[+] Pick class', level)
    essential = ''
    if args.essential:
        essential = '_essentials'
    url = SOLVED_V4_PROBS
    solved_filter = '' if args.all else f' ({unsolved_filter()})'
    query = f'solvable:true{solved_filter} in_class{essential}:{level}'
    params = {'q': query, 'page': 1, 'sort': 'random'}
    asyncio.run(async_query_solvedac(url, params, args.list, rand=True))


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
    await _http.open_session()
    try:
        page = await _http.async_get(f'{SOLVED_HOST}/ko/p/{pid}')
        save_solved_list([extract_problem_detail(page, pid)])
        return get_cached_level(pid)
    finally:
        await _http.close_session()

async def async_query_solvedac(url, params, listing=False, rand=False):
    await _http.open_session()
    try:
        page = await async_get_solved(url, params)
        items = page['problems']
        count = page['total']
        probs = []
        if count > 1:
            print(f'[+] Problems : {count}')
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
        await _http.close_session()
