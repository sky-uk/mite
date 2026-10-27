# Selenium

`mite_selenium` is mite's Selenium WebDriver integration, for journeys that
need a real browser rather than the HTTP/HTML-scraping approach of
{doc}`browser`. It installs `ctx.browser`, a `SeleniumRemote` WebDriver
wrapper, onto the journey context and automatically reports page-load timing
metrics.

Install: `pip install mite[selenium]` (no functional change today, every
mite install already includes it; this will matter starting in mite 3.0).
`wire=True` support additionally needs `pip install mite[selenium_wire]`. See
the warning below before relying on it.

```{important}
**`wire=True` does not work on a stock install today.** `selenium-wire`
requires `blinker<1.9`, but mite's own `flask>=3.0` pin resolves to a
`blinker` version `selenium-wire` can't tolerate, and no `selenium-wire`
release since October 2022 fixes this. The conflict is detailed in a `FIXME`
comment at
[`mite_selenium/__init__.py`](https://github.com/sky-uk/mite/blob/master/mite_selenium/__init__.py),
next to where `wire=True` is handled. Check there for the current status
before relying on it. Plain `mite_selenium` (without `wire=True`) is
unaffected.
```

## Basic usage

```python
from mite_selenium import mite_selenium

@mite_selenium
async def journey(ctx):
    async with ctx.transaction("Load homepage"):
        ctx.browser.get("https://example.com")
    ctx.browser.wait_for_element(("css selector", "h1"))
```

The `@mite_selenium` decorator connects a remote WebDriver session (defaulting
to `http://127.0.0.1:4444/wd/hub`), installs it as `ctx.browser` for the
duration of the journey call, and quits the session afterwards.

```python
from mite_selenium import mite_selenium

@mite_selenium(wire=True)   # see the warning above
async def journey(ctx):
    ...
```

Calling it with `wire=True` uses `selenium-wire` instead of plain Selenium,
giving access to captured requests via `ctx.browser.requests` and
`ctx.browser.wait_for_request(url)`, at the cost of the limitation above.

## WebDriver configuration

All WebDriver setup is read from `ctx.config`, so it's configured the same
way as everything else in mite. See {doc}`../config`:

| Config key | Meaning |
|---|---|
| `webdriver_command_executor` | Remote WebDriver URL (default `http://127.0.0.1:4444/wd/hub`) |
| `webdriver_capabilities` | **Required.** A spec string (`module:attr`) pointing at the desired capabilities object |
| `webdriver_keep_alive` | passed through to `RemoteConnection` |
| `webdriver_file_detector`, `webdriver_proxy`, `webdriver_browser_profile`, `webdriver_options` | optional, each a spec string resolved via `spec_import` if set |

## `ctx.browser` reference

- `get(url)` navigates and automatically reports page-load metrics (see
  below).
- `wait_for_element(locator, timeout=5)` / `wait_for_elements(locator,
  timeout=5)` waits for an element (or elements) to appear, raising a
  `MiteError` on timeout instead of Selenium's own `TimeoutException`.
- `wait_for_url(url, timeout=5)` waits for the browser URL to match.
- `switch_to_iframe(locator)` / `switch_to_parent()` / `switch_to_default()`
  frame navigation helpers.
- `current_url` the browser's current URL.
- `get_js_metrics_context()` see Custom JS timing, below.

Anything else, use the underlying Selenium `WebDriver` API as upstream
documents it.

## Metrics emitted

Every `get()` call reports page-load metrics automatically: DNS lookup, TCP
connect, TLS handshake, time to first/last byte, DOM interactive, JS onload,
render time, time to interactive, page weight, and first paint / first
contentful paint, each exposed as a histogram
(`mite_selenium_page_load_<metric>_<unit>`), plus per-resource network timing
for every sub-resource the page loaded
(`mite_selenium_network_resource_<metric>_<unit>`, labelled by
`resource_path`). The full list is registered under `mite_stats` and listed
alongside every other processor on {doc}`../stats`.

```{note}
Not every browser reports every metric above. `_browser_has_timing_capabilities`
checks for the underlying `window.performance` API before attempting to read
it, so metrics are simply omitted rather than erroring on a browser that
doesn't support them.
```

## Custom JS timing

```python
async with ctx.browser.get_js_metrics_context():
    ...  # your own JS-triggered interaction
```

Wraps a block of journey code with `js_execution_time` reporting, read from
`performance.now()` before and after. Use this to time an interaction (e.g. a
single-page-app route change) that doesn't trigger a full page load and so
wouldn't otherwise be captured by `get()`'s automatic metrics.

## See also

- {doc}`browser` mite's lighter-weight HTTP/HTML-scraping alternative, for
  journeys that don't need a real browser engine or JavaScript execution
- {doc}`../stats` the full list of registered stats processors
</content>
