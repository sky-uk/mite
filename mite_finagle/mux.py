import enum
import typing
from io import BytesIO

# Binary serialization utilities


class Int:
    """An integer encoded in `length` bytes, optionally signed."""

    def __init__(self, length, signed=False):
        self._length = length
        self._signed = signed

    def read(self, input):
        int_bytes = input.read(self._length)
        if len(int_bytes) != self._length:
            raise ValueError("integer not fully read")
        return int.from_bytes(int_bytes, "big", signed=self._signed)

    def serialize(self, value):
        return value.to_bytes(self._length, "big", signed=self._signed)


class String:
    """A string, prefixed with its length packed into `len_bytes` bytes."""

    def __init__(self, len_bytes):
        self._length = Int(len_bytes)

    def read(self, input):
        length = self._length.read(input)
        r = input.read(length)
        if len(r) != length:
            raise ValueError("string read too short")
        return r

    def serialize(self, s):
        return self._length.serialize(len(s)) + s


class RestString:
    """A string, occupying the rest of the message."""

    def read(self, input):
        return input.read()

    def serialize(self, s):
        return s


class Dict:
    """A dictionary.

    The number of keys is first, packed into `len_bytes`.  Then each key and
    value follows, each encoded as a string prefixed with its length in
    `strlen_bytes`.

    """

    def __init__(self, len_bytes, strlen_bytes):
        self._length = Int(len_bytes)
        self._string = String(strlen_bytes)

    def read(self, input):
        d = {}
        try:
            nkey = self._length.read(input)
            while nkey > 0:
                key = self._string.read(input)
                value = self._string.read(input)
                d[key] = value
                nkey -= 1
            return d
        except ValueError as e:
            raise ValueError("couldn't read dict") from e

    def serialize(self, d):
        return self._length.serialize(len(d)) + b"".join(
            self._string.serialize(k) + self._string.serialize(v) for k, v in d.items()
        )


class RestDict:
    """A dictionary encoded without length.

    The difference with the `Dict` class is: that class's encoding begins with
    a length specifying the number of kv pairs in the dictionary.  This class
    on the other hand does not specify a length, and consumes kv pairs until
    the input is exhausted.

    """

    def __init__(self, strlen_bytes):
        self._string = String(strlen_bytes)

    def read(self, input):
        d = {}
        remaining = len(input.getbuffer())  # FIXME: dangerous, can we validate it?
        while input.tell() < remaining:
            k = self._string.read(input)
            v = self._string.read(input)
            d[k] = v
        return d

    def serialize(self, d):
        return b"".join(
            self._string.serialize(k) + self._string.serialize(v) for k, v in d.items()
        )


class Body:
    """A message body.

    Read and written without length, padding, etc. because it consumes the
    rest of the message tile the end.

    """

    def read(self, input):
        return input.read()

    def serialize(self, value):
        return value


# General message class


class _MessageMeta(type):
    # FIXME @cached_property
    @property
    def _TYPES(cls):
        r = {}
        for x in cls.__subclasses__():
            r[x.type] = x
            if (reply_cls := getattr(x, "Reply", None)) is not None:
                r[-x.type] = reply_cls
        r[-62] = Discarded  # Exceptionally
        return r

    def __new__(cls, name, bases, namespace):
        if name == "Message":
            # Bail out early for the base class
            return type.__new__(cls, name, bases, namespace)

        if name != "Reply":
            # Processing for top level messages
            if "Reply" not in namespace:
                # Add reply class to top level messages that lack it
                class Reply(Message):
                    type = -namespace["type"]
                    Fields = namespace["Fields"]

                namespace["Reply"] = Reply
            else:
                # Reply explicitly present -- make sure it's a Message.
                if namespace["Reply"].__bases__[0] is not Message:
                    raise ValueError("Found Reply class not derived from Message")
                # And copy type and Fields onto it if missing.
                if "type" not in namespace["Reply"].__dict__:
                    namespace["Reply"].type = -namespace["type"]
                if "Fields" not in namespace["Reply"].__dict__:
                    namespace["Reply"].Fields = namespace["Fields"]
        return type.__new__(cls, name, bases, namespace)


