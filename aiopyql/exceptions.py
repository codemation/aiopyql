class Error(Exception):
    pass
class InvalidInputError(Error):
    def __init__(self, invalid_input, message):
        self.invalid_input = invalid_input
        self.message = message
class InvalidColumnType(Error):
    def __init__(self, invalid_type, message):
        self.invalid_type = invalid_type
        self.message = message