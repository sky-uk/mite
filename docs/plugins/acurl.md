# acurl

acurl is an asyncio HTTP client for load testing, built on
[libcurl](https://curl.se/libcurl/). It is what `mite_http` uses underneath to
make HTTP calls.

```{note}
Unlike the other pages in this section, acurl is **not** a mite plugin. It is a
separate distribution, maintained upstream at
[tonysimpson/acurl](https://github.com/tonysimpson/acurl), and it registers no
`mite_stats` entry point. There is no `mite_acurl` package.

Mite previously vendored its own Cython fork of acurl, published to PyPI as
`acurl` (up to 1.2.1). That fork has been retired in favour of upstream.
```

<!-- TODO: add the upstream PyPI distribution name once it is published. -->

**Full documentation:**
[acurl README](https://github.com/tonysimpson/acurl/blob/main/README.md) and
[connections guide](https://github.com/tonysimpson/acurl/blob/main/docs/connections.md),
covering sessions, engines, connection and TLS reuse, and timings.

To install mite with acurl, use the `http` extra:

```bash
pip install mite[http]
```

```{warning}
Upstream acurl and the old fork both install the `acurl` import package. If the
old fork is installed, uninstall it before upgrading mite:

    pip uninstall -y acurl
```
