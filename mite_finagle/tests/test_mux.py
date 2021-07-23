from io import BytesIO

import hypothesis.strategies as st
from hypothesis import example, given
from pytest import mark, raises

from mite_finagle.mux import CanTinit, Dict, Dispatch, Init, Message, Ping, String


class TestUtils:
    def test_read_pascal_string(self):
        s = BytesIO(b"\x03foo")
        assert String(1).read(s) == b"foo"

    def test_read_pascal_string_extra_data(self):
        s = BytesIO(b"\x03foobar")
        assert String(1).read(s) == b"foo"

    def test_read_pascal_string_throws_if_too_short(self):
        s = BytesIO(b"\x03fo")
        with raises(ValueError, match="string read too short"):
            String(1).read(s)

    def test_read_dict(self):
        s = BytesIO(b"\x02\x03foo\x03bar\x03baz\x04quux")
        assert Dict(1, 1).read(s) == {b"foo": b"bar", b"baz": b"quux"}

    def test_read_dict_extra_data(self):
        s = BytesIO(b"\x02\x03foo\x03bar\x03baz\x04quuxasdf")
        assert Dict(1, 1).read(s) == {b"foo": b"bar", b"baz": b"quux"}

    def test_read_dict_throws_if_not_enough_keys(self):
        s = BytesIO(b"\x02\x03foo\x03bar")
        with raises(ValueError, match="couldn't read dict"):
            Dict(1, 1).read(s)

    def test_serialize_pascal_string(self):
        assert String(2).serialize(b"foobar") == b"\x00\x06foobar"

    def test_serialize_dict(self):
        assert (
            Dict(2, 2).serialize({b"foo": b"bar", b"baz": b"quux"})
            == b"\x00\x02\x00\x03foo\x00\x03bar\x00\x03baz\x00\x04quux"
        )

    @given(st.integers(1, 4), st.dictionaries(st.binary(), st.binary()))
    @example(1, {})
    def test_read_dict_roundtrip(self, nlength, d):
        desc = Dict(nlength, nlength)
        s = desc.serialize(d)
        assert desc.read(BytesIO(s)) == d

    @given(st.integers(1, 4), st.binary())
    def test_read_pascal_string_round_trip(self, nlength, s):
        desc = String(nlength)
        ss = desc.serialize(s)
        assert desc.read(BytesIO(ss)) == s


class TestMessages:
    @mark.parametrize(
        "msg_type,args",
        (
            (Init, (1, {})),
            (Ping, ()),
            (CanTinit, (b"tinit check",)),
            (Dispatch.Reply, (0, {b"foo": b"bar"}, b"quux")),
            (Dispatch, ({b"foo": b"bar"}, b"quux", {b"foo": b"bar"}, b"corge")),
        ),
    )
    def test_roundtrip(self, msg_type, args):
        m = msg_type(1, *args)
        s = BytesIO(m.to_bytes())
        assert isinstance(Message.read_from_stream(s), msg_type)

    @mark.parametrize(
        "msg,b",
        (
            (Init(1, 1, {}), b"\x00\x00\x00\x06D\x00\x00\x01\x00\x01"),
            (Ping(1), b"\x00\x00\x00\x04A\x00\x00\x01"),
            (CanTinit(1, b"tinit check"), b"\x00\x00\x00\x0f\x7f\x00\x00\x01tinit check"),
            (
                Dispatch(1, {b"foo": b"bar"}, b"quux", {b"foo": b"bar"}, b"corge"),
                b"\x00\x00\x00'\x02\x00\x00\x01\x00\x01\x00\x03foo\x00\x03bar\x00\x04quux\x00\x01\x00\x03foo\x00\x03barcorge",
            ),
            (
                Dispatch.Reply(1, 0, {b"foo": b"bar"}, b"quux"),
                b"\x00\x00\x00\x15\xfe\x00\x00\x01\x00\x00\x01\x00\x03foo\x00\x03barquux",
            ),
        ),
    )
    def test_serialize(self, msg, b):
        assert msg.to_bytes() == b

    @mark.parametrize(
        "msg,b",
        (
            (Init(1, 1, {}), b"\x00\x00\x00\x06D\x00\x00\x01\x00\x01"),
            (Ping(1), b"\x00\x00\x00\x04A\x00\x00\x01"),
            (CanTinit(1, b"tinit check"), b"\x00\x00\x00\x0f\x7f\x00\x00\x01tinit check"),
            (
                Dispatch(1, {b"foo": b"bar"}, b"quux", {b"foo": b"bar"}, b"corge"),
                b"\x00\x00\x00'\x02\x00\x00\x01\x00\x01\x00\x03foo\x00\x03bar\x00\x04quux\x00\x01\x00\x03foo\x00\x03barcorge",
            ),
            (
                Dispatch.Reply(1, 0, {b"foo": b"bar"}, b"quux"),
                b"\x00\x00\x00\x15\xfe\x00\x00\x01\x00\x00\x01\x00\x03foo\x00\x03barquux",
            ),
        ),
    )
    def test_deserialize(self, msg, b):
        assert Message.read_from_stream(BytesIO(b)) == msg

    @mark.parametrize(
        "f",
        (
            lambda: Init(1, 1, {}),
            lambda: Ping(1),
            lambda: CanTinit(1, b"tinit check"),
            lambda: Dispatch(1, {b"foo": b"bar"}, b"quux", {b"foo": b"bar"}, b"corge"),
            lambda: Dispatch.Reply(1, 0, {b"foo": b"bar"}, b"quux"),
        ),
    )
    def test_eq(self, f):
        assert f() == f()

    @mark.parametrize("t", (Init, Ping, Dispatch))
    def test_reply_types(self, t):
        assert t.type > 0
        assert t.type == -t.Reply.type

    def test_cantinit_reply_type(self):
        assert CanTinit.type == 127
        assert CanTinit.Reply.type == -128
