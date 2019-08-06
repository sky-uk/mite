class SenderMock():
    def __init__(self):
        self.test_result = None

    def send(self, msg):
        self.test_result = msg
