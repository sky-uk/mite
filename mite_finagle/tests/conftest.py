import asyncio

import pytest


class SocketFixture:
    def __init__(self, close=False):  # false for debugging...
        self._responses = []
        self._close = close
        self._received = []

    def add_response(self, response_bytes, after=None):
        self._responses.append((after, response_bytes))

    async def serve(self, port):
        await asyncio.start_server(self._connected, host="127.0.0.1", port=port)

    async def _connected(self, reader, writer):
        while True:
            try:
                to_read, resp = self._responses.pop(0)
            except IndexError:
                if self._close:
                    writer.close()
                    await writer.wait_closed()
                    break
                else:
                    to_read = None
            if to_read is None:
                # for debugging
                while True:
                    r = await reader.read(1)
                    if len(r) == 0:
                        print("eof")
                        return
                    print(r)

            print("reading", to_read)
            read_bytes = await reader.read(to_read)
            self._received.append(read_bytes)
            writer.write(resp)
            await writer.drain()

    def assert_received(self, messages):
        assert self._received == messages


@pytest.fixture
def sock_server():
    return SocketFixture()