class Message(metaclass=_MessageMeta):
    """Represents a Mux message

    There are a few members that are special on subclasses:
    - `type`: an integer indicating the message type.
    - `Fields`: a class whose members are annotated with data-descriptor
      classes from above.  The ordering in the source determines the ordering
      in which they will be serialized.
    - `Reply`: a `Message` subclass that indicates the structure of the reply
      to a message.  Within a `Reply`:
      - if `type` is not given it defaults to the negation of the parent message
        type
      - if `Fields` is not given it defaults to the value of `Fields` for the
        parent message
    - `args_for_reply`: a function that should return a dict giving the
      keyword arguments to pass in when constructing a reply.  This function
      itself can pass arguments, which will be passed through from the
      `make_reply` function.

    The class has initializer and equality methods predefined, as well as
    `to_bytes` and `from_bytes` for (de)serialization,
    `read_from_(async_)stream` for generating messages from I/O streams, and
    `make_reply` for constructing replies to messages.

    """

    def __init__(self, tag, *args, **kwargs):
        self.tag = tag
        field_names = [name for name, _ in self._fields() if name not in kwargs]
        assert len(field_names) == len(args)
        kwargs.update(dict(zip(field_names, args)))
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def _fields(cls):
        """Get the dynamically defined fields for this class.

        Much of the behavior of Message subclasses depends in one way or
        another on this.

        """
        for name, descriptor in typing.get_type_hints(cls.Fields).items():
            if not name.startswith("_"):
                yield name, descriptor

    def __eq__(self, other):
        """Two instances are equal if they are the same type and all fields are equal."""
        return type(self) is type(other) and all(
            getattr(self, name) == getattr(other, name) for name, _ in self._fields()
        )

    def to_bytes(self):
        """Serialize to bytes."""
        payload = b"".join(
            (
                descriptor.serialize(getattr(self, name))
                for name, descriptor in self._fields()
            )
        )
        return b"".join(
            (
                Int(4).serialize(len(payload) + 4),
                Int(1, signed=True).serialize(self.type),
                Int(3).serialize(self.tag),
                payload,
            )
        )

    @classmethod
    def from_bytes(cls, msg):
        """Deserialize from bytes."""
        # print("from_bytes", msg)
        stream = BytesIO(msg)
        type = Int(1, signed=True).read(stream)
        tag = Int(3).read(stream)
        subclass = cls._TYPES[type]
        kwargs = {
            name: descriptor.read(stream) for name, descriptor in subclass._fields()
        }
        kwargs["tag"] = tag
        if (extra := stream.read()) != b"":
            raise ValueError("extra bytes in message", type, subclass, kwargs, extra, msg)
        return subclass(**kwargs)

    @classmethod
    def read_from_stream(cls, stream):
        """Read from a synchronous I/O stream.

        This needs to be distinct from `from_bytes` in order to properly read
        out a single message framed by length (and no more or less) from the
        stream.

        """
        size = Int(4).read(stream)
        msg = stream.read(size)
        return cls.from_bytes(msg)

    @classmethod
    async def read_from_async_stream(cls, stream):
        """Read from an async I/O stream."""
        size_bytes = await stream.readexactly(4)
        size = int.from_bytes(size_bytes, "big")
        msg = await stream.readexactly(size)
        return cls.from_bytes(msg)

    def make_reply(self, *args, **kwargs):
        """Construct a reply to a message object.

        The arguments to pass to this function will depend on the type of
        message you are replying to.

        """
        return self.Reply(self.tag, **self.args_for_reply(*args, **kwargs))


# Specific messages


class Ping(Message):
    """A mux ping, to check if the connection is alive.

    Can be sent by either side of the connection.

    """

    type = 65

    class Fields:
        pass


class Init(Message):
    """An initialization message.

    Sent from client to server on connection establishment.

    """

    type = 68

    class Fields:
        version: Int(2)
        kwargs: RestDict(4)

    def args_for_reply(self):
        return {"version": 1, "kwargs": {}}


class CanTinit(Message):
    """A special message type used in protocol version negotiation."""

    type = 127

    class Fields:
        message: Body()

    class Reply(Message):
        type = -128

    def args_for_reply(self):
        return {"message": b"tinit check"}


class DispatchStatus(enum.IntEnum):
    """Status codes for a Mux RPC call."""

    OK = 0
    ERROR = 1
    NACK = 2


class Dispatch(Message):
    """A RPC procedure call message.

    It contains a context (dictionary of headers), a destination string, a
    dictionary of delegations (some sort of source-routing construct...) and a
    bytestring body (which will be a thrift RPC message).  In practice, the
    destinationa nd delegations are empty for our use cases.

    """

    type = 2

    class Fields:
        context: Dict(2, 2)
        destination: String(2)
        delegations: Dict(2, 2)
        body: Body()

    class Reply(Message):
        class Fields:
            status: Int(1)
            context: Dict(2, 2)
            body: Body()

    def args_for_reply(self, body, status=DispatchStatus.OK):
        return {"status": status, "context": self.context, "body": body}


class Discarded(Message):
    """A message that the protocol explicitly says we should discard.

    Who even knows why it exists but I'm sure there is a reason.

    """

    type = 66

    class Fields:
        discard_tag: Int(3)
        why: RestString()


class Lease(Message):
    """A control message.

    Doesn't mean anything to us and doesn't need a reply; we just need to
    know how to deserialize it so it doesn't confuse us when we se eit on the
    wire.

    """

    type = 67

    class Fields:
        unit: Int(1)
        howmuch: Int(8)
