from __future__ import annotations

from nats_contrib.micro.request import Request


class NoResponseError(Exception):
    """Raised when the response is not available.

    This exception is never raised during normal operation.

    It is only used during testing to detect when the response
    has not been set by the micro handler and test attempts to
    access the response data or headers.
    """


def make_request(
    subject: str,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> RequestStub:
    """Create a request for testing.

    Args:
        subject: The subject of the request.
        data: The data of the request.
        headers: The headers of the request.

    Returns:
        A request stub for testing.

    Note:
        A request stub can be used to call a micro handler directly
        during test and to check the response data and headers.
    """
    return RequestStub(subject, data, headers)


class RequestStub(Request):
    """A request stub for testing."""

    def __init__(
        self,
        subject: str,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        # Because this is a testing request, we don't care about some overhead
        # due to asserting types. We can just use isinstance() to check the types.
        # This will allow small mistakes in tests to be caught early.
        if not isinstance(subject, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"subject must be a string, not {type(subject).__name__}")
        if not isinstance(data, (bytes, type(None))):
            raise TypeError(f"data must be bytes, not {type(data).__name__}")
        if not isinstance(headers, (dict, type(None))):
            raise TypeError(f"headers must be a dict, not {type(headers).__name__}")
        self._subject = subject
        self._data = data or b""
        self._headers = headers or {}
        self._response_headers: dict[str, str] | None = None
        self._response_data: bytes | None = None

    def subject(self) -> str:
        """The subject on which request was received."""
        return self._subject

    def headers(self) -> dict[str, str]:
        """The headers of the request."""
        return self._headers

    def data(self) -> bytes:
        """The data of the request."""
        return self._data

    async def respond(self, data: bytes, headers: dict[str, str] | None = None) -> None:
        """Send a success response to the request.

        Args:
            data: The response data.
            headers: Additional response headers.
        """
        # Detect errors early during testing
        if not isinstance(data, bytes):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"data must be bytes, not {type(data).__name__}")
        if not isinstance(headers, (dict, type(None))):
            raise TypeError(f"headers must be a dict, not {type(headers).__name__}")
        # Save the response data and headers for testing
        # Make sure there cannot be a None value when method is called
        self._response_data = data
        self._response_headers = headers or {}

    def response_data(self) -> bytes:
        """Use this method durign tests to get the response data."""
        if self._response_data is None:
            raise NoResponseError("Response data is not available")
        return self._response_data

    def response_headers(self) -> dict[str, str]:
        """Use this method during tests to get the response headers."""
        if self._response_headers is None:
            raise NoResponseError("Response headers are not available")
        return self._response_headers
