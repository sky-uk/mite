# Plugins

Mite ships a number of integration packages. Most follow the same shape: a
decorator that dependency-injects an API object onto the journey context, so a
journey can talk to a particular protocol or tool.

```{toctree}
:maxdepth: 1

http
kafka
playwright
finagle
db_datapool
amqp
websocket
browser
selenium
acurl
```

```{note}
`acurl` is included above for convenience but is not a plugin: it is a
separate distribution that `mite_http` builds on. Its page explains the
distinction.

`wire=True` support for `mite_selenium` does not currently work on a stock
install — see {doc}`selenium` before relying on it.

Having a page here says nothing about whether a package is actively
supported. See the module support note on the
{doc}`front page <../index>` for which integrations the team actively
maintains.
```

```{note}
If a plugin's third-party dependency isn't installed, importing the plugin
raises Python's own bare `ModuleNotFoundError` naming the missing package,
rather than a custom message pointing at the extra to install. This is true
at import time for every integration package. One runtime exception: passing
`wire=True` to `mite_selenium` raises a custom error naming the
`selenium_wire` extra.
```
