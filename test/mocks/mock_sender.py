class SenderMock:
    def __init__(self):
        self.messages = []

    def send(self, msg):
        self.messages.append(msg)
