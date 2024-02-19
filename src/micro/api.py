"""NATS Micro implementation based on nats-py client library.

NATS Micro is a protocol for building microservices with NATS.

It is documented in [ADR-32: Service API](https://github.com/nats-io/nats-architecture-and-design/blob/main/adr/ADR-32.md).

The reference implementation is in [nats.go](https://github.com/nats-io/nats.go) under [micro package](https://pkg.go.dev/github.com/nats-io/nats.go/micro).
A typescript implementation is available in [nats.deno](https://github.com/nats-io/nats.deno/blob/main/nats-base-client/service.ts)
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
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

from . import internal
from .models import ServiceInfo, ServiceStats
from .request import Handler, NatsRequest

DEFAULT_QUEUE_GROUP = "q"
"""Queue Group name used across all services."""

API_PREFIX = "$SRV"
"""APIPrefix is the root of all control subjects."""


def add_service(
    nc: NatsClient,
    name: str,
    version: str,
    description: str | None = None,
    metadata: dict[str, str] | None = None,
    queue_group: str | None = None,
    api_prefix: str | None = None,
    id_generator: Callable[[], str] | None = None,
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
        queue_group: The default queue group of the service.
        api_prefix: The prefix of the control subjects.
        id_generator: The function to generate a unique service instance id.
    """
    if id_generator is None:
        id_generator = token_hex
    instance_id = token_hex(12)
    service_config = internal.ServiceConfig(
        name=name,
        version=version,
        description=description or "",
        metadata=metadata or {},
        queue_group=queue_group or DEFAULT_QUEUE_GROUP,
        pending_bytes_limit_by_endpoint=DEFAULT_SUB_PENDING_BYTES_LIMIT,
        pending_msgs_limit_by_endpoint=DEFAULT_SUB_PENDING_MSGS_LIMIT,
    )
    return Service(
        nc=nc,
        id=instance_id,
        config=service_config,
        api_prefix=api_prefix or API_PREFIX,
    )


class Endpoint:
    """Endpoint manages a service endpoint."""

    def __init__(self, config: internal.EndpointConfig) -> None:
        self.config = config
        self.stats = internal.create_endpoint_stats(config)
        self.info = internal.create_endpoint_info(config)
        self._sub: Subscription | None = None

    def reset(self) -> None:
        """Reset the endpoint statistics."""
        self.stats = internal.create_endpoint_stats(self.config)
        self.info = internal.create_endpoint_info(self.config)

    async def stop(self) -> None:
        """Stop the endpoint by draining its subscription."""
        if self._sub:
            await self._sub.drain()
            self._sub = None


