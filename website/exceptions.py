class ValidationError(Exception):
    pass

    @property
    def message(self):
        return self.args[0]
