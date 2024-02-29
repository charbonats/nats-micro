from __future__ import annotations
import datetime
from typing import Callable


from ..api import Endpoint, Service
from ..request import Request
from ..sdk import Context
from .address import ParamsT, R, T
from .endpoint import DecoratedEndpoint, E, S, TypedRequest
from .service import TypedService
from .type_adapter import TypeAdapterFactory, default_type_adapter, TypeAdapter


class TypedMicroRequest(TypedRequest[ParamsT, T, R, E]):
    """Typed request."""

    def __init__(
        self,
        request: Request,
        params: ParamsT,
        data: T,
        response_type_adapter: TypeAdapter[R],
        error_type_adapter: TypeAdapter[E],
    ) -> None:
        self._request = request
        self._data = data
        self._params = params
        self._response_type_adapter = response_type_adapter
        self._error_type_adapter = error_type_adapter

    def params(self) -> ParamsT:
        return self._params

    def data(self) -> T:
        return self._data

    def headers(self) -> dict[str, str]:
        return self._request.headers()

    async def respond(self, data: R, headers: dict[str, str] | None = None) -> None:
        response = self._response_type_adapter.encode(data)
        await self._request.respond(response, headers)

    async def respond_error(
        self, data: E, headers: dict[str, str] | None = None
    ) -> None:
        response = self._error_type_adapter.encode(data)
        await self._request.respond(response, headers)


async def mount(
    ctx: Context,
    service: TypedService,
    queue_group: str | None = None,
    type_adapter: TypeAdapterFactory | None = None,
    now: Callable[[], datetime.datetime] | None = None,
    id_generator: Callable[[], str] | None = None,
    api_prefix: str | None = None,
) -> Service:
    """Start a service into a micro context."""

    type_adapter = type_adapter or default_type_adapter()
    srv = await ctx.add_service(
        name=service.name,
        version=service.version,
        description=service.description,
        metadata=service.metadata,
        queue_group=queue_group,
        now=now,
        id_generator=id_generator,
        api_prefix=api_prefix,
    )
    for (
        endpoint
    ) in service._registered_endpoints:  # pyright: ignore[reportPrivateUsage]
        await attach(srv, endpoint, type_adapter=type_adapter)
    return srv


async def attach(
    service: Service,
    endpoint: DecoratedEndpoint[S, ParamsT, T, R, E],
    queue_group: str | None = None,
    type_adapter: TypeAdapterFactory | None = None,
) -> Endpoint:
    """Attach an endpoint to a service."""

    type_adapter = type_adapter or default_type_adapter()
    request_adapter = type_adapter(endpoint.spec.request.type)
    response_adapter = type_adapter(endpoint.spec.response.type)
    error_type_adapter = type_adapter(endpoint.spec.error.type)

    async def handler(request: Request) -> None:
        # FIXME: Apply try/except and return 400 Bad Request on error
        # How can the error be consistent with the schema?
        data = request_adapter.decode(request.data())
        params = endpoint.spec.address.get_params(request.subject())
        await endpoint.handle(
            TypedMicroRequest(
                request,
                params,
                data,
                response_adapter,
                error_type_adapter,
            )
        )

    return await service.add_endpoint(
        endpoint.spec.name,
        handler=handler,
        subject=endpoint.spec.address.subject,
        metadata=endpoint.spec.metadata,
        queue_group=queue_group,
    )
