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
acurl
```

```{note}
Not every mite package has a page here. `mite_selenium`, `mite_websocket` and
`mite_browser` currently ship without written documentation of their own — a
known gap, rather than an omission from the list above.

Having no page says nothing about whether a package is supported: `mite_selenium`
is listed as a registered stats processor under {doc}`../stats` despite having
no page here. See the module support note on the
{doc}`front page <../index>` for which integrations the team actively
maintains.

`acurl` is included above for convenience but is not a plugin: it is a separate
distribution that `mite_http` builds on. Its page explains the distinction.
```

```{note}
If a plugin's third-party dependency isn't installed, importing the plugin
raises Python's own bare `ModuleNotFoundError` naming the missing package,
rather than a custom message pointing at the extra to install. This is true
at import time for every integration package. One runtime exception: passing
`wire=True` to `mite_selenium` raises a custom error naming the
`selenium_wire` extra.
```
