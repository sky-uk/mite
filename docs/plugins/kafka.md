# Kafka

`mite_kafka` is mite's Kafka integration, built on
[aiokafka](https://aiokafka.readthedocs.io/). It installs a producer and a
consumer onto the journey context and reports metrics for both.

Install: `pip install mite[kafka]` (no functional change today — every mite
install already includes it; this will matter starting in mite 3.0).

## Basic usage

```python
from mite_kafka import mite_kafka

@mite_kafka
async def journey(ctx):
    async with ctx.transaction("Produce a message"):
        await ctx.kafka_producer.create_and_start(bootstrap_servers="localhost:9092")
        await ctx.kafka_producer.send_and_wait("my-topic", value=b"hello")
        await ctx.kafka_producer.stop()
```

`@mite_kafka` installs `ctx.kafka_producer` and `ctx.kafka_consumer` for the
duration of the journey call, then removes both attributes afterwards.
Neither is started automatically — the decorator attaches the wrapper
objects, but it's the journey's job to call `create_and_start(...)` and
`stop()` on whichever one it uses, same as it would with a plain `aiokafka`
client.

## Producer

`ctx.kafka_producer` wraps `aiokafka.AIOKafkaProducer`:

- `create_and_start(*args, **kwargs)` — forwards everything to
  `AIOKafkaProducer(...)` and starts it. `bootstrap_servers` is the one
  argument you'll always need.
- `send_and_wait(topic, key=None, value=None, **kwargs)` — sends a message
  and reports it (see Metrics, below). Other keyword arguments are passed
  straight to `aiokafka`'s `send_and_wait`.
- `transaction(message)` — an async context manager around
  `ctx.transaction(message)`, for naming the surrounding mite transaction.
  This names a mite transaction; it is not Kafka's own transactional
  producer API.
- `stop()` — stops the underlying `AIOKafkaProducer`.

## Consumer

`ctx.kafka_consumer` wraps `aiokafka.AIOKafkaConsumer`:

- `create_and_start(*topics, **kwargs)` — forwards everything to
  `AIOKafkaConsumer(*topics, ...)` and starts it.
- `get_messages()` — an async generator. Each message consumed is reported
  (see Metrics, below), then yielded to the caller.
- `stop()` — stops the underlying `AIOKafkaConsumer`.

```python
@mite_kafka
async def journey(ctx):
    await ctx.kafka_consumer.create_and_start("my-topic", bootstrap_servers="localhost:9092")
    async for message in ctx.kafka_consumer.get_messages():
        ...
    await ctx.kafka_consumer.stop()
```

## Metrics emitted

- Every `send_and_wait` call sends a `kafka_producer_stats` message with
  `topic` and `key`.
- Every message yielded by `get_messages` sends a `kafka_consumer_stats`
  message with `topic`, `partition` and `offset` — though only `topic` and
  `partition` are used as labels on the registered stat (below); `offset`
  is sent but not currently turned into a metric.

These are registered as `mite_kafka_producer_stats_counter` (labelled by
`topic`, `key`) and `mite_kafka_consumer_stats_counter` (labelled by `topic`,
`partition`), listed alongside every other processor on {doc}`../stats`.

## Managed adapter (shared producer)

For journeys that would otherwise create a new producer per call,
`mite_kafka_managed_adapter` keeps a single producer alive across calls
instead:

```python
from mite_kafka import mite_kafka_managed_adapter

@mite_kafka_managed_adapter(bootstrap_servers="localhost:9092", only_producer=True)
async def journey(ctx):
    await ctx.kafka_producer.send_and_wait("my-topic", value=b"hello")
```

`bootstrap_servers` is required; `adapter_id` lets you keep more than one
such producer, installed at `ctx.kafka_producer` (or
`ctx.kafka_producer_<adapter_id>` if `adapter_id` is given). The producer
itself is a process-wide singleton, created once per `adapter_id` and reused
by every journey that asks for it — it is not stopped when the journey
function returns, since it's meant to outlive any single call.

```{important}
As the name suggests, only the producer side is currently implemented.
Passing `only_consumer=True` raises immediately, and the default call (with
neither `only_producer` nor `only_consumer` set) only sets up a producer too
— despite the parameter existing, there is no managed consumer today. Use
the plain `@mite_kafka` decorator above if you need a consumer.
```
