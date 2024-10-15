import os

from mite.config import ConfigManager, default_config_loader

TEST_DICT = dict(
    {
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
        "key4": "value4",
        "key5": "value5",
    }
)


def test_config_manager():
    conf_manager = ConfigManager()
    for k, v in TEST_DICT.items():
        conf_manager.set(k, v)
    assert conf_manager._config["key5"] == ("value5", 5)


def test_get_changes_for_runner():
    conf_manager = ConfigManager()
    for k, v in TEST_DICT.items():
        conf_manager.set(k, v)
    runner_list = conf_manager.get_changes_for_runner("test_id")
    assert runner_list[-1] == ("key5", TEST_DICT["key5"])


def test_default_config_loader():
    os.environ["MITE_CONF_TEST1"] = "test1"
    os.environ["MITE_CONF_TEST2"] = "test2"
    os.environ["MITE_CONF_TEST3"] = "test3"
    os.environ["MITE_CONF_TEST4"] = "test4"
    os.environ["MITE_CONF_TEST5"] = "test5"

    default_conf = default_config_loader()

    assert default_conf["TEST1"] == os.environ["MITE_CONF_TEST1"]
    assert default_conf["TEST2"] == os.environ["MITE_CONF_TEST2"]
    assert default_conf["TEST3"] == os.environ["MITE_CONF_TEST3"]
    assert default_conf["TEST4"] == os.environ["MITE_CONF_TEST4"]
    assert default_conf["TEST5"] == os.environ["MITE_CONF_TEST5"]


def test_get():
    cm = ConfigManager()
    cm.set("foo", "bar")
    assert cm.get("foo") == "bar"


def test_get_with_default():
    cm = ConfigManager()
    foo = cm.get("foo", "bar")
    assert foo == "bar"
