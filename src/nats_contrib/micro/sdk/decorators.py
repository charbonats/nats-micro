from __future__ import annotations

import datetime
import inspect
from dataclasses import dataclass, field
from typing import Any, AsyncContextManager, Callable, Iterator, TypeVar

from nats.aio.client import Client as NATS
from typing_extensions import dataclass_transform

from ..api import Group, Service, add_service
from ..middleware import Middleware
from ..request import Handler

S = TypeVar("S", bound=Any)
F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class EndpointSpec:
    name: str
    """An alphanumeric human-readable string used to describe the endpoint.

    Multiple endpoints can have the same names.
    """

    subject: str | None = None
    """The subject of the endpoint. When subject is not set, it defaults to the name of the endpoint."""

    queue_group: str | None = None
    """The queue group of the endpoint. When queue group is not set, it defaults to the queue group of the parent group or service."""

    metadata: dict[str, str] | None = None
    """The metadata of the endpoint."""

    pending_msgs_limit: int | None = None
    """The pending message limit for this endpoint."""

    pending_bytes_limit: int | None = None
    """The pending bytes limit for this endpoint."""

    disabled: bool = False
    """Whether the endpoint is disabled."""


@dataclass
class ServiceSpec:

    name: str
    """The kind of the service. Shared by all services that have the same name.
    This name can only have A-Z, a-z, 0-9, dash, underscore."""

    version: str
    """The version of the service.
    This verson must be a valid semantic version."""

    description: str | None = None
    """The description of the service."""

    metadata: dict[str, str] | None = None
    """The metadata of the service."""

    queue_group: str | None = None
    """The default queue group of the service."""

    pending_msgs_limit_by_endpoint: int | None = None
    """The default pending messages limit of the service.

    This limit is applied BY subject.
    """

    pending_bytes_limit_by_endpoint: int | None = None
    """The default pending bytes limit of the service.

    This limit is applied BY subject.
    """


@dataclass
class GroupSpec:
    name: str
    """An alphanumeric human-readable string used to describe the group.

    Multiple groups can have the same names.
    """

    queue_group: str | None = None
    """The queue group of the group. When queue group is not set, it defaults to the queue group of the parent group or service."""

    pending_msgs_limit: int | None = None
    """The pending message limit for this group."""

    pending_bytes_limit: int | None = None
    """The pending bytes limit for this group."""


@dataclass_transform(field_specifiers=(field,))
def service(
    name: str,
    version: str,
    description: str | None = None,
    metadata: dict[str, str] | None = None,
    queue_group: str | None = None,
    pending_msgs_limit_by_endpoint: int | None = None,
    pending_bytes_limit_by_endpoint: int | None = None,
) -> Callable[[type[S]], type[S]]:
    """ "A decorator to define a micro service."""

    def func(cls: type[S]) -> type[S]:
        spec = ServiceSpec(
            name=name,
            version=version,
            description=description,
            metadata=metadata,
            queue_group=queue_group,
            pending_msgs_limit_by_endpoint=pending_msgs_limit_by_endpoint,
            pending_bytes_limit_by_endpoint=pending_bytes_limit_by_endpoint,
        )
        dc = dataclass()(cls)
        dc.__service_spec__ = spec
        return cls

    return func


@dataclass_transform(field_specifiers=(field,))
def group(
    name: str,
    queue_group: str | None = None,
    pending_msgs_limit_by_endpoint: int | None = None,
    pending_bytes_limit_by_endpoint: int | None = None,
) -> Callable[[type[S]], type[S]]:
    """ "A decorator to define a micro service group."""

    def func(cls: type[S]) -> type[S]:
        spec = GroupSpec(
            name=name,
            queue_group=queue_group,
            pending_msgs_limit=pending_msgs_limit_by_endpoint,
            pending_bytes_limit=pending_bytes_limit_by_endpoint,
        )
        dc = dataclass()(cls)
        dc.__group_spec__ = spec
        return cls

    return func


