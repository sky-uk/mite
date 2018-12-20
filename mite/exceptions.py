

class MiteError(Exception):
    def __init__(self, message, **fields):
        super().__init__(message)
        self.fields = fields
