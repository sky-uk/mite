import importlib
import warnings

import pytest

import mite_finagle as mite_finagle_pkg
from mite_finagle import mite_finagle


def test_no_warning_on_bare_import():
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        importlib.reload(mite_finagle_pkg)
    future_warnings = [w for w in record if issubclass(w.category, FutureWarning)]
    assert not future_warnings


def test_warns_on_use():
    with pytest.warns(FutureWarning, match="mite_finagle will require"):

        @mite_finagle
        async def foo(ctx):
            pass
