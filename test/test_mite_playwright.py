from unittest.mock import AsyncMock, patch

import pytest

# Check if playwright is available
try:
    from mite_playwright import mite_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not PLAYWRIGHT_AVAILABLE,
    reason="Playwright not installed - run with 'hatch run test-playwright.py3.11:test'"
)


@pytest.mark.asyncio
async def test_mite_playwright_decorator():
    """Test decorator starts and stops playwright"""

    @mite_playwright
    async def dummy_journey(ctx, playwright):
        assert playwright is not None
        return "success"

    with patch("mite_playwright.async_playwright") as mock_pw:
        mock_playwright_instance = AsyncMock()
        mock_pw.return_value.start = AsyncMock(return_value=mock_playwright_instance)

        # Don't need MockContext - just pass None
        result = await dummy_journey(None)

        assert result == "success"
        mock_pw.return_value.start.assert_called_once()
        mock_playwright_instance.stop.assert_called_once()
