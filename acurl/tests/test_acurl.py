import pytest

import acurl


# Curl will return a non-zero exit code when something goes wrong
# https://curl.se/libcurl/c/libcurl-errors.html
# https://everything.curl.dev/usingcurl/returns
@pytest.fixture
@pytest.mark.asyncio
async def test_non_zero_exit_code_raises(acurl_session):
    with pytest.raises(acurl.AcurlError, match=r"curl failed with code 6.*"):
        # Curl returns CURLE_COULDNT_RESOLVE_HOST (6) exit code
        await acurl_session.get("unresolvable_hostname.doesnotexist")
