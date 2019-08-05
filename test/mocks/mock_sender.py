class SenderMock:
    def __init__(self):
        self.messages = []

    async def send(self, msg):
        self.messages.append(msg)
