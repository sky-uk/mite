class SenderMock():
    def __init__(self):
        self.test_result = None

    async def send(self, msg):
        self.test_result = msg
