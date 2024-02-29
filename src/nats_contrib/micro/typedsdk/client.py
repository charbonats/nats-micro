from __future__ import annotations

from typing import Generic

from nats.aio.client import Client as NatsClient

from ..client.client import Client as MicroClient
from ..client.client import ServiceError
from .endpoint import E, ParamsT, R, RequestToSend, T


class RequestError(Exception):
    """Request error."""

    def __init__(self, message: str, code: int) -> None:
        self.message = message
        self.code = code


class ReplyData:
    __slots__ = ["data", "headers"]

    def __init__(self, data: bytes, headers: dict[str, str]) -> None:
        self.data = data
        self.headers = headers


class Reply(Generic[ParamsT, T, R, E]):
    """Reply to a request."""

    def __init__(
        self,
        request: RequestToSend[ParamsT, T, R, E],
        data: ReplyData | None,
        error: ServiceError | None,
    ) -> None:
        if data is None and error is None:
            raise ValueError("data and error cannot be both None")
        self.request = request
        self._data = data
        self._error = error

    def raise_on_error(self) -> None:
        """Check if the reply is an error."""
        if self._error is not None:
            raise self._error

    def headers(self) -> dict[str, str]:
        """Get the headers."""
        if self._data:
            return self._data.headers
        assert self._error
        return self._error.headers

    def data(self) -> R:
        """Get the data."""
        if self._error:
            raise self._error
        assert self._data
        return self.request.spec.response.type_adapter.decode(self._data.data)

    def error(self) -> E:
        """Get the error."""
        if self._data:
            raise ValueError("No error")
        assert self._error
        return self.request.spec.error.type_adapter.decode(self._error.data)


class Client:
    def __init__(
        self,
        client: NatsClient,
    ) -> None:
        self._client = MicroClient(client)

    async def send(
        self,
        request: RequestToSend[ParamsT, T, R, E],
        headers: dict[str, str] | None = None,
        timeout: float = 1,
    ) -> Reply[ParamsT, T, R, E]:
        """Send a request."""
        data = request.spec.request.type_adapter.encode(request.request)
        try:
            response = await self._client.request(
                request.subject,
                data,
                headers=headers,
                timeout=timeout,
            )
        except ServiceError as e:
            return Reply(
                request,
                None,
                e,
            )
        return Reply(
            request,
            ReplyData(response.data, response.headers or {}),
            None,
        )
