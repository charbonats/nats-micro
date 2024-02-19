"""NATS Micro implementation based on nats-py client library.

NATS Micro is a protocol for building microservices with NATS.

It is documented in [ADR-32: Service API](https://github.com/nats-io/nats-architecture-and-design/blob/main/adr/ADR-32.md).

The reference implementation is in [nats.go](https://github.com/nats-io/nats.go) under [micro package](https://pkg.go.dev/github.com/nats-io/nats.go/micro).
A typescript implementation is available in [nats.deno](https://github.com/nats-io/nats.deno/blob/main/nats-base-client/service.ts)
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from json import dumps

from .models import EndpointInfo, EndpointStats, PingInfo, ServiceInfo, ServiceStats
from .request import Handler


class ServiceVerb(str, Enum):
    PING = "PING"
    INFO = "INFO"
    STATS = "STATS"


def get_internal_subject(
    verb: ServiceVerb,
    service: str | None,
    id: str | None,
    api_prefix: str,
) -> str:
    """Get the internal subject for a verb."""
    verb_literal = verb.value
    if service:
        if id:
            return f"{api_prefix}.{verb_literal}.{service}.{id}"
        return f"{api_prefix}.{verb_literal}.{service}"
    return f"{api_prefix}.{verb_literal}"


def get_internal_subjects(
    verb: ServiceVerb,
    id: str,
    config: ServiceConfig,
    api_prefix: str,
) -> list[str]:
    """Get the internal subjects for a verb."""
    return [
        get_internal_subject(verb, service=None, id=None, api_prefix=api_prefix),
        get_internal_subject(verb, service=config.name, id=None, api_prefix=api_prefix),
        get_internal_subject(verb, service=config.name, id=id, api_prefix=api_prefix),
    ]


@dataclass
class ServiceConfig:
    """The configuration of a service."""

    name: str
    """The kind of the service. Shared by all services that have the same name.
    This name can only have A-Z, a-z, 0-9, dash, underscore."""

    version: str
    """The version of the service.
    This verson must be a valid semantic version."""

    description: str
    """The description of the service."""

    metadata: dict[str, str]
    """The metadata of the service."""

    queue_group: str
    """The default queue group of the service."""

    pending_msgs_limit_by_endpoint: int
    """The default pending messages limit of the service.

    This limit is applied BY subject.
    """

    pending_bytes_limit_by_endpoint: int
    """The default pending bytes limit of the service.

    This limit is applied BY subject.
    """

    def endpoint_config(
        self,
        name: str,
        handler: Handler,
        subject: str | None = None,
        queue_group: str | None = None,
        metadata: dict[str, str] | None = None,
        pending_bytes_limit: int | None = None,
        pending_msgs_limit: int | None = None,
    ) -> EndpointConfig:
        return EndpointConfig(
            name=name,
            subject=subject or name,
            handler=handler,
            metadata=metadata or {},
            queue_group=queue_group or self.queue_group,
            pending_bytes_limit=pending_bytes_limit
            or self.pending_bytes_limit_by_endpoint,
            pending_msgs_limit=pending_msgs_limit
            or self.pending_msgs_limit_by_endpoint,
        )


@dataclass
class EndpointConfig:
    name: str
    """An alphanumeric human-readable string used to describe the endpoint.

    Multiple endpoints can have the same names.
    """

    subject: str
    """The subject of the endpoint. When subject is not set, it defaults to the name of the endpoint."""

    handler: Handler
    """The handler of the endpoint."""

    queue_group: str
    """The queue group of the endpoint. When queue group is not set, it defaults to the queue group of the parent group or service."""

    metadata: dict[str, str]
    """The metadata of the endpoint."""

    pending_msgs_limit: int
    """The pending message limit for this endpoint."""

    pending_bytes_limit: int
    """The pending bytes limit for this endpoint."""


@dataclass
class GroupConfig:
    """The configuration of a group."""

    name: str
    """The name of the group.
    Group names cannot contain '>' wildcard (as group name serves as subject prefix)."""

    queue_group: str
    """The default queue group of the group."""

    pending_msgs_limit_by_endpoint: int
    """The default pending message limit for each endpoint within the group."""

    pending_bytes_limit_by_endpoint: int
    """The default pending bytes limit for each endpoint within the group."""

    def child(
        self,
        name: str,
        queue_group: str | None = None,
        pending_bytes_limit: int | None = None,
        pending_msgs_limit: int | None = None,
    ) -> GroupConfig:
        return GroupConfig(
            name=f"{self.name}.{name}",
            queue_group=queue_group or self.queue_group,
            pending_bytes_limit_by_endpoint=pending_bytes_limit
            or self.pending_bytes_limit_by_endpoint,
            pending_msgs_limit_by_endpoint=pending_msgs_limit
            or self.pending_msgs_limit_by_endpoint,
        )


def create_endpoint_stats(config: EndpointConfig) -> EndpointStats:
    return EndpointStats(
        name=config.name,
        subject=config.subject,
        num_requests=0,
        num_errors=0,
        last_error="",
        processing_time=0,
        average_processing_time=0,
        queue_group=config.queue_group,
        data={},
    )


def new_service_stats(
    id: str, started: datetime, config: ServiceConfig
) -> ServiceStats:
    return ServiceStats(
        name=config.name,
        id=id,
        version=config.version,
        started=started.isoformat(),
        endpoints=[],
        metadata=config.metadata,
    )


def create_endpoint_info(config: EndpointConfig) -> EndpointInfo:
    return EndpointInfo(
        name=config.name,
        subject=config.subject,
        metadata=config.metadata,
        queue_group=config.queue_group,
    )


def new_service_info(id: str, config: ServiceConfig) -> ServiceInfo:
    return ServiceInfo(
        name=config.name,
        id=id,
        version=config.version,
        description=config.description,
        metadata=config.metadata,
        endpoints=[],
        data={},
    )


def new_ping_info(id: str, config: ServiceConfig) -> PingInfo:
    return PingInfo(
        name=config.name,
        id=id,
        version=config.version,
        metadata=config.metadata,
    )


def encode_ping_info(info: PingInfo) -> bytes:
    return dumps(asdict(info), separators=(",", ":")).encode()


def encode_stats(stats: ServiceStats) -> bytes:
    return dumps(asdict(stats), separators=(",", ":")).encode()


def encode_info(info: ServiceInfo) -> bytes:
    return dumps(asdict(info), separators=(",", ":")).encode()


def default_clock() -> datetime:
    """A default clock implementation."""
    return datetime.now(timezone.utc)


class Timer:
    __slots__ = "_start"

    def __init__(self) -> None:
        self._start = time.perf_counter_ns()

    def elapsed_nanoseconds(self) -> int:
        return time.perf_counter_ns() - self._start
