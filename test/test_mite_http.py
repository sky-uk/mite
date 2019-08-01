from mocks.mock_context import MockContext
from mite_http import mite_http
import pytest


@pytest.mark.asyncio
async def test_get(httpserver):
    httpserver.expect_oneshot_request("/test", "GET").respond_with_data("hi")
    context = MockContext()

    @mite_http
    async def test(ctx):
        await ctx.http.get(httpserver.url_for("/test"))

    await test(context)
    assert len(httpserver.log) == 1
    assert len(context.messages) == 1
