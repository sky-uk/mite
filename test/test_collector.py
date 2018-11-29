import os
import glob
import tempfile
from mite.collector import Collector

raw_msg = "  TEST_MSG_"
check_msg_value = "TEST_MSG_0  TEST_MSG_1  TEST_MSG_2  TEST_MSG_3  TEST_MSG_4"
check_msg_rollback = " TEST_MSG_5"


def test_collector_msg_value():

    temp_dir = tempfile.mkdtemp()
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
    temp_dir = tempfile.mkdtemp()
    collector = Collector(temp_dir, 5)
    for i in range(9):
        collector.process_raw_message((raw_msg + str(i)).encode())

    # Force the buffer to write to the dile by removing the open hadle
    del collector

    new_file = temp_dir + '/current'
    with open(new_file, 'r') as f:
        f0_last_string = f.readline()
    test_dir = temp_dir + '/'
    new_file = glob.glob(os.path.join(test_dir, '15*0'))[0]
    with open(new_file, 'r') as f:
        f1_last_string = f.readline()
    assert check_msg_rollback in f0_last_string
    assert check_msg_value in f1_last_string
