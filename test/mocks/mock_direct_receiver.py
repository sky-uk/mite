from mite.utils import pack_msg


class DirectReceiverMock:
    def __init__(self):
        self._listeners = []
        self._raw_listeners = []

    def __call__(self, msg):
        return

    def add_listener(self, listener):
        self._listeners.append(listener)

    def add_raw_listener(self, raw_listener):
        self._raw_listeners.append(raw_listener)

    def recieve(self, msg):
        for listener in self._listeners:
            listener(msg)
        packed_msg = pack_msg(msg)
        for raw_listener in self._raw_listeners:
            raw_listener(packed_msg)
