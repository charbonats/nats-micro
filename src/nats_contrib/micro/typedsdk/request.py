from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, overload

from ..request import Request
from .types import E, ParamsT, R, T

if TYPE_CHECKING:
    from .operation import OperationSpec


class TypedRequest(Generic[ParamsT, T, R, E]):
    """Typed request."""

    def __init__(
        self,
        request: Request,
        spec: OperationSpec[Any, ParamsT, T, R, E],
    ) -> None:
        data = spec.request.type_adapter.decode(request.data())
        params = spec.address.get_params(request.subject())
        self._request = request
        self._data = data
        self._params = params
        self._response_type_adapter = spec.response.type_adapter
        self._error_type_adapter = spec.error.type_adapter
        self._status_code = spec.status_code
        self._error_content_type = spec.error.content_type
        self._response_content_type = spec.response.content_type

    def params(self) -> ParamsT:
        return self._params

    def data(self) -> T:
        return self._data

    def headers(self) -> dict[str, str]:
        return self._request.headers()

    @overload
    async def respond(
        self: TypedRequest[ParamsT, T, None, E],
        *,
        headers: dict[str, str] | None = None,
    ) -> None: ...

    @overload
    async def respond(
        self: TypedRequest[ParamsT, T, R, E],
        data: R,
        *,
        headers: dict[str, str] | None = None,
    ) -> None: ...

    async def respond(
        self, data: Any = None, *, headers: dict[str, str] | None = None
    ) -> None:
        headers = headers or {}
        if self._response_content_type:
            headers["Content-Type"] = self._response_content_type
        response = self._response_type_adapter.encode(data)
        await self._request.respond_success(self._status_code, response, headers)

    @overload
    async def respond_error(
        self: TypedRequest[ParamsT, T, R, None],
        code: int,
        description: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None: ...

    @overload
    async def respond_error(
        self: TypedRequest[ParamsT, T, R, E],
        code: int,
        description: str,
        *,
        data: E,
        headers: dict[str, str] | None = None,
    ) -> None: ...

    async def respond_error(
        self,
        code: int,
        description: str,
        *,
        data: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        headers = headers or {}
        if self._error_content_type:
            headers["Content-Type"] = self._error_content_type
        response = self._error_type_adapter.encode(data)
        await self._request.respond_error(code, description, response, headers)
