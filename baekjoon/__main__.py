from . import boj
from . import solved
from . import judge
from . import __version__
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

def main():
    parser = ArgumentParser(prog='BOJ CLI', description="BOJ CLI tool")
    parser.add_argument('--version', help="version", action='version', version='%(prog)s ' + __version__)
    subparsers = parser.add_subparsers(title='commands', dest='command')
    commands = {}

    _pick = subparsers.add_parser('pick', aliases=['p'], help="Pick a problem", allow_abbrev=True)
    _pick.add_argument('pid', metavar='problemID', nargs='?', action='store', type=int)
    _pick.set_defaults(func=boj.pick)

    _random = subparsers.add_parser('random', aliases=['r'], help="Pick a random problem from solved.ac", allow_abbrev=True)
    _random.add_argument('-b', '--bronze',  action='store_true', help="Pick a random problem from bronze level")
    _random.add_argument('-s', '--silver',  action='store_true', help="Pick a random problem from silver level")
    _random.add_argument('-g', '--gold',  action='store_true', help="Pick a random problem from gold level")
    _random.add_argument('-p', '--platinum',  action='store_true', help="Pick a random problem from platinum level")
    _random.add_argument('-d', '--diamond',  action='store_true', help="Pick a random problem from diamond level")
    _random.add_argument('-r', '--ruby',  action='store_true', help="Pick a random problem from ruby level")
    _random.set_defaults(func=solved.pick_random)

    args = parser.parse_args()
    if 'func' in args:
        args.func(args)
    else:
        parser.print_help()
