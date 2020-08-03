from pytest import raises

from mite import zmq
from mite.utils import _msg_backend_module, spec_import


def test_spec_import():
    # Perhaps hacky that I used another imported thing
    # Seemed most concise way to test
    spec = "mite.utils:_msg_backend_module"
    assert spec_import(spec) == _msg_backend_module


def test_msg_backend_module_zmq():
    opts = {"--message-backend": "ZMQ"}
    assert _msg_backend_module(opts) == zmq


# TODO: Add libnanomsg to Jenkins slave
# def test_msg_backend_module_nanomsg():
#    opts = {"--message-backend": "nanomsg"}
#    assert _msg_backend_module(opts) == nanomsg


def test_msg_backend_module_not_supported():
    # arguably we should .lower() and support this
    opts = {"--message-backend": "zmq"}
    with raises(ValueError):
        _msg_backend_module(opts)
