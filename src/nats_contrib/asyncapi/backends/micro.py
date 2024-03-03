from __future__ import annotations

import datetime
from typing import Any, Callable

from nats.aio.client import Client as NatsClient

from nats_contrib.micro.api import Endpoint, Service
from nats_contrib.micro.client import Client as BaseMicroClient
from nats_contrib.micro.client import ServiceError
from nats_contrib.micro.context import Context
from nats_contrib.micro.request import Request as MicroRequest

from ..application import Application
from ..client import OperationError, Reply
from ..message import Message
from ..operation import Operation, OperationRequest, OperationSpec
from ..types import E, ParamsT, R, S, T


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
        from ..api_specs.renderer import create_docs_server

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

    async def handler(request: MicroRequest) -> None:
        try:
            await operation.handle(
                MicroMessage(
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


class MicroMessage(Message[ParamsT, T, R, E]):
    """A message received as a request."""

    def __init__(
        self,
        request: MicroRequest,
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

    def payload(self) -> T:
        return self._data

    def headers(self) -> dict[str, str]:
        return self._request.headers()

    async def respond(
        self, data: Any = None, *, headers: dict[str, str] | None = None
    ) -> None:
        headers = headers or {}
        if self._response_content_type:
            headers["Content-Type"] = self._response_content_type
        response = self._response_type_adapter.encode(data)
        await self._request.respond_success(self._status_code, response, headers)

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


class Client:
    def __init__(
        self,
        client: NatsClient,
    ) -> None:
        self._client = BaseMicroClient(client)

    async def send(
        self,
        request: OperationRequest[ParamsT, T, R, E],
        headers: dict[str, str] | None = None,
        timeout: float = 1,
    ) -> Reply[ParamsT, T, R, E]:
        """Send a request."""
        data = request.spec.request.type_adapter.encode(request.payload)
        try:
            response = await self._client.request(
                request.subject,
                data,
                headers=headers,
                timeout=timeout,
            )
        except ServiceError as e:
            return Reply(request, None, None, OperationError(e.code, e.description))
        return Reply(
            request,
            response.data,
            response.headers or {},
            None,
        )
