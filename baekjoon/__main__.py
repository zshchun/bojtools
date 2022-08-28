from . import boj
from . import solved
from . import judge
from . import submit
from . import __version__
from sys import argv
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

def main():
    parser = ArgumentParser(prog=argv[0], description="BOJ CLI tool")
    parser.add_argument('--version', help="version", action='version', version='%(prog)s ' + __version__)
    subparsers = parser.add_subparsers(title='commands', dest='command')
    commands = {}

    _pick = subparsers.add_parser('pick', aliases=['p'], help="Pick a problem", allow_abbrev=True)
    _pick.add_argument('pid', metavar='problemID', nargs='?', action='store', type=int)
    _pick.set_defaults(func=boj.pick)

    _test = subparsers.add_parser('test', aliases=['t'], help="Test with testcases", allow_abbrev=True)
    _test.add_argument('pid', metavar='problemID', nargs='?', action='store', type=int)
    _test.add_argument('-i', '--input', action='store', type=str, help="Input file")
    _test.set_defaults(func=judge.test)

    _submit = subparsers.add_parser('submit', aliases=['s'], help="Submit code", allow_abbrev=True)
    _submit.add_argument('pid', metavar='problemID', nargs='?', action='store', type=int)
    _submit.add_argument('-i', '--input', action='store', type=str, help="Input file")
    _submit.set_defaults(func=submit.submit)

    _generate = subparsers.add_parser('generate', aliases=['g'], help="Generate source code from template")
    _generate.add_argument('pid', metavar='problemID', nargs='?', action='store', type=int)
    _generate.set_defaults(func=judge.generate_code)

    _info = subparsers.add_parser('info', aliases=['i'], help="Show problem info")
    _info.add_argument('pid', metavar='problemID', nargs='?', action='store', type=int)
    _info.set_defaults(func=boj.problem_info)

    _random = subparsers.add_parser('random', aliases=['r'], help="Pick a random problem from solved.ac", allow_abbrev=True)
    _random.add_argument('level_start',  metavar="level_start (default number=5)", action='store', help="Start of problem level (b, s, g, p, d, r, g5, g4, ...)")
    _random.add_argument('level_end',  metavar="level_end (default number=1)", nargs='?', action='store', help="End of problem level (b, s, g, p, d, r, g3, g2, g1, ...)")
    _random.set_defaults(func=solved.pick_random)

    args = parser.parse_args()
    if 'func' in args:
        args.func(args)
    else:
        parser.print_help()
