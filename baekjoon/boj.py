import json
import base64
import asyncio
import sqlite3
import textwrap
from . import ui
from . import solved
from . import config
from . import _http
from .util import *
from .constants import *
from lxml import etree, html
from os import makedirs, path, sep, system
import sys

def pick(args):
    if args.pid:
        pid = args.pid
    else:
        print("[!] problemID not found")
        return
    prob = asyncio.run(async_pick(pid))

def get_cached_problem(pid):
    cur = config.db.cursor()
    q = cur.execute(f'''SELECT title, info, desc, input, output, constraints, hint, lang, spoiler, samples FROM boj WHERE pid = {pid};''').fetchone()
    if not q: return []
    prob = {'pid':pid, 'title':q[0], 'info':json.loads(q[1]), 'desc':q[2], 'input':q[3], 'output':q[4], 'constraints':q[5], 'hint':q[6], 'lang':q[7], 'spoiler':q[8], 'samples':json.loads(q[9])}
    return prob

def save_problem_cache(prob):
    cur = config.db.cursor()
    cur.execute('INSERT or REPLACE INTO boj (pid, title, info, desc, input, output, constraints, hint, lang, spoiler, samples) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (prob['pid'], prob['title'], json.dumps(prob['info']), prob['desc'], prob['input'], prob['output'], prob['constraints'], prob['hint'], prob['lang'], prob['spoiler'], json.dumps(prob['samples'])))
    config.db.commit()

async def async_pick(pid):
    url = BOJ_HOST + '/problem/' + str(pid)
    print("[+] Pick", url)
    prob = get_cached_problem(pid)
    if prob:
        show_problem(prob)
        drop_testcases(prob)
        return
    await _http.open_boj()
    try:
        resp = await _http.async_get(url)
        doc = html.fromstring(resp)
        table = doc.xpath('.//table[@id="problem-info"]')[0]
        prob = {'pid':pid}
        prob['title'] = doc.xpath('.//h1/span[@id="problem_title"]')[0].text
        prob['info'] = {k.text.strip():v.text.strip() for k, v in zip(table.xpath('.//th'), table.xpath('.//td'))}
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
        prob['samples'] = list(testcases.values())
        save_problem_cache(prob)
        show_problem(prob)
        drop_testcases(prob)
    finally:
        await _http.close_boj()

def show_problem(prob):
    print(unicode_format("\n|{:>10s} |{:>15s} |{:>10s} |{:>10s} |{:>12s} |{:>12s} |", *prob['info'].keys()))
    print(unicode_format("|{:>10s} |{:>15s} |{:>10s} |{:>10s} |{:>12s} |{:>12s} |", *prob['info'].values()))
    ui.bwhite("\n[{}] {}\n".format(prob['pid'], prob['title']))
    if prob['lang']:
        multi_lang = json.loads(base64.b64decode(prob['lang']))
        for lang in multi_lang:
            print("=" * 30)
            ui.bwhite("[+] {} : {}".format(lang['problem_lang_tcode'], lang['title']))
            desc_text = html.fromstring(lang['description']).itertext()
            desc_text = textwrap.fill(''.join(desc_text), config.conf['text_width'])
            print(desc_text)
            ui.green("\nInput:")
            in_text = html.fromstring(lang['input']).itertext()
            in_text = textwrap.fill(''.join(in_text), config.conf['text_width'])
            print(''.join(in_text))
            ui.green("\nOutput:")
            out_text = html.fromstring(lang['output']).itertext()
            out_text = textwrap.fill(''.join(out_text), config.conf['text_width'])
            print(''.join(out_text))
    else:
        print(textwrap.fill(prob['desc'], config.conf['text_width']))
        ui.green("\nInput:")
        print(textwrap.fill(prob['input'], config.conf['text_width']))
        ui.green("\nOutput:")
        print(textwrap.fill(prob['output'], config.conf['text_width']))

    if prob['constraints']:
        ui.green("\nContraints:")
        print(prob['constraints'])
    ui.bwhite("\nSamples:")
    idx = 1
    for tc in prob['samples']:
        ui.green("INPUT{}:".format(idx))
        print(tc['in'])
        ui.green("OUTPUT{}:".format(idx))
        print(tc['out'])
        idx += 1

def problem_info(args):
    pid = guess_pid(args)
    if not pid:
        print("{!] problemID is empty")
        return
    print("[+] Show problem info")
    cur = config.db.cursor()
    prob = get_cached_problem(pid)
    if not prob:
        pick(args)
        prob = get_cached_problem(pid)

    sinfo = solved.get_cached_solved(pid)
    if sinfo and sinfo['level'] != 'Hidden':
        level_info = "(" + sinfo['level'] + ")"
    else:
        level_info = ""

    if prob['lang']:
        multi_lang = json.loads(base64.b64decode(prob['lang']))
        for lang in multi_lang:
            print("BOJ {:d} {} {}".format(prob['pid'], lang['title'], level_info))
    else:
        print("BOJ {:d} {} {}".format(prob['pid'], prob['title'], level_info))
    print(BOJ_HOST + '/problem/' + str(pid))

def drop_testcases(prob):
    prob_dir = path.expanduser(config.conf['code_dir']) + sep + str(prob['pid'])
    makedirs(prob_dir, exist_ok=True)
    idx = 1
    for tc in prob['samples']:
        in_path = "{}{}in{:d}.txt".format(prob_dir, sep, idx)
        open(in_path, 'w').write(tc['in'])
        out_path = "{}{}ans{:d}.txt".format(prob_dir, sep, idx)
        open(out_path, 'w').write(tc['out'])
        idx += 1

def view_solutions(args):
    asyncio.run(async_view_solutions(args))

async def async_view_solutions(args):
    pid = guess_pid(args)
    if not pid:
        print("{!] problemID is empty")
        return
    await _http.open_boj()
    print("[+] View solutions")
    print(BOJ_HOST + '/problem/' + str(pid))
    try:
        # TODO support language_id configuration
        lang_id = 1001 # C++
        lang_ext = '.cpp'
        url = "https://www.acmicpc.net/status?problem_id={}&user_id=&language_id={}&result_id=4".format(pid, lang_id)
        while True:
            resp = await _http.async_get(url)
            doc = html.fromstring(resp)
            tr = doc.xpath('.//table[@id="status-table"]/tbody/tr[@id]')
            for row in tr:
                td = row.xpath('.//td')
                code_url = td[6].xpath('a[@href]')
                if len(code_url) == 0: continue
                submit_id = td[0].text
                user_info = td[1].xpath('.//span[@class]')
                if user_info and user_info[0].get('class').startswith('user-'):
                    # TODO parse atcoder color (coderTextXXXX)
                    userrank = user_info[0].get('class').split('-')[1]
                    username = ''.join(user_info[0].itertext()).ljust(20)
                    username = ui.setcolor(userrank, username)
                else:
                    username = ''.join(td[1].itertext()).ljust(20)
                probinfo = td[2]
                result = td[3]
                prog_memory = td[4].text + td[4].xpath('.//span[@class]')[0].get('class').split('-')[0]
                prog_time = td[5].text + td[5].xpath('.//span[@class]')[0].get('class').split('-')[0]
                lang_type = code_url[0].text
                code_url = BOJ_HOST + code_url[0].get('href')
                code_size = td[7].text + td[7].xpath('.//span[@class]')[0].get('class').split('-')[0]
                submit_time = td[8].xpath('.//a[@title]')[0].get('title')
                print("{:9s} {} {:6s} {:6s} {:6s} {:5s} {}".format(
                    submit_id, username, prog_memory, prog_time, lang_type, code_size, submit_time), end='')
                choice = input(" View? [Y/n] ").lower()
                if choice in ['y', 'yes', '']:
                    cache_dir = path.expanduser(config.conf['cache_dir']) + sep + str(pid)
                    makedirs(cache_dir, exist_ok=True)
                    cache_file = cache_dir + sep + submit_id + lang_ext
                    if not path.isfile(cache_file):
                        sol = await _http.async_get(code_url)
                        sdoc = html.fromstring(sol)
                        src = sdoc.xpath('.//textarea[@name="source"]')[0].text
                        open(cache_file, 'w').write(src)
                    system('{} "{}"'.format(config.conf['pager'], cache_file))
            url = doc.xpath(".//a[@id='next_page']")
            if not url: break
            url = BOJ_HOST + url[0].get('href')
    finally:
        await _http.close_boj()
