from . import _http
from . import config
from .ui import *
from .util import *
from time import time
from os import unlink, path
import asyncio
import subprocess

def find_input_files(_dir):
    ins = [_dir + sep + f for f in sorted(listdir(_dir)) if path.isfile(f) and path.splitext(f)[-1] == '.txt' and f.startswith('in')]
    return ins

def compile_code(args):
    proc = subprocess.run(args, capture_output=True)
    if proc.returncode != 0:
        if proc.stdout:
            print(proc.stdout.decode())
        if proc.stderr:
            print(proc.stderr.decode())
        print(RED("[!] Compile error!"))
        exit(1)

def test(args):
    pid = guess_pid(args)
    if not pid:
        print("[!] Invalid problem ID")
        return
    prob_dir = prepare_problem_dir(pid)

    if args.input:
        filename = args.input
    else:
        filename = select_source_code(pid)
    if not filename or not path.isfile(filename):
        print("[!] File not found".format(filename))
        return
    run_path, ext = path.splitext(filename)
    ext = ext.lstrip('.')
    input_files = find_input_files(prob_dir)

    cmd = [x for x in config.conf['lang'] if x['ext'] == ext]
    if not cmd:
        print("[!] Unsupported langugage, add your configuration")
        return
    cmd = cmd[0]

    if 'compile' in cmd and cmd['compile']:
        compile_args = []
        for s in cmd['compile']:
            s = s.replace("%PROB_NUM%", run_path).replace("%SOURCE%", filename)
            compile_args.append(s)
        print("[+] Compile {}".format(filename))
        compile_code(compile_args)

    exec_args = []
    for s in cmd['cmd']:
        s = s.replace("%PROB_NUM%", run_path).replace("%SOURCE%", filename)
        exec_args.append(s)

    ac = 0
    idx = 0
    for in_file in input_files:
        idx += 1
        d = path.dirname(in_file)
        f = path.basename(in_file)
        output_file = d + sep + 'ans' + f[2:]
        if not path.isfile(output_file):
            continue
        start_time = time()
        inputs = open(in_file, "rb").read()
        try:
            proc = subprocess.run(exec_args, input=inputs, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=5)
            outputs = proc.stdout
            expected_outputs = open(output_file, "rb").read()
            same = True
            end_time = time()
            report = ''
            a = outputs.decode().splitlines()
            b = expected_outputs.decode().splitlines()
            max_length = max(len(a), len(b))
            max_width = max(20, len(max(a+b, key=len))+1)
            a += [''] * (max_length - len(a))
            b += [''] * (max_length - len(b))
            for o1, o2 in zip(a, b):
                if o1.strip() == o2.strip():
                    report += o1.ljust(max_width, ' ') * 2 + '\n'
                    continue
                else:
                    same = False
                    padding = ' ' * (max_width - len(o1))
                    report += RED(o1) + padding
                    report += GREEN(o2) + '\n'
            if same:
                ac += 1
                print(GREEN("Passed #"+str(idx)), GRAY("... {:.3f}s".format(end_time-start_time)))
            else:
                print(RED("Failed #"+str(idx)), GRAY("... {:.3f}s".format(end_time-start_time)))
                print(WHITE("=======  IN #{:d} =======".format(idx)))
                print(inputs.decode())
                print(WHITE("======= OUT #{:d} =======".format(idx)))
                print(report)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
            print(RED("Failed #{}".format(idx)))
            if err.stdout: print(err.stdout.decode())
            print(GRAY(str(err)))
    total = len(input_files)
    ac_text = "[{}/{}]".format(ac, total)
    if total == 0:
        print(RED("[!] There is no testcases"))
    elif total == ac:
        print(ac_text, GREEN("Accepted"))
    else:
        print(ac_text, RED("Wrong Answer"))
    if 'compile' in cmd and cmd['compile']:
        unlink(run_path)
