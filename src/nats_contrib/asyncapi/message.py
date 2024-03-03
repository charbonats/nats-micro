from __future__ import annotations

import abc
from typing import Any, Generic, overload

from .types import E, ParamsT, R, T


class Message(Generic[ParamsT, T, R, E], metaclass=abc.ABCMeta):
    """A message received as a request."""

    @abc.abstractmethod
    def params(self) -> ParamsT:
        """Get the message parameters."""
        raise NotImplementedError

    @abc.abstractmethod
    def payload(self) -> T:
        """Get the message payload."""
        raise NotImplementedError

    @abc.abstractmethod
    def headers(self) -> dict[str, str]:
        """Get the message headers."""
        raise NotImplementedError

    @overload
    @abc.abstractmethod
    async def respond(
        self: Message[ParamsT, T, None, E],
        *,
        headers: dict[str, str] | None = None,
    ) -> None: ...

    @overload
    @abc.abstractmethod
    async def respond(
        self: Message[ParamsT, T, R, E],
        data: R,
        *,
        headers: dict[str, str] | None = None,
    ) -> None: ...

    @abc.abstractmethod
    async def respond(
        self, data: Any = None, *, headers: dict[str, str] | None = None
    ) -> None:
        """Respond to the message."""
        raise NotImplementedError

    @overload
    @abc.abstractmethod
    async def respond_error(
        self: Message[ParamsT, T, R, None],
        code: int,
        description: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None: ...

    @overload
    @abc.abstractmethod
    async def respond_error(
        self: Message[ParamsT, T, R, E],
        code: int,
        description: str,
        *,
        data: E,
        headers: dict[str, str] | None = None,
    ) -> None: ...

    @abc.abstractmethod
    async def respond_error(
        self,
        code: int,
        description: str,
        *,
        data: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Respond with an error to the message."""
        raise NotImplementedError
