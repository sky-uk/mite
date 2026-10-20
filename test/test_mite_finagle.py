import pytest

from mite_finagle import mite_finagle


def test_warns_on_use():
    with pytest.warns(FutureWarning, match="mite_finagle will require"):

        @mite_finagle
        async def foo(ctx):
            pass
