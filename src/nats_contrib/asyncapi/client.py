from __future__ import annotations

import abc
from typing import Generic

from .operation import E, OperationRequest, ParamsT, R, T


class OperationError(Exception):
    """Request error."""

    def __init__(self, code: int, description: str) -> None:
        self.description = description
        self.code = code


class Reply(Generic[ParamsT, T, R, E]):
    """Reply to a request."""

    def __init__(
        self,
        request: OperationRequest[ParamsT, T, R, E],
        data: bytes | None,
        headers: dict[str, str] | None,
        error: OperationError | None,
    ) -> None:
        if data is None and error is None:
            raise ValueError("data and error cannot be both None")
        if data is not None and error is not None:
            raise ValueError("data and error cannot be both set")
        self.request = request
        self._data = data
        self._headers = headers or {}
        self._error = error

    def raise_on_error(self) -> None:
        """Check if the reply is an error."""
        if self._error is not None:
            raise self._error

    def headers(self) -> dict[str, str]:
        """Get the headers."""
        return self._headers

    def data(self) -> R:
        """Get the data."""
        if self._error:
            raise self._error
        assert self._data
        return self.request.spec.response.type_adapter.decode(self._data)

    def error(self) -> E:
        """Get the error."""
        if not self._error:
            raise ValueError("No error")
        assert self._data
        return self.request.spec.error.type_adapter.decode(self._data)


class Client(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    async def send(
        self,
        request: OperationRequest[ParamsT, T, R, E],
        headers: dict[str, str] | None = None,
        timeout: float = 1,
    ) -> Reply[ParamsT, T, R, E]:
        """Send a request."""
