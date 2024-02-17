"""NATS Micro implementation based on nats-py client library.

NATS Micro is a protocol for building microservices with NATS.

It is documented in [ADR-32: Service API](https://github.com/nats-io/nats-architecture-and-design/blob/main/adr/ADR-32.md).

The reference implementation is in [nats.go](https://github.com/nats-io/nats.go) under [micro package](https://pkg.go.dev/github.com/nats-io/nats.go/micro).
A typescript implementation is available in [nats.deno](https://github.com/nats-io/nats.deno/blob/main/nats-base-client/service.ts)
"""

from __future__ import annotations

import abc
import asyncio
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from json import dumps
from secrets import token_hex
from typing import Awaitable, Callable

from nats.aio.client import Client as NatsClient
from nats.aio.msg import Msg
from nats.aio.subscription import (
    DEFAULT_SUB_PENDING_BYTES_LIMIT,
    DEFAULT_SUB_PENDING_MSGS_LIMIT,
    Subscription,
)
from typing_extensions import TypeAlias


Handler: TypeAlias = Callable[["Request"], Awaitable[None]]


DEFAULT_QUEUE_GROUP = "q"
"""Queue Group name used across all services."""

API_PREFIX = "$SRV"
"""APIPrefix is the root of all control subjects."""


class Request(metaclass=abc.ABCMeta):
    """Request is the interface for a request received by a service.

    An interface is used instead of a class to allow for different implementations.
    It makes it easy to test a service by using a stub implementation of Request.

    Four methods must be implemented:
    - `def subject() -> str`: the subject on which the request was received.
    - `def headers() -> dict[str, str]`: the headers of the request.
    - `def data() -> bytes`: the data of the request.
    - `async def respond(...) -> None`: send a response to the request.
    """

    @abc.abstractmethod
    def subject(self) -> str:
        """The subject on which request was received."""
        raise NotImplementedError()

    @abc.abstractmethod
    def headers(self) -> dict[str, str]:
        """The headers of the request."""
        raise NotImplementedError()

    @abc.abstractmethod
    def data(self) -> bytes:
        """The data of the request."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def respond(self, data: bytes, headers: dict[str, str] | None = None) -> None:
        """Send a success response to the request.

        Args:
            data: The response data.
            headers: Additional response headers.
        """
        raise NotImplementedError()

    async def respond_success(
        self,
        code: int,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Send a success response to the request.

        Args:
            code: The status code describing the success.
            data: The response data.
            headers: Additional response headers.
        """
        if not headers:
            headers = {}
        headers["Nats-Service-Success-Code"] = str(code)
        await self.respond(data or b"", headers=headers)

    async def respond_error(
        self,
        code: int,
        description: str,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Send an error response to the request.

        Args:
            code: The error code describing the error.
            description: A string describing the error which can be displayed to the client.
            data: The error data.
            headers: Additional response headers.
        """
        if not headers:
            headers = {}
        headers["Nats-Service-Error"] = description
        headers["Nats-Service-Error-Code"] = str(code)
        await self.respond(data or b"", headers=headers)


@dataclass
class NatsRequest(Request):
    """Implementation of Request using nats-py client library."""

    msg: Msg

    def subject(self) -> str:
        """The subject on which request was received."""
        return self.msg.subject

    def headers(self) -> dict[str, str]:
        """The headers of the request."""
        return self.msg.headers or {}

    def data(self) -> bytes:
        """The data of the request."""
        return self.msg.data

    async def respond(self, data: bytes, headers: dict[str, str] | None = None) -> None:
        """Send a success response to the request.

        Args:
            code: The response code.
            data: The response data.
            headers: Additional response headers.
        """
        if not self.msg.reply:
            return
        await self.msg._client.publish(  # type: ignore[reportPrivateUsage]
            self.msg.reply,
            data,
            headers=headers,
        )


class ServiceVerb(str, Enum):
    PING = "PING"
    INFO = "INFO"
    STATS = "STATS"


def get_internal_subject(
    verb: ServiceVerb,
    service: str | None = None,
    id: str | None = None,
    api_prefix: str = API_PREFIX,
) -> str:
    """Get the internal subject for a verb."""
    if service:
        if id:
            return f"{api_prefix}.{verb}.{service}.{id}"
        return f"{api_prefix}.{verb}.{service}"
    return f"{api_prefix}.{verb}"


def get_internal_subjects(
    verb: ServiceVerb,
    id: str,
    config: ServiceConfig,
    api_prefix: str = API_PREFIX,
) -> list[str]:
    """Get the internal subjects for a verb."""
    return [
        get_internal_subject(verb, api_prefix=api_prefix),
        get_internal_subject(verb, config.name, api_prefix=api_prefix),
        get_internal_subject(verb, config.name, id, api_prefix=api_prefix),
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

    queue_group: str = DEFAULT_QUEUE_GROUP
    """The default queue group of the service."""

    pending_msgs_limit_by_endpoint: int = DEFAULT_SUB_PENDING_MSGS_LIMIT
    """The default pending messages limit of the service.

    This limit is applied BY subject.
    """

    pending_bytes_limit_by_endpoint: int = DEFAULT_SUB_PENDING_BYTES_LIMIT
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


@dataclass
class EndpointStats:
    """The statistics of an endpoint."""

    name: str
    subject: str
    num_requests: int
    num_errors: int
    last_error: str
    processing_time: int
    average_processing_time: int
    queue_group: str
    data: dict[str, object]

    @classmethod
    def new(cls, config: EndpointConfig) -> EndpointStats:
        return cls(
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


@dataclass
class ServiceStats:
    """The statistics of a service."""

    name: str
    id: str
    version: str
    started: str
    endpoints: list[EndpointStats]
    metadata: dict[str, str]
    type: str = "io.nats.micro.v1.stats_response"

    @classmethod
    def new(cls, id: str, started: datetime, config: ServiceConfig) -> ServiceStats:
        return cls(
            name=config.name,
            id=id,
            version=config.version,
            started=started.isoformat(),
            endpoints=[],
            metadata=config.metadata,
        )


@dataclass
class EndpointInfo:
    """The information of an endpoint."""

    name: str
    subject: str
    metadata: dict[str, str]
    queue_group: str

    @classmethod
    def new(cls, config: EndpointConfig) -> EndpointInfo:
        return cls(
            name=config.name,
            subject=config.subject,
            metadata=config.metadata,
            queue_group=config.queue_group,
        )


@dataclass
class ServiceInfo:
    """The information of a service."""

    name: str
    id: str
    version: str
    description: str
    metadata: dict[str, str]
    endpoints: list[EndpointInfo]
    data: dict[str, object]
    type: str = "io.nats.micro.v1.info_response"

    @classmethod
    def new(cls, id: str, config: ServiceConfig) -> ServiceInfo:
        return cls(
            name=config.name,
            id=id,
            version=config.version,
            description=config.description,
            metadata=config.metadata,
            endpoints=[],
            data={},
        )


@dataclass
class PingInfo:
    """The response to a ping message."""

    name: str
    id: str
    version: str
    metadata: dict[str, str]
    type: str = "io.nats.micro.v1.ping_response"

    @classmethod
    def new(cls, id: str, config: ServiceConfig) -> PingInfo:
        return cls(
            name=config.name,
            id=id,
            version=config.version,
            metadata=config.metadata,
        )


class Endpoint:
    def __init__(self, config: EndpointConfig) -> None:
        """
        Create a new endpoint.

        Args:
            config: The endpoint configuration.
        """
        self.config = config
        self.stats = EndpointStats.new(config)
        self.info = EndpointInfo.new(config)
        self._sub: Subscription | None = None

    def attach_subscription(self, sub: Subscription) -> None:
        """Attach a subscription to the endpoint.

        This is used internally by the service.
        """
        self._sub = sub

    async def stop(self) -> None:
        if self._sub:
            await self._sub.drain()
            self._sub = None


class Group:
    def __init__(self, config: GroupConfig, service: Service) -> None:
        """
        Create a new group.

        Args:
            config: The group configuration.
        """
        self._config = config
        self._service = service

    def group(
        self,
        name: str,
        queue_group: str | None = None,
        pending_bytes_limit: int | None = None,
        pending_msgs_limit: int | None = None,
    ) -> Group:
        """Add a group to the group.

        Args:
            name: The name of the group. Must be a valid NATS subject prefix.
            queue_group: The default queue group of the group. When queue group is not set, it defaults to the queue group of the parent group or service.
            pending_bytes_limit: The default pending bytes limit for each endpoint within the group.
            pending_msgs_limit: The default pending messages limit for each endpoint within the group.
        """
        config = self._config.child(
            name=name,
            queue_group=queue_group,
            pending_bytes_limit=pending_bytes_limit,
            pending_msgs_limit=pending_msgs_limit,
        )
        group = Group(config, self._service)
        return group

    async def add_endpoint(
        self,
        name: str,
        handler: Handler,
        subject: str | None = None,
        queue_group: str | None = None,
        metadata: dict[str, str] | None = None,
        pending_bytes_limit: int | None = None,
        pending_msgs_limit: int | None = None,
    ) -> Endpoint:
        """Add an endpoint to the group."""
        return await self._service.add_endpoint(
            name=name,
            subject=f"{self._config.name}.{subject or name}",
            handler=handler,
            metadata=metadata,
            queue_group=queue_group or self._config.queue_group,
            pending_bytes_limit=pending_bytes_limit
            or self._config.pending_bytes_limit_by_endpoint,
            pending_msgs_limit=pending_msgs_limit
            or self._config.pending_msgs_limit_by_endpoint,
        )


class Service:
    def __init__(
        self,
        nc: NatsClient,
        config: ServiceConfig,
        api_prefix: str = API_PREFIX,
    ) -> None:
        """
        Create a new service.

        Users should not create a service directly but use `create_service` instead.

        Args:
            nc: The NATS client.
            config: The service configuration.
            api_prefix: The prefix of the control subjects.
        """
        self._nc = nc
        self._config = config
        self._api_prefix = api_prefix
        # Initialize state
        self._id = token_hex(12)
        self._endpoints: list[Endpoint] = []
        self._stopped = False
        # Internal responses
        self._stats = ServiceStats.new(self._id, datetime.now(timezone.utc), config)
        self._info = ServiceInfo.new(self._id, config)
        self._ping_response = PingInfo.new(self._id, config)
        # Cache the serialized ping response
        self._ping_response_message = dumps(asdict(self._ping_response)).encode()
        # Internal subscriptions
        self._ping_subscriptions: list[Subscription] = []
        self._info_subscriptions: list[Subscription] = []
        self._stats_subscriptions: list[Subscription] = []

    def group(
        self,
        name: str,
        queue_group: str | None = None,
        pending_bytes_limit_by_endpoint: int | None = None,
        pending_msgs_limit_by_endpoint: int | None = None,
    ) -> Group:
        """Add a group to the service.

        A group is a collection of endpoints that share the same prefix,
        and the same default queue group and pending limits.

        At runtime, a group does not exist as a separate entity, only
        endpoints exist. However, groups are useful to organize endpoints
        and to set default values for queue group and pending limits.

        Args:
            name: The name of the group.
            queue_group: The default queue group of the group. When queue group is not set, it defaults to the queue group of the parent group or service.
            pending_bytes_limit_by_endpoint: The default pending bytes limit for each endpoint within the group.
            pending_msgs_limit_by_endpoint: The default pending messages limit for each endpoint within the group.
        """
        config = GroupConfig(
            name=name,
            queue_group=queue_group or self._config.queue_group,
            pending_bytes_limit_by_endpoint=pending_bytes_limit_by_endpoint
            or self._config.pending_bytes_limit_by_endpoint,
            pending_msgs_limit_by_endpoint=pending_msgs_limit_by_endpoint
            or self._config.pending_msgs_limit_by_endpoint,
        )
        return Group(config, self)

    async def start(self) -> None:
        """Start the service.

        A service MUST be started before adding endpoints.

        This will start the internal subscriptions and enable
        service discovery.
        """
        for subject in get_internal_subjects(ServiceVerb.PING, self._id, self._config):
            sub = await self._nc.subscribe(  # pyright: ignore[reportUnknownMemberType]
                subject,
                cb=self._handle_ping_request,
            )
            self._ping_subscriptions.append(sub)

        for subject in get_internal_subjects(ServiceVerb.INFO, self._id, self._config):
            sub = await self._nc.subscribe(  # pyright: ignore[reportUnknownMemberType]
                subject,
                cb=self._handle_info_request,
            )
            self._info_subscriptions.append(sub)

        for subject in get_internal_subjects(ServiceVerb.STATS, self._id, self._config):
            sub = await self._nc.subscribe(  # pyright: ignore[reportUnknownMemberType]
                subject,
                cb=self._handle_stats_request,
            )
            self._stats_subscriptions.append(sub)

    async def stop(self) -> None:
        """Stop the service.

        This will stop all endpoints and internal subscriptions.
        """
        self._stopped = True
        # Stop endpoints
        await asyncio.gather(*(ep.stop() for ep in self._endpoints))
        # Stop internal subscriptions
        await asyncio.gather(
            *(
                sub.unsubscribe()
                for subscriptions in (
                    self._stats_subscriptions,
                    self._info_subscriptions,
                    self._ping_subscriptions,
                )
                for sub in subscriptions
            )
        )

    async def add_endpoint(
        self,
        name: str,
        handler: Handler,
        subject: str | None = None,
        queue_group: str | None = None,
        metadata: dict[str, str] | None = None,
        pending_bytes_limit: int | None = None,
        pending_msgs_limit: int | None = None,
    ) -> Endpoint:
        """Add an endpoint to the service.

        An endpoint is a request-reply handler for a subject.

        Args:
            name: The name of the endpoint.
            handler: The handler of the endpoint.
            subject: The subject of the endpoint. When subject is not set, it defaults to the name of the endpoint.
            queue_group: The queue group of the endpoint. When queue group is not set, it defaults to the queue group of the parent group or service.
            metadata: The metadata of the endpoint.
            pending_bytes_limit: The pending bytes limit for this endpoint.
            pending_msgs_limit: The pending messages limit for this endpoint.
        """
        if self._stopped:
            raise RuntimeError("Cannot add endpoint to a stopped service")
        config = self._config.endpoint_config(
            name=name,
            handler=handler,
            subject=subject,
            queue_group=queue_group,
            metadata=metadata,
            pending_bytes_limit=pending_bytes_limit,
            pending_msgs_limit=pending_msgs_limit,
        )
        ep = Endpoint(config)
        subscription_handler = self._create_handler(ep)
        subscription = (
            await self._nc.subscribe(  # pyright: ignore[reportUnknownMemberType]
                config.subject,
                queue=config.queue_group,
                cb=subscription_handler,
            )
        )
        ep.attach_subscription(subscription)
        self._endpoints.append(ep)
        self._stats.endpoints.append(ep.stats)
        self._info.endpoints.append(ep.info)
        return ep

    async def _handle_ping_request(self, msg: Msg) -> None:
        """Handle the ping message."""
        await msg.respond(data=self._ping_response_message)

    async def _handle_info_request(self, msg: Msg) -> None:
        """Handle the info message."""
        await msg.respond(data=dumps(asdict(self._info)).encode())

    async def _handle_stats_request(self, msg: Msg) -> None:
        """Handle the stats message."""
        await msg.respond(data=dumps(asdict(self._stats)).encode())

    def _create_handler(self, endpoint: Endpoint) -> Callable[[Msg], Awaitable[None]]:
        """Handle a message."""

        async def handler(msg: Msg) -> None:
            timer = _Timer()
            endpoint.stats.num_requests += 1
            request = NatsRequest(msg)
            try:
                await endpoint.config.handler(request)
            except Exception as exc:
                endpoint.stats.num_errors += 1
                endpoint.stats.last_error = str(exc)
                await request.respond_error(
                    code=500,
                    description="Internal Server Error",
                )
            endpoint.stats.processing_time += timer.elapsed_nanoseconds()
            endpoint.stats.average_processing_time = int(
                endpoint.stats.processing_time / endpoint.stats.num_requests
            )

        return handler

    async def __aenter__(self) -> Service:
        """Implement the asynchronous context manager interface."""
        await self.start()
        return self

    async def __aexit__(self, *args: object, **kwargs: object) -> None:
        """Implement the asynchronous context manager interface."""
        await self.stop()


def create_service(
    nc: NatsClient,
    name: str,
    version: str,
    description: str | None = None,
    metadata: dict[str, str] | None = None,
    api_prefix: str = API_PREFIX,
) -> Service:
    """Create a new service.

    A service is a collection of endpoints that are grouped together
    under a common name.

    Each endpoint is a request-reply handler for a subject.

    It's possible to add endpoints to a service after it has been created AND
    started.

    Args:
        nc: The NATS client.
        name: The name of the service.
        version: The version of the service. Must be a valid semver version.
        description: The description of the service.
        metadata: The metadata of the service.
        api_prefix: The prefix of the control subjects.
    """

    config = ServiceConfig(
        name=name,
        version=version,
        description=description or "",
        metadata=metadata or {},
    )
    srv = Service(nc=nc, config=config, api_prefix=api_prefix)
    return srv


class _Timer:
    __slots__ = "_start"

    def __init__(self) -> None:
        self._start = time.perf_counter_ns()

    def elapsed_nanoseconds(self) -> int:
        return time.perf_counter_ns() - self._start
