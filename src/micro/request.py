from __future__ import annotations
from dataclasses import dataclass

from typing import Awaitable, Callable
from typing_extensions import TypeAlias

from nats.aio.msg import Msg

import abc


Handler: TypeAlias = Callable[["Request"], Awaitable[None]]
"""Handler is a function that processes a micro request."""


class Request(metaclass=abc.ABCMeta):
    """Request is the interface for a request received by a service.

    An interface is used instead of a class to allow for different implementations.
    It makes it easy to test a service by using a stub implementation of Request.

    Four methods must be implemented:
    - `def subject() -> str`: the subject on which the request was received.
    - `def headers() -> dict[str, str]`: the headers of the request.
    - `def data() -> bytes`: the data of the request.
    - `async def respond(...) -> None`: send a response to the request.
    """

    @abc.abstractmethod
    def subject(self) -> str:
        """The subject on which request was received."""
        raise NotImplementedError()

    @abc.abstractmethod
    def headers(self) -> dict[str, str]:
        """The headers of the request."""
        raise NotImplementedError()

    @abc.abstractmethod
    def data(self) -> bytes:
        """The data of the request."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def respond(self, data: bytes, headers: dict[str, str] | None = None) -> None:
        """Send a success response to the request.

        Args:
            data: The response data.
            headers: Additional response headers.
        """
        raise NotImplementedError()

    async def respond_success(
        self,
        code: int,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Send a success response to the request.

        Args:
            code: The status code describing the success.
            data: The response data.
            headers: Additional response headers.
        """
        if not headers:
            headers = {}
        headers["Nats-Service-Success-Code"] = str(code)
        await self.respond(data or b"", headers=headers)

    async def respond_error(
        self,
        code: int,
        description: str,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Send an error response to the request.

        Args:
            code: The error code describing the error.
            description: A string describing the error which can be displayed to the client.
            data: The error data.
            headers: Additional response headers.
        """
        if not headers:
            headers = {}
        headers["Nats-Service-Error"] = description
        headers["Nats-Service-Error-Code"] = str(code)
        await self.respond(data or b"", headers=headers)


@dataclass
class NatsRequest(Request):
    """Implementation of Request using nats-py client library."""

    msg: Msg

    def subject(self) -> str:
        """The subject on which request was received."""
        return self.msg.subject

    def headers(self) -> dict[str, str]:
        """The headers of the request."""
        return self.msg.headers or {}

    def data(self) -> bytes:
        """The data of the request."""
        return self.msg.data

    async def respond(self, data: bytes, headers: dict[str, str] | None = None) -> None:
        """Send a success response to the request.

        Args:
            code: The response code.
            data: The response data.
            headers: Additional response headers.
        """
        if not self.msg.reply:
            return
        await self.msg._client.publish(  # type: ignore[reportPrivateUsage]
            self.msg.reply,
            data,
            headers=headers,
        )
