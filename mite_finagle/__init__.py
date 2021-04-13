import asyncio
import time
from itertools import count

from .mux import CanTinit, Dispatch, Init, Message, Ping


class FinagleMessage:
    async def wait(self, seconds):
        if (sent_time := getattr(self, "_sent_time")) is None:
            raise Exception("message hasn't been sent")
        to_sleep = seconds - (time.time() - sent_time)
        if to_sleep > 0:
            await asyncio.sleep(to_sleep)
        else:
            # FIXME: log a warning
            pass


class MiteFinagle:
    def __init__(self, address, port):
        self._address = address
        self._port = port
        self._replies = asyncio.Queue()
        self._tags = count(1)
        # FIXME: some sort of length limit to keep this from leaking...?
        self._in_flight = {}

    async def __aenter__(self):
        self._reader, self._writer = await asyncio.open_connection(
            self._address, self._port
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # FIXME: handle errors
        # Do we need to clean up the reader...?
        self._writer.close()
        await self._writer.wait_closed()

    async def replies(self):
        while True:
            done, pending = await asyncio.wait(
                (self._main_loop(), self._replies.get()),
                return_when=asyncio.FIRST_COMPLETED,
            )
            yield done[0].result()

    async def send(self, message):
        mux_msg = Dispatch({}, "foo", message.to_bytes())
        mux_msg.tag = next(self._tags)  # FIXME: ugly
        self._in_flight[mux_msg.tag] = message
        self._writer.write(mux_msg.to_bytes())
        await self._writer.drain()

    async def send_and_wait(self, message):
        await self.send(message)
        return await self._main_loop(return_msg=message)

    async def _main_loop(self, return_msg=None):
        while True:
            message = await Message.read_from_async_stream(self.reader)
            if message.type in (Ping.type, Init.type, CanTinit.type):
                self._writer.write(message.reply())
                await self._writer.drain()
            elif message.type == Dispatch.reply_type:
                if (mite_msg := self._in_flight.pop(message.tag, None)) is None:
                    raise Exception("unknown reply tag received")
                mite_msg.reply = message._body  # FIXME: private property...
                if return_msg is not None and mite_msg is return_msg:
                    return mite_msg
                await self._replies.put(mite_msg)
            else:
                breakpoint()
                raise Exception("unknown type")
