import pytest

import acurl_ng


@pytest.fixture
def acurl_session(event_loop):
    w = acurl_ng.CurlWrapper(event_loop)
    s = w.session()
    yield s
