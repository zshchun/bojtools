from . import boj
from . import _http
from .constants import *
from lxml import etree, html
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

async def async_pick_random(level):
    if not level in levels: return
    await _http.open_solved()
    try:
        page = 1
        url = '{}/search?query=*{}5..{}1~@$me&sort=random&direction=asc&page={:d}'.format(SOLVED_HOST, level, level, page)
        resp = await _http.async_get(url)
        doc = html.fromstring(resp)
        tr = doc.xpath(".//table[@style='min-width:800px' and @class]//tr")
        prob = extract_problem(tr[1])
        print('[+] Pick a random problem')
        await boj.async_pick(prob['pid'])
    finally:
        await _http.close_solved()
