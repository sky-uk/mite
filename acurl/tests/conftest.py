import pytest
import acurl
import inspect


@pytest.fixture
def acurl_session(event_loop):
    w = acurl.CurlWrapper(event_loop)
    session = w.session()
    try:
        yield session
    finally:
        # Attempt to close the session if it has a close method
        close = getattr(session, "close", None)
        if callable(close):
            if inspect.iscoroutinefunction(close):
                event_loop.run_until_complete(close())
            else:
                close()
        # Explicitly close the CurlWrapper if it has a close method
        w_close = getattr(w, "close", None)
        if callable(w_close):
            if inspect.iscoroutinefunction(w_close):
                event_loop.run_until_complete(w_close())
            else:
                w_close()
