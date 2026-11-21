from os import linesep

import pytest


@pytest.fixture
def ui(boj_config):
    from bojtools import ui

    return ui


@pytest.mark.parametrize(
    "helper, color_code",
    [
        ("BLUE", 34),
        ("RED", 31),
        ("GREEN", 32),
        ("YELLOW", 33),
        ("MAGENTA", 35),
        ("CYAN", 36),
        ("WHITE", 37),
        ("BBLUE", 94),
        ("BRED", 91),
        ("BGREEN", 92),
        ("BYELLOW", 93),
        ("BMAGENTA", 95),
        ("BCYAN", 96),
        ("BWHITE", 97),
        ("GRAY", 90),
    ],
)
def test_color_helpers_wrap_and_reset_terminal_style(ui, helper, color_code):
    assert getattr(ui, helper)("정답") == f"\033[{color_code}m정답\033[0m"


@pytest.mark.parametrize(
    "color, expected",
    [
        ("green", "\033[32m정답\033[0m"),
        ("orange", "\033[33m정답\033[0m"),
        ("legendary", "\033[37m정\033[31m답\033[0m"),
        ("unknown", "정답"),
        (None, "정답"),
    ],
)
def test_setcolor(ui, color, expected):
    assert ui.setcolor(color, "정답") == expected


def test_redraw_moves_cursor_up_and_uses_default_line_separator(ui, capsys):
    ui.redraw("채점 중")

    assert capsys.readouterr().out == f"\033[A채점 중{linesep}"


def test_redraw_accepts_custom_end(ui, capsys):
    ui.redraw("채점 완료", end="")

    assert capsys.readouterr().out == "\033[A채점 완료"
