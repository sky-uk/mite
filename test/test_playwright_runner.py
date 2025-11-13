import pytest
from unittest.mock import AsyncMock, patch

from mocks.mock_context import MockContext
from mite_playwright.playwright_runner import mite_playwright


@pytest.mark.asyncio
async def test_new_page():
    """Test new_page creates a page"""
    mock_context = MockContext()
    
    mock_page = AsyncMock()
    mock_browser_context = AsyncMock()
    mock_browser_context.new_page = AsyncMock(return_value=mock_page)
    
    @mite_playwright
    async def dummy_journey(ctx):
        page = await ctx.browser.new_page()
        return page
    
    with patch('mite_playwright.playwright_runner.async_playwright') as mock_pw:
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        
        mock_pw.return_value.start = AsyncMock(return_value=mock_playwright)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_browser_context)
        
        page = await dummy_journey(mock_context)
        
        assert page == mock_page


@pytest.mark.asyncio
async def test_goto():
    """Test goto navigates to URL"""
    mock_context = MockContext()
    
    url = "https://example.com"
    mock_page = AsyncMock()
    mock_response = AsyncMock()
    mock_response.request.timing = {}
    mock_page.goto = AsyncMock(return_value=mock_response)
    
    mock_browser_context = AsyncMock()
    mock_browser_context.new_page = AsyncMock(return_value=mock_page)
    
    @mite_playwright
    async def dummy_journey(ctx):
        page = await ctx.browser.new_page()
        response = await ctx.browser.goto(page, url)
        return response
    
    with patch('mite_playwright.playwright_runner.async_playwright') as mock_pw:
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        
        mock_pw.return_value.start = AsyncMock(return_value=mock_playwright)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_browser_context)
        
        response = await dummy_journey(mock_context)
        
        assert response == mock_response


@pytest.mark.asyncio
async def test_login():
    """Test login basic flow"""
    mock_context = MockContext()
    
    url = "https://example.com/login"
    username = "testuser"
    password = "testpass"
    
    mock_page = AsyncMock()
    mock_response = AsyncMock()
    mock_response.request.timing = {}
    mock_page.goto = AsyncMock(return_value=mock_response)
    
    mock_browser_context = AsyncMock()
    mock_browser_context.new_page = AsyncMock(return_value=mock_page)
    
    @mite_playwright
    async def dummy_journey(ctx):
        page = await ctx.browser.new_page()
        await ctx.browser.login(page, login_url=url, username=username, password=password)
    
    with patch('mite_playwright.playwright_runner.async_playwright') as mock_pw:
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        
        mock_pw.return_value.start = AsyncMock(return_value=mock_playwright)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_browser_context)
        
        await dummy_journey(mock_context)
        
        # Verify login called page methods
        assert mock_page.goto.called
        assert mock_page.fill.called
        assert mock_page.click.called