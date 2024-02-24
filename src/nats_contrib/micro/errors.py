class ServiceError(Exception):
    """Raised when a service error is received."""

    def __init__(self, code: int, description: str) -> None:
        super().__init__(f"Service error {code}: {description}")
        self.code = code
        self.description = description
