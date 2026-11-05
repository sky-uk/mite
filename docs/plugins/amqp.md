# AMQP

`mite_amqp` is mite's AMQP integration, built on
[aio_pika](https://docs.aio-pika.com/). It installs a connection helper onto
the journey context; everything past that point is plain `aio_pika`.

```{note}
The integrations the team actively uses and supports are listed on the
{doc}`front page <../index>`: Kafka, HTTP and InfluxDB. AMQP is not currently
one of them, but it remains available, documented, and open to
contributions — if you rely on it or want to improve it, it's a good
candidate.
```

Install: `pip install mite[amqp]`

## Basic usage

```python
from mite_amqp import mite_amqp

@mite_amqp
async def journey(ctx):
    connection = await ctx.amqp.connect_robust("amqp://guest:guest@localhost/")
    async with connection:
        channel = await connection.channel()
        await channel.default_exchange.publish(
            ctx.amqp.message(b"hello"),
            routing_key="my_queue",
        )
```

The `@mite_amqp` decorator installs `ctx.amqp` for the duration of the journey
call and removes it afterwards.

## `ctx.amqp` reference

- `connect(*args, **kwargs)` / `connect_robust(*args, **kwargs)` — thin
  wrappers around `aio_pika.connect` / `aio_pika.connect_robust`. They inject
  the running event loop as the `loop` keyword automatically; everything else
  is passed straight through, so `aio_pika`'s own documentation applies.
- `message(body, **kwargs)` — builds an `aio_pika.Message`. A `str` body is
  encoded as UTF-8 first; `bytes` is passed through unchanged.

Beyond these three methods, use the connection, channel and queue objects
exactly as `aio_pika` documents them — mite does not wrap anything else.

## Error handling

Any `aio_pika.AMQPException` raised while the decorator is active is caught
and re-raised as `mite_amqp.AMQPError`, a `mite.exceptions.MiteError`. Mite
reports `MiteError` subclasses as journey error metrics rather than letting
them propagate, so an AMQP failure shows up the same way an HTTP or Selenium
failure would.

## Metrics

`mite_amqp` emits no metrics of its own — there is no registered stats
processor and no automatic `ctx.send()` call anywhere in the package. If you
want AMQP activity to show up in mite's stats, send your own messages from the
journey and register a stats processor to turn them into Prometheus series.
{doc}`../stats` walks through exactly this: its worked example is a custom
`_MITE_STATS` list for `amqp_tx_stats` / `amqp_rx_stats` messages, built
against an external AMQP integration — the pattern applies directly here.
