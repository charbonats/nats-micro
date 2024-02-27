from __future__ import annotations


class ServiceError(Exception):
    """Raised when a service error is received."""

    def __init__(
        self,
        code: int,
        description: str,
        subject: str,
        data: bytes,
        headers: dict[str, str],
    ) -> None:
        super().__init__(f"Service error {code}: {description}")
        self.code = code
        self.description = description
        self.subject = subject
        self.data = data
        self.headers = headers
