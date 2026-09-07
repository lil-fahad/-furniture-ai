class DomainError(Exception):
    def __init__(self, code: str, message: str, status: int = 422, retryable: bool = False):
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable
        super().__init__(message)


class LeaseLost(Exception):
    """The current worker may no longer commit or publish results."""
