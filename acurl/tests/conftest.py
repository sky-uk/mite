import pytest

import acurl


@pytest.fixture
def acurl_session(event_loop):
    w = acurl.CurlWrapper(event_loop)
    s = w.session()
    yield s
