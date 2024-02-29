from __future__ import annotations

import datetime
from typing import Callable

from ..api import Endpoint, Service
from ..request import Request
from ..sdk import Context
from .endpoint import DecoratedEndpoint
from .request import TypedRequest
from .service import TypedService
from .types import E, ParamsT, R, S, T


async def mount(
    ctx: Context,
    service: TypedService,
    queue_group: str | None = None,
    now: Callable[[], datetime.datetime] | None = None,
    id_generator: Callable[[], str] | None = None,
    api_prefix: str | None = None,
) -> Service:
    """Start a service into a micro context."""

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
        await attach(srv, endpoint, queue_group=queue_group)
    return srv


async def attach(
    service: Service,
    endpoint: DecoratedEndpoint[S, ParamsT, T, R, E],
    queue_group: str | None = None,
) -> Endpoint:
    """Attach an endpoint to a service."""
    errors_to_catch = {e.origin: e for e in endpoint.spec.catch}

    async def handler(request: Request) -> None:
        try:
            await endpoint.handle(
                TypedRequest(
                    request,
                    endpoint.spec,
                )
            )
        except BaseException as e:
            for err in errors_to_catch:
                if isinstance(e, err):
                    error = errors_to_catch[err]
                    code = error.code
                    description = error.description
                    data = error.fmt(e) if error.fmt else None
                    if data:
                        payload = endpoint.spec.error.type_adapter.encode(data)
                    else:
                        payload = b""
                    await request.respond_error(code, description, data=payload)
                    return
            raise

    return await service.add_endpoint(
        endpoint.spec.name,
        handler=handler,
        subject=endpoint.spec.address.get_subject(),
        metadata=endpoint.spec.metadata,
        queue_group=queue_group,
    )
