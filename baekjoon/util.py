import subprocess
import unicodedata
from . import config
from os import path, getcwd, sep, makedirs, listdir

def extract_text(tags):
    ret = ''
    for t in tags:
        ret += "".join([x.replace('\t', '') for x in t.itertext()])
    return ret.strip()

def guess_pid(args):
    if 'pid' in args and args.pid:
        pid = int(args.pid)
    else:
        pid = get_cwd_info()
    return pid

def get_cwd_info():
    p = path.normpath(getcwd()).split(sep)
    if len(p) >= 1 and p[-1].isnumeric():
        return int(p[-1])
    else:
        return None

def find_source_files(_dir):
    exts = [k['ext'] for k in config.conf['lang']]
    if not exts: return
    files = [_dir + sep + f for f in listdir(_dir) if path.isfile(f) and path.splitext(f)[-1].lstrip('.') in exts]
    return files

def prepare_problem_dir(pid):
    p = path.expanduser(config.conf['code_dir'] + sep + str(pid))
    makedirs(p, exist_ok=True)
    return p

def select_source_code(pid):
    prob_path = prepare_problem_dir(pid)
    files = find_source_files(prob_path)
    if len(files) == 0:
        print("[!] File not found")
        return None
    elif len(files) >= 2:
        print("[!] There are multiple solutions")
        return None
    return files[0]

def unicode_format(fmt, *args):
    new_fmt = ''
    new_args = []
    idx = 0
    for f in fmt.split('{:'):
        e = f.split('}')
        assert len(e) < 3, "Single '}' encountered"
        if len(e) == 1:
            new_fmt += e[0]
            continue
        if e[0][-1] != 's':
            new_fmt += '{:' + f
            new_args.append(args[idx])
            idx += 1
            continue
        new_fmt += '{:s}' + e[1]
        r = e[0]
        if r[0] == '>':
            direction = 1
        else:
            direction = 0
        if r[0] in ['<', '>']:
            width = int(r[1:-1])
        else:
            width = int(r[0:-1])
        wcnt = 0
        for c in args[idx]:
            if unicodedata.east_asian_width(c) in ['F', 'W']:
                wcnt += 2
            else:
                wcnt += 1
        if wcnt > width:
            wcnt = width
        if direction == 0:
            new_args.append(args[idx] + ' '*(width-wcnt))
        else:
            new_args.append(' '*(width-wcnt) + args[idx])
        idx += 1
    return new_fmt.format(*new_args)
