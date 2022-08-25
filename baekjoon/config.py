import tomli
import sqlite3
from os import makedirs, path, environ

DEFAULT_CONFIG = {
    'cache_dir': '~/boj/cache',
    'code_dir': '~/boj/code',
    'database': '~/.boj/cache.db',
    'template': '~/.boj/template.cpp',
    'open_in_browser': True,
    'browser': 'google-chrome',
    'pager': 'less',
    'boj_token': '',
    'solved_token': '',
    'lang': [
        {'ext': "cpp", 'cmd': "g++ -O2", },
        {'ext': "py", 'cmd': "python3", },
    ],
    }

base_dir = environ["HOME"] + "/.boj"
config_path = base_dir + "/config.toml"
cookies_path = base_dir + "/cookies"
conf = {}

def load_config():
    global conf, db
    if path.isfile(config_path):
        conf = tomli.load(open(config_path, "rb"))
    else:
        conf = DEFAULT_CONFIG
    for d in [base_dir, conf['cache_dir'], conf['code_dir']]:
        if not path.isdir(path.expanduser(d)):
            makedirs(path.expanduser(d))

    db_path = path.expanduser(conf['database'])
    if not path.isfile(db_path):
        db = sqlite3.connect(db_path)
        cur = db.cursor()
        cur.execute('''CREATE TABLE boj (pid integer primary key, title varchar, info varchar, desc varchar, input varchar, output varchar, constraints varchar, hint varchar, lang varchar, spoiler varchar, samples varchar);''')
        cur.execute('''CREATE TABLE solved (pid integer primary key, title varchar, solved_count integer, avg_try float, level varchar, solved boolean);''')
        db.commit()
    else:
        db = sqlite3.connect(db_path)
