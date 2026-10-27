# WebSocket

`mite_websocket` is mite's WebSocket integration, built on
[websockets](https://websockets.readthedocs.io/). It installs a connection
helper onto the journey context; everything past that point is plain
`websockets`.

Install: `pip install mite[websocket]` (no functional change today. Every
mite install already includes it; this will matter starting in mite 3.0).

## Basic usage

```python
from mite_websocket import mite_websocket

@mite_websocket
async def journey(ctx):
    conn = await ctx.websocket.connect("ws://localhost:8765")
    await conn.send("hello")
    reply = await conn.recv()
    await ctx.websocket.close_connection(conn)
```

The `@mite_websocket` decorator installs `ctx.websocket` for the duration of
the journey call and closes every connection it opened before removing it
afterwards, even if the journey raises.

## `ctx.websocket` reference

- `connect(*args, **kwargs)` a thin wrapper around `websockets.connect`.
  Everything is passed straight through, so `websockets`'s own documentation
  applies. The returned connection is tracked internally so it can be cleaned
  up automatically.
- `close_connection(conn)` closes a specific connection and stops tracking
  it. Calling this yourself is optional; any connection still open when the
  journey returns is closed for you.
- `get_connections()` the list of connections opened via `connect` that
  haven't been closed yet.

Beyond `connect`/`close_connection`, use the connection object exactly as
`websockets` documents it (`send`, `recv`, async iteration, etc.). Mite does
not wrap anything else.

## Error handling

Any `websockets.exceptions.WebSocketException` raised while the decorator is
active is caught and re-raised as `mite_websocket.WebsocketError`, a
`mite.exceptions.MiteError`. Mite reports `MiteError` subclasses as journey
error metrics rather than letting them propagate, so a WebSocket failure
shows up the same way an HTTP or AMQP failure would.

## Metrics

`mite_websocket` emits no metrics of its own. There is no registered stats
processor and no automatic `ctx.send()` call anywhere in the package. If you
want WebSocket activity to show up in mite's stats, send your own messages
from the journey and register a stats processor to turn them into Prometheus
series. {doc}`../stats` walks through exactly this pattern.
</content>
