import os
import tempfile

import msgpack

from mite.recorder import Recorder

data_value = "Data value for the recorder unit test"
msg_create = {"type": "data_created", "name": "recorder_create_test", "data": data_value}
msg_purge = {"type": "purge_data", "name": "recorder_purge_test", "data": data_value}


def test_process_message_file_opening():
    with tempfile.TemporaryDirectory() as tempdir:
        recorder = Recorder(target_dir=tempdir)
        recorder.process_message(msg_create)
        assert os.path.isfile(os.path.join(tempdir, msg_create["name"] + ".msgpack"))


def test_process_message_right_content():
    with tempfile.TemporaryDirectory() as tempdir:
        recorder = Recorder(target_dir=tempdir)
        recorder.process_message(msg_create)
        with open(os.path.join(tempdir, msg_create["name"] + ".msgpack"), "rb") as f:
            unpacked = msgpack.Unpacker(f, raw=False, use_list=False)
            assert next(unpacked) == data_value


def test_process_message_remove_file():
    with tempfile.TemporaryDirectory() as tempdir:
        with open(os.path.join(tempdir, msg_purge["name"] + ".msgpack"), "wb") as f:
            f.write(data_value.encode("utf-8"))
        recorder = Recorder(target_dir=tempdir)
        recorder.process_message(msg_purge)
        try:
            open(os.path.join(tempdir, msg_purge["name"] + ".msgpack"), "rb")
            assert False, "The file has not been removed"
        except FileNotFoundError:
            assert True
        except Exception as e:
            assert False, e
