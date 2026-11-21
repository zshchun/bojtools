import sys
from unittest.mock import Mock

import pytest


@pytest.fixture
def cli(boj_config, monkeypatch):
    from bojtools import __main__

    monkeypatch.setattr(__main__.util, "register_signal", Mock())
    return __main__


def run_cli(cli, monkeypatch, *args):
    argv = ["boj", *args]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(cli, "argv", argv)
    cli.main()


@pytest.mark.parametrize(
    "command, alias, module, handler, arguments, expected",
    [
        ("login", "l", "login", "start", [], {}),
        ("init", "I", "init", "setup", [], {}),
        ("pick", "p", "boj", "pick", ["1000", "--force"], {"pid": 1000, "force": True}),
        ("solution", "q", "boj", "view_solutions", ["1000"], {"pid": 1000}),
        (
            "test", "t", "judge", "test",
            ["1000", "-i", "1000.py"], {"pid": 1000, "input": "1000.py"},
        ),
        (
            "submit", "s", "submit", "submit",
            ["1000", "--input", "1000.py"], {"pid": 1000, "input": "1000.py"},
        ),
        ("generate", "g", "boj", "generate_code", ["1000"], {"pid": 1000}),
        ("info", "i", "boj", "problem_info", ["1000", "--level"], {"pid": 1000, "level": True}),
        (
            "archive", "A", "boj", "archive_prob",
            ["1000", "1002", "-f"], {"prob_start": 1000, "prob_end": 1002, "force": True},
        ),
        (
            "class", "c", "solved", "pick_class",
            ["3", "-a", "-e", "-l"], {"level": 3, "all": True, "essential": True, "list": True},
        ),
        (
            "random", "r", "solved", "pick_random",
            ["b5", "s1", "-l", "-s", "25"],
            {"level_start": "b5", "level_end": "s1", "list": True, "solved_count": 25},
        ),
    ],
)
@pytest.mark.parametrize("use_alias", [False, True], ids=["command", "alias"])
def test_dispatches_with_parsed_arguments(
    cli, monkeypatch, command, alias, module, handler, arguments, expected, use_alias
):
    dispatch = Mock()
    monkeypatch.setattr(getattr(cli, module), handler, dispatch)
    spelling = alias if use_alias else command

    run_cli(cli, monkeypatch, spelling, *arguments)

    dispatch.assert_called_once()
    assert vars(dispatch.call_args.args[0]) == {"command": spelling, "func": dispatch, **expected}
    cli.util.register_signal.assert_called_once_with()


def test_pick_leaves_problem_id_optional_and_force_disabled(cli, monkeypatch):
    dispatch = Mock()
    monkeypatch.setattr(cli.boj, "pick", dispatch)

    run_cli(cli, monkeypatch, "pick")

    dispatch.assert_called_once()
    args = dispatch.call_args.args[0]
    assert args.pid is None
    assert args.force is False


def test_prints_help_without_a_command(cli, monkeypatch, capsys):
    run_cli(cli, monkeypatch)

    output = capsys.readouterr().out
    assert "usage: boj" in output
    assert "Test with testcases" in output


def test_prints_version_and_exits_successfully(cli, monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        run_cli(cli, monkeypatch, "--version")

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"boj {cli.__version__}"


def test_rejects_non_numeric_problem_id_before_dispatch(cli, monkeypatch, capsys):
    dispatch = Mock()
    monkeypatch.setattr(cli.boj, "pick", dispatch)

    with pytest.raises(SystemExit) as exc:
        run_cli(cli, monkeypatch, "pick", "not-a-number")

    assert exc.value.code == 2
    assert "not-a-number" in capsys.readouterr().err
    dispatch.assert_not_called()
