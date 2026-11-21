import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def sample_problem(boj_config):
    problem_dir = Path(boj_config.conf["code_dir"]) / "1000"
    problem_dir.mkdir()
    source = problem_dir / "1000.py"
    source.write_text("print(sum(map(int, input().split())))\n", encoding="utf-8")
    (problem_dir / "in1.txt").write_text("1 2\n", encoding="utf-8")
    (problem_dir / "ans1.txt").write_text("3\n", encoding="utf-8")
    for language in boj_config.conf["lang"]:
        if language["ext"] == "py":
            language["cmd"] = [sys.executable, "%SOURCE%"]
    return problem_dir, Namespace(pid=1000, input=str(source))


def test_find_input_files_filters_and_sorts(boj_config, sample_problem, monkeypatch):
    from bojtools import judge

    problem_dir, _ = sample_problem
    (problem_dir / "in2.txt").touch()
    (problem_dir / "in3.json").touch()
    (problem_dir / "in4.txt").mkdir()
    monkeypatch.chdir(problem_dir)

    assert judge.find_input_files(str(problem_dir)) == [
        str(problem_dir / "in1.txt"),
        str(problem_dir / "in2.txt"),
    ]


def test_find_input_files_is_independent_of_current_directory(
    boj_config, sample_problem, monkeypatch, tmp_path
):
    from bojtools import judge

    problem_dir, _ = sample_problem
    (problem_dir / "in2.txt").mkdir()
    (tmp_path / "in2.txt").touch()
    monkeypatch.chdir(tmp_path)

    assert judge.find_input_files(str(problem_dir)) == [str(problem_dir / "in1.txt")]


@pytest.mark.parametrize("returncode", [0, 1])
def test_compile_code_reports_compiler_failure(boj_config, monkeypatch, capsys, returncode):
    from bojtools import judge

    cmd = ["compiler", "main.cpp"]
    run = Mock(return_value=subprocess.CompletedProcess(cmd, returncode, b"compiler output", b"error"))
    monkeypatch.setattr(judge.subprocess, "run", run)

    if returncode:
        with pytest.raises(SystemExit) as stopped:
            judge.compile_code(cmd)
        assert stopped.value.code == 1
        output = capsys.readouterr().out
        assert "compiler output" in output
        assert "error" in output
        assert "Compile error" in output
    else:
        judge.compile_code(cmd)
        assert not capsys.readouterr().out
    run.assert_called_once_with(cmd, capture_output=True)


@pytest.mark.parametrize(("answer", "outcome"), [("3\n", "Accepted"), ("4\n", "Wrong Answer")])
def test_local_judge_compares_outputs_offline(
    boj_config, sample_problem, monkeypatch, capsys, answer, outcome
):
    from bojtools import judge

    problem_dir, args = sample_problem
    monkeypatch.chdir(problem_dir)
    (problem_dir / "ans1.txt").write_text(answer, encoding="utf-8")
    open_session = Mock(side_effect=AssertionError("The local judge must run offline"))
    monkeypatch.setattr(judge._http, "open_session", open_session)

    judge.test(args)

    assert outcome in capsys.readouterr().out
    open_session.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        subprocess.CalledProcessError(1, ["test-program"], output=b"process failed"),
        subprocess.TimeoutExpired(["test-program"], 5, output=b"process timed out"),
    ],
)
def test_local_judge_reports_process_errors(boj_config, sample_problem, monkeypatch, capsys, error):
    from bojtools import judge

    problem_dir, args = sample_problem
    monkeypatch.chdir(problem_dir)
    monkeypatch.setattr(judge.subprocess, "run", Mock(side_effect=error))

    judge.test(args)

    output = capsys.readouterr().out
    assert "Failed #1" in output
    assert error.stdout.decode() in output
    assert "[0/1]" in output


def test_local_judge_reports_missing_samples(boj_config, sample_problem, monkeypatch, capsys):
    from bojtools import judge

    problem_dir, args = sample_problem
    (problem_dir / "in1.txt").unlink()
    monkeypatch.chdir(problem_dir)

    judge.test(args)

    assert "There is no testcases" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("pid", "source_name", "source_exists", "message"),
    [
        (None, "1000.py", True, "Invalid problem ID"),
        (1000, "missing.py", False, "File not found"),
        (1000, "1000.txt", True, "Unsupported langugage"),
    ],
)
def test_local_judge_rejects_invalid_arguments(
    boj_config, monkeypatch, tmp_path, capsys, pid, source_name, source_exists, message
):
    from bojtools import judge

    monkeypatch.chdir(tmp_path)
    source = tmp_path / source_name
    if source_exists:
        source.touch()
    run = Mock()
    monkeypatch.setattr(judge.subprocess, "run", run)

    judge.test(Namespace(pid=pid, input=str(source)))

    assert message in capsys.readouterr().out
    run.assert_not_called()


def test_local_judge_compiles_runs_and_removes_output(boj_config, sample_problem, monkeypatch, capsys):
    from bojtools import judge

    problem_dir, args = sample_problem
    monkeypatch.chdir(problem_dir)
    source = problem_dir / "1000.cpp"
    source.touch()
    args.input = str(source)
    binary = source.with_suffix("")
    compiler_args = boj_config.conf["lang"][0]["compile"]
    expected_arguments = [
        arg.replace("%PROB_NUM%", str(binary)).replace("%SOURCE%", str(source))
        for arg in compiler_args
    ]

    def run_program(command, **kwargs):
        assert binary.is_file()
        assert kwargs["input"] == b"1 2\n"
        return subprocess.CompletedProcess(command, 0, stdout=b"3\n")

    def compile_program(command):
        assert command == expected_arguments
        binary.touch()

    run = Mock(side_effect=run_program)
    monkeypatch.setattr(judge.subprocess, "run", run)
    monkeypatch.setattr(judge, "compile_code", compile_program)

    judge.test(args)

    assert "Accepted" in capsys.readouterr().out
    assert run.call_args.args == ([str(binary)],)
    assert not binary.exists()
