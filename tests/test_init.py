import pytest
import tomli


@pytest.mark.parametrize("has_previous_config", [False, True], ids=["new", "existing"])
def test_setup_writes_default_config(
    boj_config, monkeypatch, tmp_path, capsys, has_previous_config
):
    from bojtools import init

    config_path = tmp_path / "config.toml"
    if has_previous_config:
        config_path.write_text('custom_setting = "old value"\n', encoding="utf-8")
    monkeypatch.setattr(boj_config, "config_path", str(config_path))

    init.setup(None)

    with config_path.open("rb") as config_file:
        assert tomli.load(config_file) == boj_config.DEFAULT_CONFIG
    assert f"Initial file generated: {config_path}" in capsys.readouterr().out
