import tomli
from os import makedirs, path, environ

DEFAULT_CONFIG = {
    'cache_dir': '~/boj/cache',
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
    global conf
    if path.isfile(config_path):
        conf = tomli.load(open(config_path, "rb"))
    else:
        conf = DEFAULT_CONFIG
    for d in [base_dir, conf['cache_dir']]:
        if not path.isdir(path.expanduser(d)):
            makedirs(path.expanduser(d))
