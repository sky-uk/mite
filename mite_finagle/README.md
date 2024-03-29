# Finagle load injection for mite

This module contains the infrastructure for injecting load into finagle
services with mite.  Specifically, it implements the thrift binary RPC
format wrapped in finagleʼs mux framing protocol.  In order to use it
you must install mite with the `finagle` extra:
```
cd /path/to/mite
pip install ".[finagle]"
```

## Design

Unlike http which might be the paradigm of performance testing you are
most familiar with, finagle is an explicitly pipelined protocol.  It
would not be a realistic simulation of app behavior to open a new
connection for each finagle request.  So, we expose the finagle
connection explicitly as an (async) context manager:

```
from mite_finagle import mite_finagle

@mite_finagle
async def my_journey(ctx):
    async with ctx.finagle.connect("hostname", port=1234) as finagle:
        ...
```

(As is usual in mite, the `@mite_finagle` decorator dependency-injects a
finagle API object onto the first argument to the function which is a
context object)

Within the body of the context manager, the connection object has a few
methods available on it:

- `send`: sends as message to the finagle server.  It expects a message
  factory (see below) as well as `args` and `kwargs` to pass to the
  factory.  It accepts an additional kwarg `mux_context` which is a
  dictionary with `bytes` keys and values that represents the context
  passed with the finagle call.  (The context functions similarly to
  headers in an http request).  The send method does not wait for the
  reply.  It is designed to operate with the `replies` method.
- `send_and_wait`: sends the message, then waits for and returns the
  reply
- `replies`: an async generator that yields, in sequence, the reply
  objects received on the finagle connection.

The way this is designed to be used is to pre-seed a specific number of
messages (the desired tps) onto the finagle connection.  Then wait for
the replies, using the `chained_wait` functionality to wait the
appropriate amount of time (one second) before putting another message
into flight to maintain the tps.  You can think of this a bit like
juggling: there are always a certain number of balls in the air, and
when we “catch” a reply we need to (at the appropriate rate) “throw”
another message into the air:

```
for _ in range(desired_tps):
    finagle.send(factory, ...)
async for reply in finagle.replies():
    reply.chained_wait(1)
    finagle.send(factory, ...)
```

### Reply objects

The reply object is a thrift code-generated object.  In addition, it is
monkeypatched by mite_finagle with a `chained_wait` method.  The purpose
of this is to enable waiting for a specific period of time, starting
from when a message was sent (and not when the reply was received).
This allows controlling the rate of message injection.

Itʼs not the only possible method of rate control – we could use a
token bucket in concurrent processes for send+receive.  But a choice had
to be made.  Itʼs also worth noting that this implementation has
co-evolved with our finagle codebase which contains mostly methods that
return objects (or void) – itʼs likely that this doesnʼt work correctly
for methods that return non-objects (incl void, int, things like that).

### Message factories

The message factory abstraction encapsulates the knowledge that mite
needs about the thrift-level objects involved in making a finagle call:
the type of the request arguments and the return value.  It is
instantiated with two arguments: a method name and an autogenerated
thrift `Client` class which contains the code for invoking that method:

```
from my_module.MyService import Client

msg_factory = ThriftMessageFactory("my_method", Client)
```

Once the message factory is instantiated, it can be passed as an
argument to the `send` function (see above).  It has the below methods,
but itʼs unlikely (at the present point in time/design space) that mite
tests will need to invoke them for any reason:

- `get_(request|reply)_object`: convert from bytes into the
  request/reply to the factoryʼs method
- `get_(request|reply)_bytes`: get the serialization of a request/reply
  to the factoryʼs function.
- `get_reply_args`: get a kwargs dict of dummy values appropriate for
  passing to `get_reply_bytes` (useful for writing thrift stubs).

FIXME: the `get` verb in the above method names is heavily overloaded;
we probably want to do some renaming.

### Mux protocol code

This code includes an impementation of the finagle Mux binary protocol,
which is documented
[here](https://github.com/twitter/finagle/blob/91ff887d297f5d7b46dfec703fa6486a45b18b9b/finagle-mux/src/main/scala/com/twitter/finagle/mux/package.scala#).
(See also:
[1](https://github.com/twitter/finagle/blob/91ff887d297f5d7b46dfec703fa6486a45b18b9b/finagle-mux/src/main/scala/com/twitter/finagle/mux/transport/Message.scala#L47)
about the message type constants,
[2](https://github.com/twitter/finagle/blob/25878bda54de2d59ac11549a709e4cb1488f3d37/finagle-mux/src/main/scala/com/twitter/finagle/mux/pushsession/MuxServerNegotiator.scala#L70)
about the slightly odd version negotiation handshake)
There are three parts to this implementation:
1. General serialization utility classes, which are responsible for
   reading integers, bytestrings, dictionaries, etc from a stream of
   bytes according to the mux protocol, and serializing them back out
   again.
2. The `Message` class (and associated metaclass) which implements the
   (de)serialization of complete mux messages
3. Classes for each specific message type

These work together to allow a succinct description of the message
structure.  Here is an example message definition for a specific kind of
control message (used during version negotiation):

```
class CanTinit(Message):
    type = 127

    class Fields:
        message: Body()

    class Reply(Message):
        type = -128

    def args_for_reply(self):
        return {"message": b"tinit check"}
```

This says:
- the type constant of this message is 127
- the message has one field, a bytestring (“body”)
- the reply has a non-default type of -128 (usually the type of the
  reply is the negation of the type of the original message, and this is
  what is generated if the reply type is omitted)
- the reply implicitly has the same fields as the original message (but
  these can be overridden if desired)
- when constructing a reply to a message received, the `message` will be
  set to “tinit check” (a magic protocol constant).

## Testing

There are unit tests in the `tests/` directory.  In addition, there are
integration tests (well, “test” singular, so far...) in the
`test_integration.py` file.  The `foo_service` directory is generated
from the `foo_service.thrift` file using the command in a comment at the
top of the latter file.  The tests are plumbed into the mite test suite,
or you can run them with `pytest -- mite_finagle/tests` from the repo root.

## TODOs / future extension

### Implicit connection cache

(an idea that just occurred to me while writing these docs, sigh)

One thing we could do, rather than exposing the finagle connection in
the way that this code does, is to enable an implicit process-level
connection pool.  Then we could write the finagle journeys just like we
write the http ones, but get the desired connection reuse behavior that
we want to simulate the finagle protocol.

### Better/more complete integration suite

What it says in the title

### Better unit test coverage

What it says in the title

### Performance tests/characterization of the finagle code

What it says in the title

### Finish the reply object implemetation

The reply yielding code works OK when the reply is a thrift object and
(I hope – test this) `void`.  What is missing is:
- tests for the handling of int, list, etc return
- `chained_wait` for non-object returns

### Smarter handling of method arguments

Currently if we have a thrift method that takes lots of custom types in
its arguments, we need to import all those from the thrift generated
code, and construct them ourselves.  Do we want to implement some sort
of clever coercion so that dicts (etc) can be transformed into the right
objects?  We have all the info we need to do this; itʼs just not plumbed
up (and idk if tiʼs a good idea or not).
