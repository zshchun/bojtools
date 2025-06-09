from . import boj
from . import config
from .ui import *
import os
import tomli_w

def setup(args):
    with open(config.config_path, 'wb') as f:
        tomli_w.dump(config.DEFAULT_CONFIG, f)
    print(WHITE("Initial file generated: " + config.config_path))
