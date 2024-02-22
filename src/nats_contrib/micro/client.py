from __future__ import annotations

import json
from typing import AsyncContextManager, AsyncIterator

from nats.aio.client import Client as NATS
from nats_contrib.request_many import (
    RequestManyExecutor,
    RequestManyIterator,
    transform,
)

from . import internal
from .api import API_PREFIX
from .models import PingInfo, ServiceInfo, ServiceStats


class ServiceError(Exception):
    """Raised when a service error is received."""

    def __init__(self, code: int, description: str) -> None:
        super().__init__(f"Service error {code}: {description}")
        self.code = code
        self.description = description


class Client:

    def __init__(
        self,
        nc: NATS,
        default_max_wait: float = 0.5,
        api_prefix: str = API_PREFIX,
    ) -> None:
        self.nc = nc
        self.api_prefix = api_prefix
        self.request_executor = RequestManyExecutor(nc, default_max_wait)

    async def request(
        self,
        subject: str,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 1,
    ) -> bytes:
        """Send a request and get the response."""
        response = await self.nc.request(
            subject, data or b"", headers=headers, timeout=timeout
        )
        if response.headers:
            error_code = response.headers.get("Nats-Service-Error-Code")
            if error_code:
                raise ServiceError(
                    int(error_code), response.headers.get("Nats-Service-Error", "")
                )

        return response.data

    async def ping(
        self,
        service: str | None = None,
        max_wait: float | None = None,
        max_count: int | None = None,
        max_interval: float | None = None,
    ) -> list[PingInfo]:
        """Ping all the services."""
        subject = internal.get_internal_subject(
            internal.ServiceVerb.PING, service, None, self.api_prefix
        )
        responses = await self.request_executor(
            subject,
            max_count=max_count,
            max_wait=max_wait,
            max_interval=max_interval,
        )
        return [PingInfo.from_response(json.loads(res.data)) for res in responses]

    async def info(
        self,
        service: str | None = None,
        max_wait: float | None = None,
        max_count: int | None = None,
        max_interval: float | None = None,
    ) -> list[ServiceInfo]:
        """Get all service informations."""
        subject = internal.get_internal_subject(
            internal.ServiceVerb.INFO, service, None, self.api_prefix
        )
        responses = await self.request_executor(
            subject,
            max_count=max_count,
            max_wait=max_wait,
            max_interval=max_interval,
        )
        return [ServiceInfo.from_response(json.loads(res.data)) for res in responses]

    async def stats(
        self,
        service: str | None = None,
        max_wait: float | None = None,
        max_count: int | None = None,
        max_interval: float | None = None,
    ) -> list[ServiceStats]:
        """Get all services stats."""
        subject = internal.get_internal_subject(
            internal.ServiceVerb.STATS, service, None, self.api_prefix
        )
        responses = await self.request_executor(
            subject,
            max_count=max_count,
            max_wait=max_wait,
            max_interval=max_interval,
        )
        return [ServiceStats.from_response(json.loads(res.data)) for res in responses]

    def aping(
        self,
        service: str | None = None,
        max_wait: float | None = None,
        max_count: int | None = None,
        max_interval: float | None = None,
    ) -> AsyncContextManager[AsyncIterator[PingInfo]]:
        """Ping all the services."""
        subject = internal.get_internal_subject(
            internal.ServiceVerb.PING, service, None, self.api_prefix
        )
        return transform(
            RequestManyIterator(
                self.nc,
                subject,
                inbox=self.nc.new_inbox(),
                max_count=max_count,
                max_wait=max_wait,
                max_interval=max_interval,
            ),
            lambda res: PingInfo.from_response(json.loads(res.data)),
        )

    def ainfo(
        self,
        service: str | None = None,
        max_wait: float | None = None,
        max_count: int | None = None,
        max_interval: float | None = None,
    ) -> AsyncContextManager[AsyncIterator[ServiceInfo]]:
        """Get all service informations."""
        subject = internal.get_internal_subject(
            internal.ServiceVerb.INFO, service, None, self.api_prefix
        )
        return transform(
            RequestManyIterator(
                self.nc,
                subject,
                inbox=self.nc.new_inbox(),
                max_count=max_count,
                max_wait=max_wait,
                max_interval=max_interval,
            ),
            lambda res: ServiceInfo.from_response(json.loads(res.data)),
        )

    def astats(
        self,
        service: str | None = None,
        max_wait: float | None = None,
        max_count: int | None = None,
        max_interval: float | None = None,
    ) -> AsyncContextManager[AsyncIterator[ServiceStats]]:
        """Get all services stats."""
        subject = internal.get_internal_subject(
            internal.ServiceVerb.STATS, service, None, self.api_prefix
        )
        return transform(
            RequestManyIterator(
                self.nc,
                subject,
                inbox=self.nc.new_inbox(),
                max_count=max_count,
                max_wait=max_wait,
                max_interval=max_interval,
            ),
            lambda res: ServiceStats.from_response(json.loads(res.data)),
        )

    def service(self, service: str) -> Service:
        """Get a client for a single service."""
        return self.Service(self, service)

    class Service:
        def __init__(self, client: Client, service: str) -> None:
            self.client = client
            self.service = service

        async def ping(
            self,
            max_wait: float | None = None,
            max_count: int | None = None,
            max_interval: float | None = None,
        ) -> list[PingInfo]:
            """Ping all the service instances."""
            return await self.client.ping(
                self.service, max_wait, max_count, max_interval
            )

        async def info(
            self,
            max_wait: float | None = None,
            max_count: int | None = None,
            max_interval: float | None = None,
        ) -> list[ServiceInfo]:
            """Get all service instance informations."""
            return await self.client.info(
                self.service, max_wait, max_count, max_interval
            )

        async def stats(
            self,
            max_wait: float | None = None,
            max_count: int | None = None,
            max_interval: float | None = None,
        ) -> list[ServiceStats]:
            """Get all service instance stats."""
            return await self.client.stats(
                self.service, max_wait, max_count, max_interval
            )

        def aping(
            self,
            max_wait: float | None = None,
            max_count: int | None = None,
            max_interval: float | None = None,
        ) -> AsyncContextManager[AsyncIterator[PingInfo]]:
            """Ping all the service instances."""
            return self.client.aping(self.service, max_wait, max_count, max_interval)

        def ainfo(
            self,
            max_wait: float | None = None,
            max_count: int | None = None,
            max_interval: float | None = None,
        ) -> AsyncContextManager[AsyncIterator[ServiceInfo]]:
            """Get all service instance informations."""
            return self.client.ainfo(self.service, max_wait, max_count, max_interval)

        def astats(
            self,
            max_wait: float | None = None,
            max_count: int | None = None,
            max_interval: float | None = None,
        ) -> AsyncContextManager[AsyncIterator[ServiceStats]]:
            """Get all service instance stats."""
            return self.client.astats(self.service, max_wait, max_count, max_interval)

        def instance(self, id: str) -> Client.Instance:
            """Get a client for a single service instance."""
            return Client.Instance(self.client, self.service, id)

    class Instance:
        def __init__(self, client: Client, service: str, id: str) -> None:
            self.client = client
            self.service = service
            self.id = id

        async def ping(
            self,
            timeout: float = 0.5,
        ) -> PingInfo:
            """Ping a service instance."""
            subject = internal.get_internal_subject(
                internal.ServiceVerb.PING, self.service, self.id, self.client.api_prefix
            )
            response = await self.client.nc.request(subject, b"", timeout=timeout)
            return PingInfo.from_response(json.loads(response.data))

        async def info(
            self,
            timeout: float = 0.5,
        ) -> ServiceInfo:
            """Get the service instance information."""
            subject = internal.get_internal_subject(
                internal.ServiceVerb.INFO, self.service, self.id, self.client.api_prefix
            )
            response = await self.client.nc.request(subject, b"", timeout=timeout)
            return ServiceInfo.from_response(json.loads(response.data))

        async def stats(
            self,
            timeout: float = 0.5,
        ) -> ServiceStats:
            """Get the service instance stats."""
            subject = internal.get_internal_subject(
                internal.ServiceVerb.STATS,
                self.service,
                self.id,
                self.client.api_prefix,
            )
            response = await self.client.nc.request(subject, b"", timeout=timeout)
            return ServiceStats.from_response(json.loads(response.data))
