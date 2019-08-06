import zmq

from .utils import pack_msg, unpack_msg
import asyncio
import logging

logger = logging.getLogger(__name__)


class Duplicator:
    def __init__(self, in_address, out_addresses, loop=None):
        self._zmq_context = zmq.Context()
        self._in_socket = self._zmq_context.socket(zmq.PULL)
        self._in_socket.bind(in_address)
        self._out_sockets = [(i, self._zmq_context.socket(zmq.PUSH)) for i in out_addresses]
        for address, socket in self._out_sockets:
            socket.bind(address)
        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop

    async def run(self, stop_func=None):
        return await self._loop.run_in_executor(None, self._run, stop_func)

    def _run(self, stop_func=None):
        while stop_func is None or not stop_func():
            msg = self._in_socket.recv()
            for address, socket in self._out_sockets:
                try:
                    socket.send(msg, flags=zmq.NOBLOCK)
                except zmq.ZMQError:
                    logger.error("Duplicator message buffer full for address %s" % (address,))


class Sender:
    def __init__(self):
        self._zmq_context = zmq.Context()
        self._socket = self._zmq_context.socket(zmq.PUSH)

    def bind(self, address):
        self._socket.bind(address)
        logger.debug("sender bound to address: %s", address)

    def connect(self, address):
        self._socket.connect(address)
        logger.debug("sender connected to address: %s", address)

    def send(self, msg):
        self._socket.send(pack_msg(msg), flags=zmq.NOBLOCK)


class Receiver:
    def __init__(self, listeners=None, raw_listeners=None, loop=None):
        self._zmq_context = zmq.Context()
        self._socket = self._zmq_context.socket(zmq.PULL)
        if listeners is None:
            listeners = []
        self._listeners = listeners
        if raw_listeners is None:
            raw_listeners = []
        self._raw_listeners = raw_listeners
        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop

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

    def _recv(self):
        return self._socket.recv()

    async def run(self, stop_func=None):
        return await self._loop.run_in_executor(None, self._run, stop_func)

    def _run(self, stop_func=None):
        while stop_func is None or not stop_func():
            raw = self._recv()
            for raw_listener in self._raw_listeners:
                raw_listener(raw)
            msg = unpack_msg(raw)
            for listener in self._listeners:
                listener(msg)


_MSG_TYPE_HELLO = 1
_MSG_TYPE_REQUEST_WORK = 2
_MSG_TYPE_BYE = 3


class RunnerTransport:
    def __init__(self, socket_address, loop=None):
        self._zmq_context = zmq.Context()
        self._sock = self._zmq_context.socket(zmq.REQ)
        self._sock.connect(socket_address)
        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop

    def _hello(self):
        self._sock.send(pack_msg((_MSG_TYPE_HELLO, None)))
        return unpack_msg(self._sock.recv())

    async def hello(self):
        return await self._loop.run_in_executor(None, self._hello)

    def _request_work(self, runner_id, current_work, completed_data_ids, max_work):
        self._sock.send(pack_msg((_MSG_TYPE_REQUEST_WORK, [runner_id, current_work, completed_data_ids, max_work])))
        msg = self._sock.recv()
        result = unpack_msg(msg)
        return result

    async def request_work(self, runner_id, current_work, completed_data_ids, max_work):
        logger.debug(
            "Requesting work runner_id=%s current_work=%s completed_data_ids=%s max_work=%s" % (
                runner_id, current_work, completed_data_ids, max_work))
        return await self._loop.run_in_executor(None, self._request_work, runner_id, current_work,
                                                completed_data_ids, max_work)

    def _bye(self, runner_id):
        self._sock.send(pack_msg((_MSG_TYPE_BYE, runner_id)))
        return unpack_msg(self._sock.recv())

    async def bye(self, runner_id):
        logger.debug("Saying bye")
        return await self._loop.run_in_executor(None, self._bye, runner_id)


class ControllerServer:
    def __init__(self, socket_address, loop=None):
        self._zmq_context = zmq.Context()
        self._sock = self._zmq_context.socket(zmq.REP)
        self._sock.bind(socket_address)
        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop

    async def run(self, controller, stop_func=None):
        return await self._loop.run_in_executor(None, self._run, controller, stop_func)

    def _run(self, controller, stop_func=None):
        while stop_func is None or not stop_func():
            _type, content = unpack_msg(self._sock.recv())
            if _type == _MSG_TYPE_HELLO:
                self._sock.send(pack_msg(controller.hello()))
            elif _type == _MSG_TYPE_REQUEST_WORK:
                self._sock.send(pack_msg(controller.request_work(*content)))
            elif _type == _MSG_TYPE_BYE:
                self._sock.send(pack_msg(controller.bye(content)))