def endpoint(
    name: str | None = None,
    subject: str | None = None,
    queue_group: str | None = None,
    pending_msgs_limit: int | None = None,
    pending_bytes_limit: int | None = None,
    disabled: bool = False,
) -> Callable[[F], F]:
    """A decorator to define an endpoint."""

    def func(f: F) -> F:

        spec = EndpointSpec(
            name=name or f.__name__,
            subject=subject,
            queue_group=queue_group,
            metadata=None,
            pending_msgs_limit=pending_msgs_limit,
            pending_bytes_limit=pending_bytes_limit,
            disabled=disabled,
        )
        setattr(f, "__endpoint_spec__", spec)
        return f

    return func


def register_service(
    client: NATS,
    service: Any,
    prefix: str | None = None,
    now: Callable[[], datetime.datetime] | None = None,
    id_generator: Callable[[], str] | None = None,
    api_prefix: str | None = None,
    middlewares: list[Middleware] | None = None,
) -> AsyncContextManager[Service]:
    class ServiceMounter:
        def __init__(self) -> None:
            self.service: Service | None = None

        async def __aenter__(self) -> Service:
            # Get service spec
            service_spec = get_service_spec(service)
            # Iterate over endpoints
            micro_service = add_service(
                client,
                service_spec.name,
                service_spec.version,
                service_spec.description,
                service_spec.metadata,
                service_spec.queue_group,
                service_spec.pending_bytes_limit_by_endpoint,
                service_spec.pending_msgs_limit_by_endpoint,
                now=now,
                id_generator=id_generator,
                api_prefix=api_prefix,
            )
            await micro_service.start()
            self.service = micro_service
            parent: Group | Service
            if prefix:
                parent = micro_service.add_group(prefix)
            else:
                parent = micro_service
            for endpoint_handler, endpoint_spec in get_endpoints_specs(service):
                if endpoint_spec.disabled:
                    continue
                await parent.add_endpoint(
                    name=endpoint_spec.name,
                    handler=endpoint_handler,
                    subject=endpoint_spec.subject,
                    queue_group=endpoint_spec.queue_group,
                    pending_msgs_limit=endpoint_spec.pending_msgs_limit,
                    pending_bytes_limit=endpoint_spec.pending_bytes_limit,
                    middlewares=middlewares,
                )
            return micro_service

        async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
            if self.service:
                await self.service.stop()

    return ServiceMounter()


async def register_group(
    service: Service,
    group: Any,
    prefix: str | None = None,
    middlewares: list[Middleware] | None = None,
) -> None:

    group_spec = get_group_spec(group)
    parent: Group | Service
    if prefix:
        parent = service.add_group(prefix)
    else:
        parent = service
    parent_group = parent.add_group(
        name=group_spec.name,
        queue_group=group_spec.queue_group,
        pending_msgs_limit_by_endpoint=group_spec.pending_msgs_limit,
        pending_bytes_limit_by_endpoint=group_spec.pending_bytes_limit,
    )
    for endpoint_handler, endpoint_spec in get_endpoints_specs(group):
        if endpoint_spec.disabled:
            continue
        await parent_group.add_endpoint(
            name=endpoint_spec.name,
            handler=endpoint_handler,
            subject=endpoint_spec.subject,
            queue_group=endpoint_spec.queue_group,
            pending_msgs_limit=endpoint_spec.pending_msgs_limit,
            pending_bytes_limit=endpoint_spec.pending_bytes_limit,
            middlewares=middlewares,
        )


def get_service_spec(instance: object) -> ServiceSpec:
    try:
        return instance.__service_spec__  # type: ignore
    except AttributeError:
        raise TypeError("ServiceRouter must be decorated with @service")


def get_group_spec(instance: object) -> GroupSpec:
    try:
        return instance.__group_spec__  # type: ignore
    except AttributeError:
        raise TypeError("Group must be decorated with @group")


def get_endpoints_specs(instance: object) -> Iterator[tuple[Handler, EndpointSpec]]:
    for _, member in inspect.getmembers(instance):
        if hasattr(member, "__endpoint_spec__"):
            yield member, member.__endpoint_spec__
