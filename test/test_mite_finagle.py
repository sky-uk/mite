import importlib

import pytest

import mite_finagle as mite_finagle_pkg


def test_warns_on_import():
    with pytest.warns(FutureWarning, match="mite_finagle will require"):
        importlib.reload(mite_finagle_pkg)