class Group:
    """Group allows for grouping endpoints on a service.

    Endpoints created using `Group.add_endpoint` will be grouped
    under common prefix (group name). New groups can also be derived
    from a group using `Group.add_group`.
    """

    def __init__(self, config: internal.GroupConfig, service: Service) -> None:
        self._config = config
        self._service = service

    def add_group(
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
        """Add an endpoint to the group.

        Args:
            name: The name of the endpoint.
            handler: The handler of the endpoint.
            subject: The subject of the endpoint. When subject is not set, it defaults to the name of the endpoint.
            queue_group: The queue group of the endpoint. When queue group is not set, it defaults to the queue group of the parent group or service.
            metadata: The metadata of the endpoint.
            pending_bytes_limit: The pending bytes limit for this endpoint.
            pending_msgs_limit: The pending messages limit for this endpoint.
        """
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
    """Services simplify the development of NATS micro-services.

    Endpoints can be added to a service after it has been created and started.
    Each endpoint is a request-reply handler for a subject.

    Groups can be added to a service to group endpoints under a common prefix.
    """

    def __init__(
        self,
        nc: NatsClient,
        id: str,
        config: internal.ServiceConfig,
        api_prefix: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._nc = nc
        self._config = config
        self._api_prefix = api_prefix
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        # Initialize state
        self._id = id
        self._endpoints: list[Endpoint] = []
        self._stopped = False
        # Internal responses
        self._stats = internal.new_service_stats(self._id, self._clock(), config)
        self._info = internal.new_service_info(self._id, config)
        self._ping_response = internal.new_ping_info(self._id, config)
        # Cache the serialized ping response
        self._ping_response_message = dumps(asdict(self._ping_response)).encode()
        # Internal subscriptions
        self._ping_subscriptions: list[Subscription] = []
        self._info_subscriptions: list[Subscription] = []
        self._stats_subscriptions: list[Subscription] = []

    async def start(self) -> None:
        """Start the service.

        A service MUST be started before adding endpoints.

        This will start the internal subscriptions and enable
        service discovery.
        """
        for subject in internal.get_internal_subjects(
            internal.ServiceVerb.PING,
            self._id,
            self._config,
            api_prefix=self._api_prefix,
        ):
            sub = await self._nc.subscribe(  # pyright: ignore[reportUnknownMemberType]
                subject,
                cb=self._handle_ping_request,
            )
            self._ping_subscriptions.append(sub)

        for subject in internal.get_internal_subjects(
            internal.ServiceVerb.INFO,
            self._id,
            self._config,
            api_prefix=self._api_prefix,
        ):
            sub = await self._nc.subscribe(  # pyright: ignore[reportUnknownMemberType]
                subject,
                cb=self._handle_info_request,
            )
            self._info_subscriptions.append(sub)

        for subject in internal.get_internal_subjects(
            internal.ServiceVerb.STATS,
            self._id,
            self._config,
            api_prefix=self._api_prefix,
        ):
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

    def stopped(self) -> bool:
        """Stopped informs whether [Stop] was executed on the service."""
        return self._stopped

    def info(self) -> ServiceInfo:
        """Returns the service info."""
        return self._info.copy()

    def stats(self) -> ServiceStats:
        """Returns statistics for the service endpoint and all monitoring endpoints."""
        return self._stats.copy()

    def reset(self) -> None:
        """Resets all statistics (for all endpoints) on a service instance."""
        # Internal responses
        self._stats = internal.new_service_stats(self._id, self._clock(), self._config)
        self._info = internal.new_service_info(self._id, self._config)
        self._ping_response = internal.new_ping_info(self._id, self._config)
        self._ping_response_message = internal.encode_ping_info(self._ping_response)
        # Reset all endpoints
        for ep in self._endpoints:
            ep.reset()
            self._endpoints.append(ep)
            self._stats.endpoints.append(ep.stats)
            self._info.endpoints.append(ep.info)

    def add_group(
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
        config = internal.GroupConfig(
            name=name,
            queue_group=queue_group or self._config.queue_group,
            pending_bytes_limit_by_endpoint=pending_bytes_limit_by_endpoint
            or self._config.pending_bytes_limit_by_endpoint,
            pending_msgs_limit_by_endpoint=pending_msgs_limit_by_endpoint
            or self._config.pending_msgs_limit_by_endpoint,
        )
        return Group(config, self)

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
        # Create the endpoint
        ep = Endpoint(config)
        # Create the endpoint handler
        subscription_handler = _create_handler(ep)
        # Start the endpoint subscription
        subscription = (
            await self._nc.subscribe(  # pyright: ignore[reportUnknownMemberType]
                config.subject,
                queue=config.queue_group,
                cb=subscription_handler,
            )
        )
        # Attach the subscription to the endpoint
        ep._sub = subscription  # pyright: ignore[reportPrivateUsage]
        # Append the endpoint to the service
        self._endpoints.append(ep)
        # Append the endpoint to the service stats and info
        self._stats.endpoints.append(ep.stats)
        self._info.endpoints.append(ep.info)
        return ep

    async def _handle_ping_request(self, msg: Msg) -> None:
        """Handle the ping message."""
        await msg.respond(data=self._ping_response_message)

    async def _handle_info_request(self, msg: Msg) -> None:
        """Handle the info message."""
        await msg.respond(data=internal.encode_info(self._info))

    async def _handle_stats_request(self, msg: Msg) -> None:
        """Handle the stats message."""
        await msg.respond(data=internal.encode_stats(self._stats))

    async def __aenter__(self) -> Service:
        """Implement the asynchronous context manager interface."""
        await self.start()
        return self

    async def __aexit__(self, *args: object, **kwargs: object) -> None:
        """Implement the asynchronous context manager interface."""
        await self.stop()


def _create_handler(endpoint: Endpoint) -> Callable[[Msg], Awaitable[None]]:
    """A helper function called internally to create endpoint message handlers."""

    async def handler(msg: Msg) -> None:
        timer = internal.Timer()
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
