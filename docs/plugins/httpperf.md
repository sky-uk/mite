# httpperf

[httpperf](https://github.com/tonysimpson/httpperf) is an asyncio HTTP client
for load testing, built on [libcurl](https://curl.se/libcurl/). It is what
`mite_http` uses underneath to make HTTP calls.

```{note}
Unlike the other pages in this section, httpperf is **not** a mite plugin. It is
a separate distribution, maintained upstream and published to PyPI as
`httpperf`, and it registers no `mite_stats` entry point.

httpperf grew out of the original acurl. Mite previously vendored its own Cython
fork of acurl, published to PyPI as `acurl` (up to 1.2.1). That fork has been
retired; `mite_http` translates the few places where its API differed (see
{doc}`http`).
```

**Full documentation:**
[httpperf README](https://github.com/tonysimpson/httpperf/blob/main/README.md) and
[connections guide](https://github.com/tonysimpson/httpperf/blob/main/docs/connections.md),
covering sessions, engines, connection and TLS reuse, and timings.

To install mite with httpperf, use the `http` extra:

```bash
pip install mite[http]
```

The Linux wheels on PyPI bundle their own libcurl, built with HTTP/2 and
HTTP/3, so no system libcurl is needed.
