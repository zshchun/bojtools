from . import boj
from . import login
from . import solved
from . import judge
from . import submit
from . import init
from . import  __version__
from sys import argv
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

def main():
    parser = ArgumentParser(prog=argv[0], description="Baekjoon Online Judge & solved.ac CLI tool")
    parser.add_argument('--version', help="version", action='version', version='%(prog)s ' + __version__)
    subparsers = parser.add_subparsers(title='commands', dest='command')
    commands = {}

    _login = subparsers.add_parser('login', aliases=['l'], help="Log in to baekjoon and solved.ac", allow_abbrev=True)
    _login.set_defaults(func=login.start)

    _init = subparsers.add_parser('init', aliases=['I'], help="Setup initial file", allow_abbrev=True)
    _init.set_defaults(func=init.setup)

    _pick = subparsers.add_parser('pick', aliases=['p'], help="Pick a problem", allow_abbrev=True)
    _pick.add_argument('pid', metavar='problemID', nargs='?', action='store', type=int)
    _pick.add_argument('-f', '--force', action='store_true', help="Update without cache data")
    _pick.set_defaults(func=boj.pick)

    _solution = subparsers.add_parser('solution', aliases=['q'], help="Get problem's solutions", allow_abbrev=True)
    _solution.add_argument('pid', metavar='problemID', nargs='?', action='store', type=int)
    _solution.set_defaults(func=boj.view_solutions)

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
    _generate.set_defaults(func=boj.generate_code)

    _info = subparsers.add_parser('info', aliases=['i'], help="Show problem info")
    _info.add_argument('pid', metavar='problemID', nargs='?', action='store', type=int)
    _info.add_argument('-l', '--level', action='store_true', help="Show problem level")
    _info.set_defaults(func=boj.problem_info)

    _class = subparsers.add_parser('class', aliases=['c'], help="Pick a problem of classes", allow_abbrev=True)
    _class.add_argument('level',  metavar="class level (default number=1)", action='store', type=int, help="Pick a problem from solved.ac class")
    _class.add_argument('-e', '--essential', action='store_true', help="Essential problems only")
    _class.add_argument('-a', '--all', action='store_true', help="All problems including solved")
    _class.add_argument('-l', '--list', action='store_true', help="List title of problems")
    _class.set_defaults(func=solved.pick_class)

    _random = subparsers.add_parser('random', aliases=['r'], help="Pick a random problem from solved.ac", allow_abbrev=True)
    _random.add_argument('level_start',  metavar="level_start (default number=5)", action='store', help="Start of problem level (b, s, g, p, d, r, g5, g4, ...)")
    _random.add_argument('level_end',  metavar="level_end (default number=1)", nargs='?', action='store', help="End of problem level (b, s, g, p, d, r, g3, g2, g1, ...)")
    _random.add_argument('-l', '--list', action='store_true', help="List title of problems")
    _random.add_argument('-s', '--solved_count', action='store', type=int, help="Number of people solved")
    _random.set_defaults(func=solved.pick_random)

    args = parser.parse_args()
    if 'func' in args:
        args.func(args)
    else:
        parser.print_help()
