from . import ui
from . import _http
from . import config
from .util import *
from os import unlink
import asyncio

def find_input_files(_dir):
    ins = [_dir + sep + f for f in listdir(_dir) if path.isfile(f) and path.splitext(f)[-1] == '.txt' and f.startswith('in')]
    return ins

def compile_code(src_path, run_path):
    print("[+] Compile {}".format(src_path))
    proc = subprocess.run(["g++", "-O2", "-o", run_path, src_path], capture_output=True)
    if proc.returncode != 0:
        if proc.stdout:
            print(proc.stdout.decode())
        if proc.stderr:
            print(proc.stderr.decode())
        ui.red("[!] Compile error!")
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
    if not path.isfile(filename):
        print("[!] File not found : {}".format(filename))
        return
    run_path = path.splitext(filename)[0]
    input_files = find_input_files(prob_dir)
    compile_code(filename, run_path)
    ac = 0
    idx = 1
    for in_file in input_files:
        d = path.dirname(in_file)
        f = path.basename(in_file)
        output_file = d + sep + 'ans' + f[2:]
        if not path.isfile(output_file):
            continue
        proc = subprocess.Popen([run_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        inputs = open(in_file, "rb").read()
        proc.stdin.write(inputs)
        try:
            outputs, error = proc.communicate(timeout=5)
            if proc.returncode != 0:
                print("[!] Failed with exit code : {}".format(proc.returncode))
                if outputs: print(outputs.decode())
                if error: print(error.decode())
                continue
            expected_outputs = open(output_file, "rb").read()
            same = True
            report = ''
            a = outputs.decode().splitlines()
            b = expected_outputs.decode().splitlines()
            max_length = max(len(a), len(b))
            a += [''] * (max_length - len(a))
            b += [''] * (max_length - len(b))
            for o1, o2 in zip(a, b):
                if o1.strip() == o2.strip():
                    report += ' ' + o1 + '\n'
                    continue
                else:
                    same = False
                    report += ui.setcolor('red', o1.ljust(20, ' '))
                    report += ui.setcolor('green', o2.ljust(20, ' ')) + '\n'
            if same:
                ac += 1
                ui.green("Passed #{}".format(idx))
            else:
                ui.red("Failed #{}".format(idx))
                ui.white("=======  IN #{:d} =======".format(idx))
                print(inputs.decode())
                ui.white("======= OUT #{:d} =======".format(idx))
                print(report)
        except subprocess.TimeoutExpired:
            proc.kill()
            outputs, error = proc.communicate()
            ui.red("[!] Timeout!")
            if outputs: print(outputs.decode())
            if error: print(error.decode())
        idx += 1
    total = len(input_files)
    if total == 0:
        ui.red("[!] There is no testcases")
    elif total == ac:
        ui.green("[{}/{}] Accepted".format(ac, total))
    else:
        ui.red("[{}/{}] Wrong Answer".format(ac, total))
    unlink(run_path)

def generate_code(args):
    pid = guess_pid(args)
    if not pid:
        print("[!] Invalid problem ID")
        return
    template_path = path.expanduser(config.conf['template'])
    if not path.isfile(template_path):
        print("[!] Template file not found")
        return
    prob_dir = prepare_problem_dir(pid)
    ext = path.splitext(template_path)[-1]
    assert ext != "", "[!] File extension not found"
    new_path = prob_dir + sep + str(pid) + ext
    inf = open(template_path, 'r')
    outf = open(new_path, 'w')
    for line in inf:
        outf.write(line)
    ui.green('[+] Generate {}'.format(new_path))
