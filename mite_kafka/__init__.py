import asyncio
from contextlib import asynccontextmanager

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from functools import wraps


class KafkaProducer:

    def __init__(self, ctx):
        self._loop = asyncio.get_event_loop()
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

    async def stop(self):
        await self._producer.stop()


class KafkaConsumer:
    def __init__(self, ctx):
        self._loop = asyncio.get_event_loop()
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


class KafkaProducerSingleton(KafkaProducer):

    _instances = {}

    def __init__(self, context, producer_id=None):
        super().__init__(context)
        self._id = producer_id

    @classmethod
    async def get_instance(cls, context, singleton_id, *args, **kwargs):
        if singleton_id is None:
            singleton_id = "DEFAULT"
        if cls._instances.get(singleton_id, None) is None:
            cls._instances[f"{singleton_id}"] = cls(context, singleton_id)
            await cls._instances.get(singleton_id).create_and_start(*args, **kwargs)
        return cls._instances.get(singleton_id)

@asynccontextmanager
async def _kafka_context_manager(ctx):
    ctx.kafka_producer = KafkaProducer(ctx)
    ctx.kafka_consumer = KafkaConsumer(ctx)
    try:
        yield
    finally:
        del ctx.kafka_producer
        del ctx.kafka_consumer


@asynccontextmanager
async def _kafka_singleton_context_manager(ctx, singleton_id, producer, consumer, *args, **kwargs):
    if producer:
        ctx.kafka_producer = await KafkaProducerSingleton.get_instance(ctx, singleton_id, *args, **kwargs)
    if consumer:
        # TODO: Implement
        raise NotImplementedError
    yield

def mite_kafka(*args, singleton=False, singleton_id=None, producer=False, consumer=False, bootstrap_servers=None, security_protocol=None, ssl_context=None, value_serializer=None):
    def wrapper_factory(func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            kafka_args = {}
            if bootstrap_servers:
                kafka_args['bootstrap_servers'] = bootstrap_servers
            if security_protocol:
                kafka_args['security_protocol'] = security_protocol
            if ssl_context:
                kafka_args['ssl_context'] = ssl_context
            if value_serializer:
                kafka_args['value_serializer'] = value_serializer

            if singleton:    
                async with _kafka_singleton_context_manager(ctx, singleton_id=singleton_id, producer=producer, consumer=consumer, **kafka_args):
                    return await func(ctx, *args, **kwargs)
            else:
                async with _kafka_context_manager(ctx):
                    return await func(ctx, *args, **kwargs)

        return wrapper
    
    if len(args) == 0:
        # invoked as @mite_kafka(singleton=...) def foo(...)
        return wrapper_factory
    elif len(args) > 1:
        breakpoint()
        raise Exception("Anomalous invocation of mite_kafka decorator")
    else:
        # len(args) == 1; invoked as @mite_kafka def foo(...)
        return wrapper_factory(args[0])
