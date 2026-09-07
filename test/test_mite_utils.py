import subprocess
import sys
from unittest.mock import MagicMock

from pytest import raises, warns

from mite import zmq
from mite.utils import _msg_backend_module, spec_import


def test_mite_utils_no_warning_on_import():
    result = subprocess.run(
        [sys.executable, "-W", "error::FutureWarning", "-c", "import mite.utils"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_spec_import():
    # Perhaps hacky that I used another imported thing
    # Seemed most concise way to test
    spec = "mite.utils:_msg_backend_module"
    assert spec_import(spec) == _msg_backend_module


def test_msg_backend_module_zmq():
    opts = {"--message-backend": "ZMQ"}
    assert _msg_backend_module(opts) == zmq


def test_msg_backend_module_nanomsg_warns(monkeypatch):
    # The real nanomsg C-extension doesn't import in this dev environment (see
    # the skipped test below), so mock it to exercise the warning without a
    # working nanomsg install.
    monkeypatch.setitem(sys.modules, "mite.nanomsg", MagicMock())
    with warns(FutureWarning, match="nanomsg support will move"):
        _msg_backend_module({"--message-backend": "nanomsg"})


# TODO: Add libnanomsg to Jenkins slave
# def test_msg_backend_module_nanomsg():
#    opts = {"--message-backend": "nanomsg"}
#    assert _msg_backend_module(opts) == nanomsg


def test_msg_backend_module_not_supported():
    # arguably we should .lower() and support this
    opts = {"--message-backend": "zmq"}
    with raises(ValueError):
        _msg_backend_module(opts)
