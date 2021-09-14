import pytest

import acurl_ng


@pytest.fixture
def acurl_session_ng(event_loop):
    w = acurl_ng.CurlWrapper(event_loop)
    s = w.session()
    yield s
