# Browser

`mite_browser` is mite's HTML-scraping integration, built on `mite_http` and
[BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/). Despite the
name, it does not drive a real browser engine,there is no JavaScript
execution or rendering. It parses HTML responses and gives journeys a
page/form/link API on top of plain HTTP requests, which is enough to script
form submissions and link navigation without hand-rolling HTML parsing in
every journey.

Install: `pip install mite[browser]` (depends on `http`; no functional change
today. Every mite install already includes it; this will matter starting in
mite 3.0).

## Basic usage

```python
from mite_browser import browser_decorator

@browser_decorator()
async def journey(ctx):
    async with ctx.transaction("Load homepage"):
        page = await ctx.browser.get("https://example.com")
    page.assert_element_in(name="h1", text="Welcome")
```

`browser_decorator()` wraps `@mite_http` and installs `ctx.browser`, a
`Browser` instance built on top of `ctx.http`, for the duration of the
journey call. It accepts two optional arguments:

- `separation` passed to `mite.ensure_fixed_separation`, for pacing
  requests within the journey.
- `embedded_resources` if `True`, every page fetched also downloads its
  embedded resources (images, scripts, stylesheets, iframes) recursively.
  This better simulates a real browser's network footprint, at the cost of
  extra requests per page.

## The `Browser` object

`ctx.browser` exposes one async method per HTTP verb used for page
navigation (`get`, `post`, `options`, `patch`) each returning a `Page`.
Anything else, use `ctx.browser.request(method, url, ...)` directly. Cookie
helpers (`erase_all_cookies`, `erase_session_cookies`, `get_cookie_list`) are
also available, forwarding to the underlying `ctx.http` session.

## The `Page` object

A `Page` wraps an HTML response and lazily parses it with BeautifulSoup the
first time you touch `.dom`, `.find()`, or `.find_all()`:

```python
page = await ctx.browser.get("https://example.com")
page.find("a", text="Sign in")
page.find_all("div", {"class": "product"})
```

- `assert_element_in(name=..., attrs=..., text=...)` raises
  `ElementNotFoundError` if nothing matches; useful as a lightweight
  assertion that a page loaded correctly.
- `click_link(text)` finds an `<a>` by its visible text and follows it via
  `ctx.browser.get`.
- `get_form(name=None)` / `get_forms()` see Forms, below.
- `xhr_request(method, url, ...)` / `xhr_post(url, ...)` issues a request
  with `X-Requested-With: XMLHttpRequest` and a `Referer` set to the current
  page's URL, for simulating an AJAX call made from the page.

If `embedded_resources=True` was passed to the decorator, a page's `.scripts`,
`.stylesheets`, `.resources` and `.frames` lists are populated with the
downloaded sub-resources; otherwise they stay empty.

## Forms

```python
form = page.get_form()          # first form on the page
form = page.get_form(name="login")
form["username"] = "test"
form["password"] = "hunter2"
result_page = await form.submit()
```

`Form` behaves like a dict of its fields (`select`, `textarea`, and `input`
elements, with radio groups collapsed into a single field by name).
Assigning to a field name sets its value; assigning to a name that doesn't
exist creates one, so you can inject values a form doesn't declare.
`submit()` sends the form using its declared `method` and `action`.

```{important}
File upload fields are parsed but not actually submitted: `Form._serialize`
only encodes the non-file fields, with a `TODO` in source noting file
support depends on the underlying HTTP backend (`acurl`) supporting
multipart uploads, which it does not today. A form with a file input submits
successfully, just without the file.
```

## Metrics

`mite_browser` emits no metrics of its own. It has no registered stats
processor. Every request it makes goes through `ctx.http`, so the metrics
that show up are `mite_http`'s (see {doc}`http`), not anything
browser-specific.

## See also

- {doc}`http` the HTTP integration `mite_browser` is built on
</content>
