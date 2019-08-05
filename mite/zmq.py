import zmq.asyncio as zmq
import zmq as zmq_constants

from .utils import pack_msg, unpack_msg
import logging

logger = logging.getLogger(__name__)


class Duplicator:
    def __init__(self, in_address, out_addresses, loop=None):
        self._zmq_context = zmq.Context()
        self._in_socket = self._zmq_context.socket(zmq_constants.PULL)
        self._in_socket.bind(in_address)
        self._out_sockets = [
            (i, self._zmq_context.socket(zmq_constants.PUSH)) for i in out_addresses
        ]
        for address, socket in self._out_sockets:
            socket.bind(address)

    async def run(self, stop_func=None):
        while stop_func is None or not stop_func():
            msg = await self._in_socket.recv()
            for address, socket in self._out_sockets:
                try:
                    await socket.send(msg, flags=zmq_constants.NOBLOCK)
                except zmq_constants.ZMQError:
                    logger.error(
                        "Duplicator message buffer full for address %s" % (address,)
                    )


class Sender:
    def __init__(self):
        self._zmq_context = zmq.Context()
        self._socket = self._zmq_context.socket(zmq_constants.PUSH)

    def bind(self, address):
        self._socket.bind(address)
        logger.debug("sender bound to address: %s", address)

    def connect(self, address):
        self._socket.connect(address)
        logger.debug("sender connected to address: %s", address)

    async def send(self, msg):
        try:
            await self._socket.send(pack_msg(msg), flags=zmq_constants.NOBLOCK)
        except zmq_constants.ZMQError as e:
            logging.error(f"ZMQ errno {e.errno}; {e.strerror}")


class Receiver:
    def __init__(self, listeners=None, raw_listeners=None, loop=None):
        self._zmq_context = zmq.Context()
        self._socket = self._zmq_context.socket(zmq_constants.PULL)
        if listeners is None:
            listeners = []
        self._listeners = listeners
        if raw_listeners is None:
            raw_listeners = []
        self._raw_listeners = raw_listeners

    def bind(self, address):
        self._socket.bind(address)
        logger.debug("receiver bound to address: %s", address)

    def connect(self, address):
        self._socket.connect(address)
        logger.debug("receiver connected to address: %s", address)

    def add_listener(self, listener):
        self._listeners.append(listener)

    def add_raw_listener(self, listener):
        self._raw_listeners.append(listener)

    async def run(self, stop_func=None):
        while stop_func is None or not stop_func():
            raw = await self._socket.recv()
            for raw_listener in self._raw_listeners:
                raw_listener(raw)
            msg = unpack_msg(raw)
            for listener in self._listeners:
                listener(msg)


_MSG_TYPE_HELLO = 1
_MSG_TYPE_REQUEST_WORK = 2
_MSG_TYPE_BYE = 3


class RunnerTransport:
    def __init__(self, socket_address):
        self._zmq_context = zmq.Context()
        self._sock = self._zmq_context.socket(zmq_constants.REQ)
        self._sock.connect(socket_address)

    async def hello(self):
        await self._sock.send(pack_msg((_MSG_TYPE_HELLO, None)))
        return unpack_msg(await self._sock.recv())

    async def request_work(self, runner_id, current_work, completed_data_ids, max_work):
        logger.debug(
            "Requesting work runner_id=%s current_work=%s completed_data_ids=%s max_work=%s"
            % (runner_id, current_work, completed_data_ids, max_work)
        )
        await self._sock.send(
            pack_msg(
                (
                    _MSG_TYPE_REQUEST_WORK,
                    [runner_id, current_work, completed_data_ids, max_work],
                )
            )
        )
        msg = unpack_msg(await self._sock.recv())
        return msg

    async def bye(self, runner_id):
        logger.debug("Saying bye")
        await self._sock.send(pack_msg((_MSG_TYPE_BYE, runner_id)))
        return unpack_msg(await self._sock.recv())


class ControllerServer:
    def __init__(self, socket_address):
        self._zmq_context = zmq.Context()
        self._sock = self._zmq_context.socket(zmq_constants.REP)
        self._sock.bind(socket_address)

    async def run(self, controller, stop_func=None):
        while stop_func is None or not stop_func():
            _type, content = unpack_msg(await self._sock.recv())
            if _type == _MSG_TYPE_HELLO:
                await self._sock.send(pack_msg(controller.hello()))
            elif _type == _MSG_TYPE_REQUEST_WORK:
                await self._sock.send(pack_msg(controller.request_work(*content)))
            elif _type == _MSG_TYPE_BYE:
                await self._sock.send(pack_msg(controller.bye(content)))
