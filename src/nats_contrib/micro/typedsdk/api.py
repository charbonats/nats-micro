from __future__ import annotations

from ..api import Endpoint, Service
from ..request import Request
from ..sdk import Context
from .address import ParamsT, R, T
from .endpoint import DecoratedEndpoint, E, S
from .service import AppService
from .type_adapter import TypeAdapterFactory, default_type_adapter


async def mount(
    ctx: Context,
    service: AppService,
    type_adapter: TypeAdapterFactory | None = None,
) -> Service:
    type_adapter = type_adapter or default_type_adapter()
    srv = await ctx.add_service(service.name, service.version, service.description)
    for (
        endpoint
    ) in service._registered_endpoints:  # pyright: ignore[reportPrivateUsage]
        await attach(srv, endpoint, type_adapter)
    return srv


async def attach(
    service: Service,
    endpoint: DecoratedEndpoint[S, ParamsT, T, R, E],
    type_adapter: TypeAdapterFactory | None = None,
) -> Endpoint:
    type_adapter = type_adapter or default_type_adapter()
    request_adapter = type_adapter(endpoint.spec.request_schema)
    response_adapter = type_adapter(endpoint.spec.response_schema)

    async def handler(request: Request) -> None:
        params = endpoint.spec.address.get_params(request.subject())
        data = request_adapter.decode(request.data())
        result = await endpoint.handle(params, data)
        response = response_adapter.encode(result)
        await request.respond(response)

    return await service.add_endpoint(
        endpoint.spec.name,
        handler=handler,
        subject=endpoint.spec.address.subject,
    )
