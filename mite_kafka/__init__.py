import asyncio
import threading
from contextlib import asynccontextmanager
from functools import wraps

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer


class KafkaProducer:
    def __init__(self, ctx):
        self._producer = None
        self._context = ctx

    async def create_and_start(self, *args, **kwargs):
        self._producer = AIOKafkaProducer(*args, **kwargs)
        await self._producer.start()

    async def send_and_wait(self, topic, key=None, value=None, **kwargs):
        await self._producer.send_and_wait(topic, key=key, value=value, **kwargs)
        self._context.send(
            "kafka_producer_stats",
            topic=topic,
            key=key,
        )

    @asynccontextmanager
    async def transaction(self, message):
        async with self._context.transaction(message):
            yield

    async def stop(self):
        await self._producer.stop()


class KafkaConsumer:
    def __init__(self, ctx):
        self._consumer = None
        self._topics = None
        self._context = ctx

    async def create_and_start(self, *topics, **kwargs):
        self._consumer = AIOKafkaConsumer(*topics, **kwargs)
        self._topics = topics
        await self._consumer.start()

    async def get_messages(self):
        async for message in self._consumer:
            self._context.send(
                "kafka_consumer_stats",
                topic=self._topics,
                partition=message.partition,
                offset=message.offset,
            )
            yield message

    async def stop(self):
        await self._consumer.stop()


@asynccontextmanager
async def _kafka_context_manager(ctx):
    ctx.kafka_producer = KafkaProducer(ctx)
    ctx.kafka_consumer = KafkaConsumer(ctx)
    try:
        yield
    finally:
        del ctx.kafka_producer
        del ctx.kafka_consumer


def mite_kafka(func):
    async def wrapper(ctx, *args, **kwargs):
        async with _kafka_context_manager(ctx):
            return await func(ctx, *args, **kwargs)

    return wrapper


class KafkaAdapterManager:
    _producers = {}
    _lock = threading.Lock()

    @classmethod
    async def get_producer(
        cls, context, bootstrap_servers, adapter_id=None, *args, **kwargs
    ):
        if adapter_id is None:
            adapter_id = "DEFAULT"
        if cls._producers.get(adapter_id, None) is None:
            with cls._lock:
                if cls._producers.get(adapter_id, None) is None:
                    cls._producers[f"{adapter_id}"] = KafkaProducer(context)
                    await cls._producers.get(adapter_id).create_and_start(
                        bootstrap_servers=bootstrap_servers, *args, **kwargs
                    )
        return cls._producers.get(adapter_id)


@asynccontextmanager
async def _kafka_managed_adapter_context_manager(
    ctx,
    bootstrap_servers,
    only_consumer=False,
    only_producer=False,
    adapter_id=None,
    *args,
    **kwargs,
):
    if adapter_id:
        ctx_producer_key = f"kafka_producer_{adapter_id}"
    else:
        ctx_producer_key = "kafka_producer"
    if only_producer:
        producer = await KafkaAdapterManager.get_producer(
            ctx, bootstrap_servers, *args, **kwargs
        )
        setattr(ctx, ctx_producer_key, producer)
    elif only_consumer:
        # TODO: Implement consumer
        raise Exception("only_consumer not yet implemented")
    else:
        producer = await KafkaAdapterManager.get_producer(
            ctx, bootstrap_servers, *args, **kwargs
        )
        setattr(ctx, ctx_producer_key, producer)
        # TODO: Add consumer once implemented
    yield


def mite_kafka_managed_adapter(
    *args,
    bootstrap_servers,
    only_consumer=False,
    only_producer=False,
    security_protocol=None,
    ssl_context=None,
    value_serializer=None,
    adapter_id=None,
):
    if only_consumer:
        raise Exception("only_consumer not yet implemented")
    if only_consumer and only_producer:
        raise Exception("Cannot specify both only_consumer and only_producer")
    if security_protocol is None:
        security_protocol = "PLAINTEXT"

    def wrapper_factory(func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            async with _kafka_managed_adapter_context_manager(
                ctx,
                bootstrap_servers=bootstrap_servers,
                only_consumer=only_consumer,
                only_producer=only_producer,
                security_protocol=security_protocol,
                ssl_context=ssl_context,
                value_serializer=value_serializer,
                adapter_id=adapter_id,
            ):
                return await func(ctx, *args, **kwargs)

        return wrapper

    if len(args) == 0:
        # invoked as @mite_kafka_managed_producer(producer_id=...) def foo(...)
        return wrapper_factory
    elif len(args) > 1:
        raise Exception("Anomalous invocation of mite_kafka_managed_producer decorator")
    else:
        # len(args) == 1; invoked as @mite_kafka_managed_producer def foo(...)
        return wrapper_factory(args[0])
