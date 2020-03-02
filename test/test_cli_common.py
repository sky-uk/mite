from mite.cli.common import _create_config_manager


def dummy_config():
    return {"foo": "bar"}


def test_create_config_manager():
    cm = _create_config_manager({
        "--config": "test_cli_common:dummy_config",
        "--add-to-config": (),
    })
    assert cm.get("foo") == "bar"


def test_create_config_manager_add_to_config():
    cm = _create_config_manager({
        "--config": "test_cli_common:dummy_config",
        "--add-to-config": ("abc:xyz",),
    })
    assert cm.get("foo") == "bar"
    assert cm.get("abc") == "xyz"
