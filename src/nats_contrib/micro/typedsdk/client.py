from __future__ import annotations

from typing import Generic

from nats.aio.client import Client as NatsClient

from ..client.client import Client as MicroClient
from ..client.client import ServiceError
from .endpoint import E, EndpointRequest, ParamsT, R, T
from .type_adapter import TypeAdapter, TypeAdapterFactory, default_type_adapter


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
        request: EndpointRequest[ParamsT, T, R, E],
        data: ReplyData | None,
        error: ServiceError | None,
        data_type_adapter: TypeAdapter[R],
        error_type_adapter: TypeAdapter[E],
    ) -> None:
        if data is None and error is None:
            raise ValueError("data and error cannot be both None")
        self.request = request
        self._data = data
        self._error = error
        self._data_type_adapter = data_type_adapter
        self._error_type_adapter = error_type_adapter

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
        return self._data_type_adapter.decode(self._data.data)

    def error(self) -> E:
        """Get the error."""
        if self._data:
            raise ValueError("No error")
        assert self._error
        return self._error_type_adapter.decode(self._error.data)


class Client:
    def __init__(
        self,
        client: NatsClient,
        type_adapter: TypeAdapterFactory | None = None,
    ) -> None:
        self._client = MicroClient(client)
        self._type_adapter = type_adapter or default_type_adapter()

    async def send(
        self,
        request: EndpointRequest[ParamsT, T, R, E],
        headers: dict[str, str] | None = None,
        timeout: float = 1,
    ) -> Reply[ParamsT, T, R, E]:
        """Send a request."""
        data = self._type_adapter(request.request_type).encode(request.request)
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
                self._type_adapter(request.response_type),
                self._type_adapter(request.error_type),
            )
        return Reply(
            request,
            ReplyData(response.data, response.headers or {}),
            None,
            self._type_adapter(request.response_type),
            self._type_adapter(request.error_type),
        )
