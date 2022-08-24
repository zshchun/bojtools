import json
import base64
import asyncio
from . import solved
from . import config
from . import _http
from .util import *
from .constants import *
from lxml import etree, html
from pprint import PrettyPrinter as pp
import sys

def pick(args):
    if args.pid:
        pid = args.pid
    else:
        print("[!] problemID not found")
        return
    asyncio.run(async_pick(pid))

async def async_pick(pid):
    await _http.open_boj()
    try:
        url = BOJ_HOST + '/problem/' + str(pid)
        print("[+] Pick a problem", pid)
        print(url)
        resp = await _http.async_get(url)
        doc = html.fromstring(resp)
        title = doc.xpath('.//h1/span[@id="problem_title"]')[0].text
        table = doc.xpath('.//table[@id="problem-info"]')[0]
        prob = {'pid':pid}
        prob['info'] = {k.text:v.text for k, v in zip(table.xpath('.//th'), table.xpath('.//td'))}
        prob['desc'] = extract_text(doc.xpath('.//div[@id="problem_description"]'))
        prob['input'] = extract_text(doc.xpath('.//div[@id="problem_input"]'))
        prob['output'] = extract_text(doc.xpath('.//div[@id="problem_output"]'))
        prob['constraints'] = extract_text(doc.xpath('.//div[@id="problem_limit"]'))
        prob['hint'] = extract_text(doc.xpath('.//div[@id="problem_hint"]'))
        lang = doc.xpath('.//div[@id="problem-lang-base64"]')
        prob['lang'] = lang[0].text if lang else None
        prob['spoiler'] = "\n".join([x.text for x in doc.xpath(".//a[@class='spoiler-link']")])
        testcases = {}
        for s in doc.xpath('.//pre[@class="sampledata"]'):
            io = s.get('id').split('-')
            num = io[2]
            if not num in testcases:
                testcases[num] = {}
            if io[1] == 'input':
                testcases[num]['in'] = s.text
            elif io[1] == 'output':
                testcases[num]['out'] = s.text
        prob['samples'] = testcases.values()
#    show_problem(prob)
        pp().pprint(prob)
    finally:
        await _http.close_boj()

def show_problem(prob):
    print(prob['desc'])
