from __future__ import annotations

from typing import Any

from .message import Message
from .types import E, ParamsT, R, T


class NoResponseError(Exception):
    """Raised when the response is not available.

    This exception is never raised during normal operation.

    It is only used during testing to detect when the response
    has not been set by the micro handler and test attempts to
    access the response data or headers.
    """


class StubMessage(Message[ParamsT, T, R, E]):
    """A message received as a request."""

    def __init__(
        self,
        params: ParamsT,
        data: T,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._params = params
        self._data = data
        self._headers = headers or {}
        self._response_headers: dict[str, str] = ...
        self._response_data: R = ...
        self._response_error: E = ...
        self._response_error_code: int = ...
        self._response_error_description: str = ...

    def params(self) -> ParamsT:
        return self._params

    def payload(self) -> T:
        return self._data

    def headers(self) -> dict[str, str]:
        return self._headers

    async def respond(
        self, data: Any = None, *, headers: dict[str, str] | None = None
    ) -> None:
        self._response_headers = headers or {}
        self._response_data = data

    async def respond_error(
        self,
        code: int,
        description: str,
        *,
        data: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._response_headers = headers or {}
        self._response_error = data
        self._response_error_code = code
        self._response_error_description = description

    def response_data(self) -> R:
        """Use this method durign tests to get the response data."""
        if self._response_data is ...:
            raise NoResponseError("No response has been set")
        return self._response_data

    def response_error(self) -> E:
        """Use this method during tests to get the response error."""
        if self._response_error is ...:
            raise NoResponseError("No response has been set")
        return self._response_error

    def response_error_code(self) -> int:
        """Use this method during tests to get the response error code."""
        if self._response_error_code is ...:
            raise NoResponseError("No response has been set")
        return self._response_error_code

    def response_error_description(self) -> str:
        """Use this method during tests to get the response error description."""
        if self._response_error_description is ...:
            raise NoResponseError("No response has been set")
        return self._response_error_description

    def response_headers(self) -> dict[str, str]:
        """Use this method during tests to get the response headers."""
        if self._response_headers is ...:
            raise NoResponseError("No response has been set")
        return self._response_headers
