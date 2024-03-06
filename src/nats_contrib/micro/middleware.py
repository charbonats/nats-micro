from __future__ import annotations

from typing import Awaitable, Callable

from typing_extensions import TypeAlias

from .request import Handler, Request

NextHandler: TypeAlias = Callable[[Request], Awaitable["Response"]]
"""NextHandler is a type alias for the next handler in a chain of middlewares."""

Middleware: TypeAlias = Callable[[Request, NextHandler], Awaitable["Response"]]
"""Middleware is a type alias for a middleware function."""


class Response:
    """Response holds the response data and headers as well as the original request.

    In order to update the response data or headers, use the methods provided by this class.
    """

    __slots__ = ["origin", "_data", "_headers"]

    def __init__(self, origin: Request, data: bytes, headers: dict[str, str]):
        self.origin = origin
        self._data = data
        self._headers = headers

    def data(self) -> bytes:
        """Get the response data."""
        return self._data

    def headers(self) -> dict[str, str]:
        """Get the response headers."""
        return self._headers

    def add_header(self, key: str, value: str) -> None:
        """Add a header to the response."""
        self._headers[key] = value

    def remove_header(self, key: str) -> None:
        """Remove a header from the response."""
        self._headers.pop(key, None)

    def update_headers(self, headers: dict[str, str]) -> None:
        """Update the response headers."""
        self._headers.update(headers)

    def clear_headers(self) -> None:
        """Clear the response headers."""
        self._headers.clear()

    def set_data(self, data: bytes) -> None:
        """Set the response data."""
        self._data = data

    def clear_data(self) -> None:
        """Clear the response data."""
        self._data = b""


def apply_middlewares(handler: Handler, middlewares: list[Middleware]) -> Handler:
    """Apply a list of middlewares to a handler."""
    if not middlewares:
        return handler
    chained = _create_next_handler(handler)
    chained = _apply_middlewares_to_next_handler(chained, middlewares)
    return _create_final_handler(chained)


def _create_next_handler(handler: Handler) -> NextHandler:
    async def forward(request: Request) -> Response:
        req = _CapturedRequest(request)
        await handler(req)
        return req.get_response()

    return forward


def _create_final_handler(forward: NextHandler) -> Handler:
    async def unwrap(request: Request) -> None:
        response = await forward(request)
        await response.origin.respond(response.data(), response.headers())

    return unwrap


def _apply_middlewares_to_next_handler(
    handler: NextHandler, middlewares: list[Middleware]
) -> NextHandler:
    """Apply a list of middlewares to a handler."""
    if not middlewares:
        return handler
    chained = handler
    for middleware in reversed(middlewares):
        chained = _chain_next_handler_and_middleware(chained, middleware)
    return chained


def _chain_next_handler_and_middleware(
    handler: NextHandler, middleware: Middleware
) -> NextHandler:
    """Chain a middleware to a handler."""

    async def forward(request: Request) -> Response:
        return await middleware(request, handler)

    return forward


class _CapturedRequest(Request):
    def __init__(self, request: Request):
        self._request = request
        self._response: Response | None = None

    def subject(self) -> str:
        return self._request.subject()

    def headers(self) -> dict[str, str]:
        return self._request.headers()

    def data(self) -> bytes:
        return self._request.data()

    async def respond(self, data: bytes, headers: dict[str, str] | None = None) -> None:
        self._response = Response(self._request, data, headers or {})

    def get_response(self) -> Response:
        if self._response is None:
            raise ValueError("No response was set")
        return self._response
