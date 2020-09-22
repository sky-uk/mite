import glob
import os
import tempfile
from unittest.mock import Mock

from mite.collector import Collector
from mite.utils import pack_msg

raw_msg = "  TEST_MSG_"
check_msg_value = "TEST_MSG_0  TEST_MSG_1  TEST_MSG_2  TEST_MSG_3  TEST_MSG_4"
check_msg_rollback = " TEST_MSG_5"


def test_collector_msg_value():
    with tempfile.TemporaryDirectory() as temp_dir:
        collector = Collector(temp_dir)
        for i in range(5):
            collector.process_raw_message((raw_msg + str(i)).encode())

        # Force the buffer to write to the file by removing the open handle
        del collector

        new_file = temp_dir + '/current'
        with open(new_file, 'r') as f:
            last_string = f.readline()
        assert check_msg_value in last_string


def test_collector_rollback():
    with tempfile.TemporaryDirectory() as temp_dir:
        collector = Collector(temp_dir, 5)
        for i in range(9):
            collector.process_raw_message((raw_msg + str(i)).encode())

        # Force the buffer to write to the dile by removing the open hadle
        del collector

        new_file = temp_dir + '/current'
        with open(new_file, 'r') as f:
            f0_last_string = f.readline()
        test_dir = temp_dir + '/'
        new_file = glob.glob(os.path.join(test_dir, '16*0'))[0]
        with open(new_file, 'r') as f:
            f1_last_string = f.readline()
        assert check_msg_rollback in f0_last_string
        assert check_msg_value in f1_last_string


def test_rotating_file():
    with tempfile.TemporaryDirectory() as temp_dir:
        collector = Collector(temp_dir)
        collector.process_raw_message((raw_msg).encode())

        # Force the buffer to write to the file by removing the open handle
        del collector

        coll_curr_start_time = os.path.join(temp_dir, 'current_start_time')
        assert os.path.isfile(
            coll_curr_start_time
        ), "The collector_start_time file doen't exist"
        with open(coll_curr_start_time, "r") as f:
            start_time = f.read()

        # Creating a new controler to rotate the current file
        collector = Collector(temp_dir)  # noqa: F841

        assert any(file.startswith(start_time + "_") for file in os.listdir(temp_dir))


def test_filter_fn():
    filter_mock = Mock()
    test_dict = {"type": "test"}
    test_msg = pack_msg(test_dict)
    with tempfile.TemporaryDirectory() as temp_dir:
        collector = Collector(target_dir=temp_dir, filter_fn=filter_mock)
        collector.process_raw_message(test_msg)
    filter_mock.assert_called_once_with(test_dict)


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
