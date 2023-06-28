import tomli
import sqlite3
from os import makedirs, path, environ
from . import __version__

DEFAULT_CONFIG = {
    'cache_dir': '~/boj/cache',
    'code_dir': '~/boj/code',
    'database': '~/.boj/cache.db',
    'template': '~/.boj/template.cpp',
    'open_in_browser': True,
    'user_agent': 'bojtools/' + __version__,
    'browser': 'google-chrome',
    'pager': 'less',
    'code_open': 'open',
    'tab_width': 4,
    'auto_generate': True,
    'text_width': 70,
    'boj_token': '',
    'solved_token': '',
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
cookies_path = base_dir + "/cookies"
conf = {}

def load_config():
    global conf, db
    if path.isfile(config_path):
        conf = tomli.load(open(config_path, "rb"))
    for k, v in DEFAULT_CONFIG.items():
        if not k in conf:
            conf[k] = v
    for d in [base_dir, conf['cache_dir'], conf['code_dir']]:
        if not path.isdir(path.expanduser(d)):
            makedirs(path.expanduser(d))

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
