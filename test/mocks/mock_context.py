class MockContext:
    def __init__(self):
        self.messages = []

    async def send(self, message, **kwargs):
        self.messages.append((message, kwargs))

    @property
    def config(self):
        return {}

    @property
    def should_stop(self):
        return False

    def transaction(self):
        # TODO
        raise NotImplementedError
