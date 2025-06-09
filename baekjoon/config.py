import json
import tomli
import sqlite3
import platform
from os import makedirs, path, environ
from . import __version__

nix_path = [ '/usr/bin/chromium', '/usr/bin/chromium-browser',
             '/usr/bin/google-chrome-stable', '/usr/bin/google-chrome',
             '/snap/bin/chromium', ]
win_path = [ 'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe', ]
mac_path = [ '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
             '/Applications/Chromium.app/Contents/MacOS/Chromium',
             '/usr/bin/google-chrome',
             '/usr/bin/google-chrome-stable',
             '/usr/bin/chromium',
             '/usr/bin/chromium-browser', ]

def_browser_path = {
    'Windows': win_path,
    'Linux': nix_path,
    'OpenBSD': nix_path,
    'Darwin': mac_path,
}
def_browser_args = [ '--start-maximized', '--no-first-run', '--disable-notifications', ]
def_user_agent = 'Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'

DEFAULT_CONFIG = {
    'cache_dir': '~/boj/cache',
    'code_dir': '~/boj/code',
    'database': '~/.boj/cache.db',
    'template': '~/.boj/template.cpp',
    'open_in_browser': False,
    'headless_login': False,
    'pager': 'less',
    'code_open': 'open', # open, close, onlyaccepted
    'tab_width': 4,
    'auto_generate': True,
    'text_width': 70,
    'state_path': '~/.boj/state.json',
    'locale': 'ko-KR',
    'browser': '',
    'browser_args': [],
#    'browser_dir': '~/.boj/browser-cache',
    'browser_cookies': '~/.boj/cookies',
    'lang': [
        {'ext': "cpp", 'cmd': ["%PROB_NUM%"], 'compile': ["g++", "-Wall", "-W", "-std=c++17", "-O2", "-o", "%PROB_NUM%", "%SOURCE%"], 'lang_id': "C++17"},
        {'ext': "py", 'cmd': ["python3", "%SOURCE%"], 'compile': [], 'lang_id': "Python 3"},
    ],
    }

lang_ids = {
    "C++17": 84,
    "C99": 0,
    "Python 3": 28,
    "C++14": 88,
    "PyPy3": 73,
    "C++11": 49,
    "C++17 (Clang)": 85,
    "C++": 1001,
    "Java": 1002,
    "Python": 1003,
    "C": 1004,
    "Rust": 1005,
}

base_dir = environ["HOME"] + "/.boj"
config_path = base_dir + "/config.toml"
conf = {}


def find_browser_path():
    plat = platform.system()
    if not plat in def_browser_path:
        return None
    paths = def_browser_path[plat]
    for p in paths:
        if path.isfile(p):
            return p
    return None


def load_config():
    global conf, db, state, state_path
    if path.isfile(config_path):
        conf = tomli.load(open(config_path, "rb"))
    for k, v in DEFAULT_CONFIG.items():
        if not k in conf:
            conf[k] = v
    for d in [base_dir, conf['cache_dir'], conf['code_dir']]:
        if not path.isdir(path.expanduser(d)):
            makedirs(path.expanduser(d))
    state_path = path.expanduser(conf['state_path'])
    if path.isfile(state_path) and path.getsize(state_path) > 0:
        with open(state_path, 'r') as f:
            state = json.load(f)
            if 'user_agent' in state:
                conf['user_agent'] = state['user_agent']
    conf['browser_args'] += def_browser_args
    if not 'user_agent' in conf:
        conf['user_agent'] = def_user_agent

    if conf['browser_cookies']:
        conf['browser_cookies'] = path.expanduser(conf['browser_cookies'])

    if conf['browser']:
        conf['browser'] = path.expanduser(conf['browser'])
    else:
        conf['browser'] = find_browser_path()
        if not conf['browser']:
            raise Exception("Failed to detect browser environment. Define the browser within the configuration file.")

#    if conf['browser_dir']:
#        conf['browser_dir'] = path.expanduser(conf['browser_dir'])
#    if not path.isdir(conf['browser_dir']):
#        makedirs(conf['browser_dir'])

    db_path = path.expanduser(conf['database'])
    if not path.isfile(db_path):
        db = sqlite3.connect(db_path)
        cur = db.cursor()
        cur.execute('''CREATE TABLE boj (pid integer primary key, title varchar, info varchar, desc varchar, input varchar, output varchar, constraints varchar, hint varchar, lang varchar, spoiler varchar, samples varchar, accepted boolean);''')
        cur.execute('''CREATE TABLE solved (pid integer primary key, title varchar, solved_count integer, avg_try float, level varchar);''')
        db.commit()
    else:
        db = sqlite3.connect(db_path)

if not conf:
    load_config()
