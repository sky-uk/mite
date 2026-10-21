# Plugins

Mite ships a number of integration packages. Most follow the same shape: a
decorator that dependency-injects an API object onto the journey context, so a
journey can talk to a particular protocol or tool.

```{toctree}
:maxdepth: 1

playwright
finagle
db_datapool
acurl
```

```{note}
Not every mite package has a page here. `mite_http`, `mite_selenium`,
`mite_kafka`, `mite_amqp`, `mite_websocket` and `mite_browser` currently ship
without written documentation of their own — a known gap, rather than an
omission from the list above.

Three of them (`mite_http`, `mite_selenium` and `mite_kafka`) do register stats
processors, which are listed under {doc}`../stats`.

`acurl` is included above for convenience but is not a plugin: it is a separate
distribution that `mite_http` builds on. Its page explains the distinction.
```
