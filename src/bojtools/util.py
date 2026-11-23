import re
import subprocess
import unicodedata
from . import config
from lxml import etree, html
from os import path, getcwd, getpid, sep, makedirs, listdir, kill
from pylatexenc.latex2text import LatexNodes2Text
from pylatexenc.latexwalker import LatexWalker, LatexWalkerParseError
import signal


_MATH_SPAN = re.compile(
    r"\\\\|\\\((?:[^\\]|\\[^()[\]])*\\\)|\\\[(?:[^\\]|\\[^()[\]])*\\\]"
)


class _UnsupportedTex(ValueError):
    pass


class _ProblemMathText(LatexNodes2Text):
    def nodelist_to_text(self, nodelist):
        if len(nodelist) == 1 and getattr(nodelist[0], "macroname", None) == "frac":
            return self._fraction_to_text(nodelist[0])
        return super().nodelist_to_text(nodelist)

    def _fraction_to_text(self, node):
        if not node.nodeargd or len(node.nodeargd.argnlist) != 2:
            raise _UnsupportedTex
        numerator = self.node_arg_to_text(node, 0).strip()
        denominator = self.node_arg_to_text(node, 1).strip()
        if not numerator or not denominator:
            raise _UnsupportedTex
        numerator = numerator if numerator.isalnum() else f"({numerator})"
        denominator = denominator if denominator.isalnum() else f"({denominator})"
        return f"{numerator}/{denominator}"

    def macro_node_to_text(self, node):
        if node.macroname == "frac":
            return f"({self._fraction_to_text(node)})"
        if node.macroname == "sqrt" and (
            not node.nodeargd or not node.nodeargd.argnlist or node.nodeargd.argnlist[0] is not None
        ):
            raise _UnsupportedTex
        if self.latex_context.get_macro_spec(node.macroname) is None:
            raise _UnsupportedTex
        return super().macro_node_to_text(node)

    def environment_node_to_text(self, node):
        if self.latex_context.get_environment_spec(node.environmentname) is None:
            raise _UnsupportedTex
        return super().environment_node_to_text(node)


_MATH_TEXT = _ProblemMathText(math_mode="text", keep_braced_groups=True)


def render_problem_math(text):
    def render_span(match):
        source = match.group()
        if source == r"\\":
            return source
        try:
            nodes, _, _ = LatexWalker(source, tolerant_parsing=False).get_latex_nodes()
            return _MATH_TEXT.nodelist_to_text(nodes) or source
        except (LatexWalkerParseError, _UnsupportedTex, RecursionError):
            return source

    return _MATH_SPAN.sub(render_span, text)


def sig_handler(signum, frame):
    job = []
    print(f"Terminated by signal : {signum}")
    signal.signal(signum, signal.SIG_DFL)
    kill(getpid(), signum)


def register_signal():
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)


def get_tag_text(tags):
    ret = ''
    for t in tags:
        ret += t.text_content().replace('\n\t', '\n ')
    return ret.strip()

def wrap_html_text(s):
    if not s:
        return ""
    text = html.fromstring(s).text_content().replace('\n\t', '\n ')
    text = text_wrap(render_problem_math(text), config.conf['text_width'])
    return text

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
    files = []
    for name in listdir(_dir):
        candidate = path.join(_dir, name)
        if path.isfile(candidate) and path.splitext(name)[-1].lstrip('.') in exts:
            files.append(candidate)
    return files

def prepare_problem_dir(pid):
    p = path.expanduser(config.conf['code_dir'] + sep + str(pid))
    makedirs(p, exist_ok=True)
    return p

def select_source_code(pid):
    prob_path = prepare_problem_dir(pid)
    files = find_source_files(prob_path)
    if len(files) == 0:
        return None
    elif len(files) >= 2:
        print("[!] There are multiple solutions")
        return None
    return files[0]

def text_wrap(string, width):
    ret = []
    wcnt = 0
    s = ''
    for c in string:
        if unicodedata.east_asian_width(c) in ['F', 'W']:
            wcnt += 2
        else:
            wcnt += 1
        if c != '\n':
            s += c
        if wcnt >= width or c == '\n':
            wcnt = 0
            ret.append(s)
            s = ''
    if s: ret.append(s)
    return '\n'.join(ret)

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
