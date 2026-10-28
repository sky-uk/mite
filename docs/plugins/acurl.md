# acurl

acurl is an asynchronous wrapper around [libcurl](https://curl.se/libcurl/),
built to interface with the uvloop python library. It is what `mite_http` uses
underneath to make HTTP calls.

```{note}
Unlike the other pages in this section, acurl is **not** a mite plugin. It is a
separate distribution, published to PyPI in its own right, and it registers no
`mite_stats` entry point. There is no `mite_acurl` package.

Because its `README.md` is also its PyPI description, that file is the canonical
documentation and is deliberately not duplicated here.
```

**Full documentation:**
[acurl/README.md](https://github.com/sky-uk/mite/blob/master/acurl/README.md)

It covers how mite obtains a `CurlWrapper`, and architectural notes on the
`curl_multi` integration (`handle_socket` and `start_timer`).

To install mite with acurl, use the `http` extra:

```bash
pip install mite[http]
```
