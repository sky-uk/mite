from mite import ensure_fixed_separation
from mite_browser import browser_decorator
from mite_http.checks import check_status_code


@browser_decorator()
async def journey(ctx):
    async with ensure_fixed_separation(1.25):
        async with ctx.transaction('Request get https://shop.example/'):
            resp = await ctx.browser.get(
                'https://shop.example/',
                headers={'accept': 'text/html', 'user-agent': 'Mozilla/5.0'},
            )
            check_status_code(resp, 200)

    async with ensure_fixed_separation(0.75):
        async with ctx.transaction('Request post https://shop.example/api/items'):
            resp = await ctx.browser.post(
                'https://shop.example/api/items',
                headers={'content-type': 'application/json'},
                data='{"name":"café","n":1}',
            )
            check_status_code(resp, 201)

    async with ensure_fixed_separation(1.5):
        async with ctx.transaction('Request put https://shop.example/api/items/1'):
            resp = await ctx.browser.put(
                'https://shop.example/api/items/1',
                headers={'content-type': 'application/x-www-form-urlencoded'},
                data='name=tea&n=2',
            )
            check_status_code(resp, 200)

    async with ensure_fixed_separation(0.5):
        async with ctx.transaction('Request get https://shop.example/old'):
            resp = await ctx.browser.get(
                'https://shop.example/old',
                headers={},
            )
            check_status_code(resp, 200)

    async with ensure_fixed_separation(0.5):
        async with ctx.transaction('Request get https://shop.example/logo.png'):
            resp = await ctx.browser.get(
                'https://shop.example/logo.png',
                headers={},
            )
            check_status_code(resp, (200, 304))

    async with ensure_fixed_separation(0.5):
        async with ctx.transaction('Request delete https://shop.example/api/items/1'):
            resp = await ctx.browser.delete(
                'https://shop.example/api/items/1',
                headers={},
            )
            check_status_code(resp, 204)

    async with ensure_fixed_separation(0):
        async with ctx.transaction('Request head https://shop.example/health'):
            resp = await ctx.browser.head(
                'https://shop.example/health',
                headers={},
            )
            check_status_code(resp, 200)
