# Record and replay a browser journey

You can turn a journey you click through in Chrome into a mite test
without writing Python. You record the journey, convert it with
`mite har`, set any credentials, and run it.

## 1. Record

1. Open Chrome DevTools (F12) and select the **Network** tab.
2. Select **Preserve log**. Set the filter to **All**, not Fetch/XHR, so
   page loads are recorded too.
3. Click through the journey you want to test.
4. Right-click the request list and choose **Save all as HAR (sanitized)**.

A HAR file holds everything the browser sent, including tokens and email
addresses. Don't commit or share it.

## 2. Convert

Run the converter without `--host` first. It writes nothing and lists the
hosts in the recording, with request counts:

```console
$ mite har journey.har my_journey.py
No --host given; nothing written.

Hosts in journey.har (request counts, 61 static assets not counted):
     27  api.shop.example
      3  www.shop.example
     13  cdn.consent-vendor.example
      ...
```

Then convert again, keeping only the hosts you own and want to test. You
can repeat `--host`, and `*` matches any part of a name:

```console
$ mite har journey.har my_journey.py --host=api.shop.example --host=www.shop.example
Wrote 30 requests to my_journey.py
```

The converter drops requests to all other hosts, such as analytics,
consent banners, chat widgets and monitoring endpoints. The converter also drops static assets (images, CSS,
JS, fonts) and CORS preflights. Add `--include-static` to keep the static
assets.

| Option | Default | What it does |
|---|---|---|
| `--host=HOST` | required | Keep requests to this host. Repeatable; `*.shop.example` and `host:8000` work. |
| `--include-static` | off | Also keep static assets and CORS preflights on the kept hosts. |
| `--sleep-time=SECONDS` | `1` | Time from the start of one request to the start of the next. `0` uses the gaps from the recording. |

## 3. Set credentials

The converter removes values that look like credentials or personal data:
tokens, `Authorization` headers, passwords and email addresses. Each one
becomes a config key, which the top of the generated file lists:

```python
# Values that looked like credentials or personal data were removed
# from the recording. Set them before running:
#   export MITE_CONF_email=...
#   export MITE_CONF_x_api_token=...
```

Set them as environment variables. Any other way of supplying mite
config works too (see {doc}`config`). A journey that runs without a key it
needs stops with `Missing config 'x_api_token': set MITE_CONF_x_api_token`.

The application issues some tokens during the journey, for example at
login. For now, set these as config too.

The converter does not copy cookies from the recording. The browser session keeps the
cookies the server sets while the journey runs.

## 4. Run

From the directory that holds `my_journey.py`, run the journey once to
check it works:

```console
mite journey test my_journey:journey
```

A request that gets a different status code from the recording fails the
journey with an `UnexpectedResponseCodeError`, which names the URL. A
recorded `304 Not Modified` accepts either 200 or 304.

To run it under load, edit the two settings at the top of the file:

```python
TARGET_TPS = 1  # requests per second across all running journeys
DURATION_S = 300
```

Then run the scenario:

```console
mite scenario test my_journey:scenario
```

The scenario works out how many journeys to run at once from
`TARGET_TPS` and two numbers measured from the recording:

- `REQUESTS_PER_JOURNEY`: requests in one run
- `SECONDS_PER_JOURNEY`: minimum time one run takes

For example, 30 requests with the default 1-second spacing take 30
seconds, so each running journey makes about 1 request per second. A
`TARGET_TPS` of 50 then runs 50 journeys at once. If the server is slower
than the spacing, each journey takes longer and the real rate is lower.
For other load shapes, see {doc}`volume-model`.

## What the generated file looks like

`test/har/sample.har` and its converted output,
`test/har/sample_journey.py`, in the mite repository are a complete
example. A request looks like this:

```python
    async with ensure_fixed_separation(1.0):
        async with ctx.transaction('Page 1 | POST shop.example/api/login'):
            resp = await ctx.browser.post(
                'https://shop.example/api/login',
                headers={
                    'content-type': 'application/json',
                },
                data='{"email":"' + _config(ctx, 'email') + '","password":"' + _config(ctx, 'password') + '"}',
            )
            check_status_code(resp, 200)
```

- Requests are grouped under the page they were recorded on.
- Transaction names leave out the query string, so repeated calls
  aggregate in dashboards.
- The journey sends each request body exactly as recorded, with config
  values in place of the removed values.
