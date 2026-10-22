import importlib
import sys
from unittest.mock import MagicMock

import pytest


def test_warns_on_import(monkeypatch):
    # The real nanomsg C-extension doesn't import in this dev environment
    # (pre-existing gap, see the skipped test_msg_backend_module_nanomsg in
    # test_mite_utils.py: "Add libnanomsg to Jenkins slave"), so mock it out
    # at the sys.modules level - this lets the test exercise mite.nanomsg's
    # own import-time warning without needing a working nanomsg install.
    monkeypatch.setitem(sys.modules, "nanomsg", MagicMock())
    monkeypatch.delitem(sys.modules, "mite.nanomsg", raising=False)
    try:
        with pytest.warns(FutureWarning, match="nanomsg support will move"):
            importlib.import_module("mite.nanomsg")
    finally:
        # mite.nanomsg is not normally in sys.modules (only mite/utils.py
        # imports it, lazily, under --message-backend=nanomsg) - leaving a
        # MagicMock-backed copy behind would affect any later test that
        # imports it for real.
        sys.modules.pop("mite.nanomsg", None)
