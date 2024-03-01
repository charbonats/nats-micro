from __future__ import annotations

import datetime
from typing import Callable

from ..api import Endpoint, Service
from ..request import Request
from ..sdk import Context
from .application import Application
from .async_api.renderer import create_docs_server
from .operation import Operation
from .request import TypedRequest
from .types import E, ParamsT, R, S, T


async def add_application(
    ctx: Context,
    app: Application,
    http_port: int | None = None,
    queue_group: str | None = None,
    now: Callable[[], datetime.datetime] | None = None,
    id_generator: Callable[[], str] | None = None,
    api_prefix: str | None = None,
) -> Service:
    """Start an app in a micro context."""

    srv = await ctx.add_service(
        name=app.name,
        version=app.version,
        description=app.description,
        metadata=app.metadata,
        queue_group=queue_group,
        now=now,
        id_generator=id_generator,
        api_prefix=api_prefix,
    )
    for endpoint in app._registered_endpoints:  # pyright: ignore[reportPrivateUsage]
        await add_operation(srv, endpoint, queue_group=queue_group)

    if http_port is not None:
        http_server = create_docs_server(app, http_port)
        await ctx.enter(http_server)

    return srv


async def add_operation(
    service: Service,
    operation: Operation[S, ParamsT, T, R, E],
    queue_group: str | None = None,
) -> Endpoint:
    """Add an operation to a service."""
    errors_to_catch = {e.origin: e for e in operation.spec.catch}

    async def handler(request: Request) -> None:
        try:
            await operation.handle(
                TypedRequest(
                    request,
                    operation.spec,
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
                        payload = operation.spec.error.type_adapter.encode(data)
                    else:
                        payload = b""
                    await request.respond_error(code, description, data=payload)
                    return
            raise

    return await service.add_endpoint(
        operation.spec.name,
        handler=handler,
        subject=operation.spec.address.get_subject(),
        metadata=operation.spec.metadata,
        queue_group=queue_group,
    )
