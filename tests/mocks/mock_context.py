class MockContext:
    def __init__(self):
        self.messages = []
        self.config = {}

    def send(self, message, **kwargs):
        self.messages.append((message, kwargs))

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, value):
        self._config = value

    @property
    def should_stop(self):
        return False

    def transaction(self):
        # TODO
        raise NotImplementedError
