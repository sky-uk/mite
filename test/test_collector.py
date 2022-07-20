import json
import os
import tempfile
from unittest.mock import Mock, patch

from docopt import docopt

import mite.__main__ as main
import mite.cli.collector as cli_collector
from mite.collector import Collector
from mite.utils import pack_msg

raw_msg = "  TEST_MSG_"
check_msg_value = b"TEST_MSG_0  TEST_MSG_1  TEST_MSG_2  TEST_MSG_3  TEST_MSG_4"
check_msg_rollback = b" TEST_MSG_5"


def test_collector_msg_value():
    with tempfile.TemporaryDirectory() as temp_dir:
        collector = Collector(temp_dir)
        for i in range(5):
            collector.process_raw_message((raw_msg + str(i)).encode())

        # Force the buffer to write to the file by removing the open handle
        del collector

        new_file = f"{temp_dir}/current"
        with open(new_file, "rb") as f:
            last_string = f.read()
        assert last_string == b"  " + check_msg_value


def test_collector_rollover():
    with tempfile.TemporaryDirectory() as temp_dir:
        collector = Collector(temp_dir, roll_after=5)
        for i in range(9):
            collector.process_raw_message((raw_msg + str(i)).encode())

        del collector

        new_file = f"{temp_dir}/current"
        with open(new_file, "rb") as f:
            f0_last_string = f.read()

        files = [x for x in os.listdir(temp_dir) if x.endswith("_0")]
        assert len(files) == 1, "could not find a unique rolled collector file"
        new_file = os.path.join(temp_dir, files[0])
        with open(new_file, "rb") as f:
            f1_last_string = f.read()
        assert check_msg_rollback in f0_last_string
        assert check_msg_value in f1_last_string


def test_rotating_file():
    with tempfile.TemporaryDirectory() as temp_dir:
        collector = Collector(temp_dir)
        collector.process_raw_message((raw_msg).encode())

        del collector

        coll_curr_start_time = os.path.join(temp_dir, "current_start_time")
        assert os.path.isfile(
            coll_curr_start_time
        ), "The collector_start_time file doen't exist"
        with open(coll_curr_start_time, "r") as f:
            start_time = f.read()

        # Creating a new controler to rotate the current file
        collector = Collector(temp_dir)  # noqa: F841

        assert any(file.startswith(f"{start_time}_") for file in os.listdir(temp_dir))


def test_filter_fn():
    filter_mock = Mock()
    test_dict = {"type": "test"}
    test_msg = pack_msg(test_dict)
    with tempfile.TemporaryDirectory() as temp_dir:
        collector = Collector(target_dir=temp_dir, filter_fn=filter_mock)
        collector.process_raw_message(test_msg)
    filter_mock.assert_called_once_with(test_msg)


def test_filter_fn_true():
    filter_mock = lambda x: True
    test_dict = {"type": "test"}
    test_msg = pack_msg(test_dict)
    with tempfile.TemporaryDirectory() as temp_dir:
        collector = Collector(target_dir=temp_dir, filter_fn=filter_mock)
        collector.process_raw_message(test_msg)
        del collector
        with open(os.path.join(temp_dir, "current"), "rb") as fin:
            assert test_msg in fin.read()


def test_filter_fn_false():
    filter_mock = lambda x: False
    test_dict = {"type": "test"}
    test_msg = pack_msg(test_dict)
    with tempfile.TemporaryDirectory() as temp_dir:
        collector = Collector(target_dir=temp_dir, filter_fn=filter_mock)
        collector.process_raw_message(test_msg)
        del collector
        with open(os.path.join(temp_dir, "current"), "rb") as fin:
            assert test_msg not in fin.read()


def test_use_json():
    test_dict = {"type": "test"}
    test_msg = pack_msg(test_dict)
    with tempfile.TemporaryDirectory() as temp_dir:
        collector = Collector(target_dir=temp_dir, use_json=True)
        collector.process_raw_message(test_msg)
        del collector
        with open(os.path.join(temp_dir, "current"), "r") as fin:
            assert fin.read() == json.dumps(test_dict) + "\n"


def test_collector_cli_defaults():
    opts = docopt(main.__doc__, ["collector"])
    with patch("asyncio.get_event_loop"), patch(
        "mite.cli.collector._collector_receiver"
    ) as receiver_mock:
        c = cli_collector.collector(opts)
    c = receiver_mock.return_value.add_raw_listener.call_args_list[0][0][0].__self__
    assert c._filter_fn is None
    assert not c._use_json
    assert c._roll_after == 100000
    assert c._target_dir == os.path.abspath("collector_data")


def test_collector_cli_use_json():
    opts = docopt(main.__doc__, ["collector", "--collector-use-json"])
    with patch("asyncio.get_event_loop"), patch(
        "mite.cli.collector._collector_receiver"
    ) as receiver_mock:
        cli_collector.collector(opts)
    c = receiver_mock.return_value.add_raw_listener.call_args_list[0][0][0].__self__
    assert c._use_json


def foo():
    pass


def test_collector_cli_filter():
    opts = docopt(main.__doc__, ["collector", "--collector-filter=test_collector:foo"])
    with patch("asyncio.get_event_loop"), patch(
        "mite.cli.collector._collector_receiver"
    ) as receiver_mock:
        cli_collector.collector(opts)
    c = receiver_mock.return_value.add_raw_listener.call_args_list[0][0][0].__self__
    assert c._filter_fn is foo
