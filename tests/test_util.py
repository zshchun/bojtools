import signal
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock, call

import pytest
from lxml import html


def test_get_tag_text_and_wrap_html(boj_config):
    from bojtools import util

    tags = html.fragment_fromstring("<p>가\n\t나</p><p>다</p>", create_parent=True)
    boj_config.conf["text_width"] = 4

    assert util.get_tag_text(tags) == "가\n 나다"
    assert util.get_tag_text([]) == ""
    assert util.wrap_html_text("<b>가나다</b>") == "가나\n다"
    assert util.wrap_html_text("") == ""


def test_guess_pid_prefers_argument_and_falls_back_to_numeric_directory(boj_config, monkeypatch, tmp_path):
    from bojtools import util

    problem_dir = tmp_path / "1000"
    problem_dir.mkdir()
    monkeypatch.chdir(problem_dir)
    assert util.get_cwd_info() == 1000
    assert util.guess_pid(Namespace(pid=2000)) == 2000
    assert util.guess_pid(Namespace(pid=None)) == 1000
    monkeypatch.chdir(tmp_path)
    assert util.guess_pid(Namespace(pid=None)) is None


def test_select_source_code_requires_a_single_supported_file(boj_config, monkeypatch, capsys):
    from bojtools import util

    problem_dir = Path(util.prepare_problem_dir(1000))
    assert problem_dir == Path(boj_config.conf["code_dir"]) / "1000"
    monkeypatch.chdir(problem_dir)
    (problem_dir / "notes.txt").touch()
    (problem_dir / "folder.py").mkdir()
    assert util.find_source_files(str(problem_dir)) == []
    assert util.select_source_code(1000) is None

    source = problem_dir / "1000.py"
    source.touch()
    assert util.find_source_files(str(problem_dir)) == [str(source)]
    assert util.select_source_code(1000) == str(source)

    (problem_dir / "1000.cpp").touch()
    assert util.select_source_code(1000) is None
    assert "multiple solutions" in capsys.readouterr().out


def test_find_source_files_is_independent_of_current_directory(boj_config, monkeypatch, tmp_path):
    from bojtools import util

    problem_dir = Path(util.prepare_problem_dir(1000))
    source = problem_dir / "1000.py"
    source.touch()
    (problem_dir / "folder.py").mkdir()
    (tmp_path / "folder.py").touch()
    monkeypatch.chdir(tmp_path)

    assert util.find_source_files(str(problem_dir)) == [str(source)]


@pytest.mark.parametrize(
    ("value", "width", "wrapped"),
    [("abc", 2, "ab\nc"), ("가나다", 4, "가나\n다"), ("a\n\nb", 5, "a\n\nb"), ("", 4, "")],
)
def test_text_wrap_handles_display_width_and_line_breaks(boj_config, value, width, wrapped):
    from bojtools import util

    assert util.text_wrap(value, width) == wrapped


def test_unicode_format_aligns_korean_and_numeric_values(boj_config):
    from bojtools import util

    assert util.unicode_format("|{:>4s}|{:<4s}|{:03d}|", "한", "글", 7) == "|  한|글  |007|"


def test_signal_registration_and_handler(boj_config, monkeypatch, capsys):
    from bojtools import util

    register = Mock()
    kill = Mock()
    monkeypatch.setattr(util.signal, "signal", register)
    monkeypatch.setattr(util, "kill", kill)
    monkeypatch.setattr(util, "getpid", lambda: 123)

    util.register_signal()
    util.sig_handler(signal.SIGTERM, None)

    assert register.call_args_list == [
        call(signal.SIGINT, util.sig_handler),
        call(signal.SIGTERM, util.sig_handler),
        call(signal.SIGTERM, signal.SIG_DFL),
    ]
    kill.assert_called_once_with(123, signal.SIGTERM)
    assert "Terminated by signal" in capsys.readouterr().out
