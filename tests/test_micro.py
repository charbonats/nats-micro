from __future__ import annotations

import contextlib
import datetime
from typing import AsyncIterator

import pytest
import pytest_asyncio
from nats.aio.client import Client as NATS
from nats_contrib.test_server import NATSD

from nats_contrib import micro
from nats_contrib.micro.client import MicroClient


@pytest.mark.asyncio
class MicroTestSetup:
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, nats_server: NATSD, nats_client: NATS) -> AsyncIterator[None]:
        self.nats_server = nats_server
        self.nats_client = nats_client
        self.micro_client = MicroClient(nats_client)
        self.test_stack = contextlib.AsyncExitStack()
        async with self.test_stack:
            yield None

    def now(self) -> datetime.datetime:
        return datetime.datetime(1970, 1, 1)

    def service_id(self) -> str:
        return "123456789"

    def service_name(self) -> str:
        return "service1"

    def service_version(self) -> str:
        return "0.0.1"


class TestMicro(MicroTestSetup):
    async def test_ping(self) -> None:
        expected = micro.models.PingInfo(
            id=self.service_id(),
            name=self.service_name(),
            version=self.service_version(),
            metadata={},
            type="io.nats.micro.v1.ping_response",
        )
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            generate_id=self.service_id,
        ):
            results = await self.micro_client.ping(max_count=1)
            assert results == [expected]
            results = await self.micro_client.ping(
                service=self.service_name(), max_count=1
            )
            assert results == [expected]
            results = await self.micro_client.service(self.service_name()).ping(
                max_count=1
            )
            assert results == [expected]
            result = (
                await self.micro_client.service(self.service_name())
                .instance(self.service_id())
                .ping()
            )
            assert result == expected

    async def test_info(self) -> None:
        expected = micro.ServiceInfo(
            id=self.service_id(),
            name=self.service_name(),
            version=self.service_version(),
            description="",
            endpoints=[],
            metadata={},
            type="io.nats.micro.v1.info_response",
        )
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            generate_id=self.service_id,
        ):
            results = await self.micro_client.info(max_count=1)
            assert results == [expected]
            # Save instance id
            results = await self.micro_client.info(
                service=self.service_name(), max_count=1
            )
            assert results == [expected]
            results = await self.micro_client.service(self.service_name()).info(
                max_count=1
            )
            assert results == [expected]
            result = (
                await self.micro_client.service(self.service_name())
                .instance(self.service_id())
                .info()
            )
            assert result == expected

    async def test_stats(self) -> None:
        expected = micro.ServiceStats(
            name=self.service_name(),
            version=self.service_version(),
            id=self.service_id(),
            endpoints=[],
            metadata={},
            type="io.nats.micro.v1.stats_response",
            started="1970-01-01T00:00:00",
        )
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            generate_id=self.service_id,
            now=self.now,
        ):
            results = await self.micro_client.stats(max_count=1)
            assert results == [expected]
            # Save instance id
            results = await self.micro_client.stats(
                service=self.service_name(), max_count=1
            )
            assert results == [expected]
            results = await self.micro_client.service(self.service_name()).stats(
                max_count=1
            )
            assert results == [expected]
            result = (
                await self.micro_client.service(self.service_name())
                .instance(self.service_id())
                .stats()
            )
            assert result == expected


class TestMicroEndpoint(MicroTestSetup):
    async def handler(self, request: micro.Request) -> None:
        await request.respond(b"OK")

    async def test_info(self) -> None:
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            now=self.now,
            generate_id=self.service_id,
        ) as service:
            await service.add_endpoint(
                "endpoint1",
                self.handler,
            )
            result = (
                await self.micro_client.service(self.service_name())
                .instance(self.service_id())
                .info()
            )
            assert result == micro.ServiceInfo(
                id=self.service_id(),
                name=self.service_name(),
                version=self.service_version(),
                description="",
                endpoints=[
                    micro.EndpointInfo(
                        name="endpoint1",
                        subject="endpoint1",
                        queue_group="q",
                        metadata={},
                    )
                ],
                metadata={},
                type="io.nats.micro.v1.info_response",
            )

    async def test_stats(self) -> None:
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            now=self.now,
            generate_id=self.service_id,
        ) as service:
            await service.add_endpoint(
                "endpoint1",
                self.handler,
            )
            result = (
                await self.micro_client.service(self.service_name())
                .instance(self.service_id())
                .stats()
            )
            assert result == micro.ServiceStats(
                name=self.service_name(),
                version=self.service_version(),
                id=self.service_id(),
                endpoints=[
                    micro.EndpointStats(
                        name="endpoint1",
                        subject="endpoint1",
                        queue_group="q",
                        num_errors=0,
                        num_requests=0,
                        last_error="",
                        processing_time=0,
                        average_processing_time=0,
                        data={},
                    )
                ],
                metadata={},
                type="io.nats.micro.v1.stats_response",
                started="1970-01-01T00:00:00",
            )


class TestMicroEndpointWithSubject(MicroTestSetup):
    async def handler(self, request: micro.Request) -> None:
        await request.respond(b"OK")

    async def test_info(self) -> None:
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            now=self.now,
            generate_id=self.service_id,
        ) as service:
            await service.add_endpoint(
                "endpoint1",
                self.handler,
                subject="other",
            )
            result = (
                await self.micro_client.service(self.service_name())
                .instance(self.service_id())
                .info()
            )
            assert result == micro.ServiceInfo(
                id=self.service_id(),
                name=self.service_name(),
                version=self.service_version(),
                description="",
                endpoints=[
                    micro.EndpointInfo(
                        name="endpoint1",
                        subject="other",
                        queue_group="q",
                        metadata={},
                    )
                ],
                metadata={},
                type="io.nats.micro.v1.info_response",
            )

    async def test_stats(self) -> None:
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            now=self.now,
            generate_id=self.service_id,
        ) as service:
            await service.add_endpoint(
                "endpoint1",
                self.handler,
                subject="other",
            )
            result = (
                await self.micro_client.service(self.service_name())
                .instance(self.service_id())
                .stats()
            )
            assert result == micro.ServiceStats(
                name=self.service_name(),
                version=self.service_version(),
                id=self.service_id(),
                endpoints=[
                    micro.EndpointStats(
                        name="endpoint1",
                        subject="other",
                        queue_group="q",
                        num_errors=0,
                        num_requests=0,
                        last_error="",
                        processing_time=0,
                        average_processing_time=0,
                        data={},
                    )
                ],
                metadata={},
                type="io.nats.micro.v1.stats_response",
                started="1970-01-01T00:00:00",
            )


class TestMicroGroup(MicroTestSetup):
    async def handler(self, request: micro.Request) -> None:
        await request.respond(b"OK")

    async def test_info(self) -> None:
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            now=self.now,
            generate_id=self.service_id,
        ) as service:
            group = service.add_group("group1", queue_group="q1")
            await group.add_endpoint(
                "endpoint1",
                self.handler,
            )
            result = (
                await self.micro_client.service(self.service_name())
                .instance(self.service_id())
                .info()
            )
            assert result == micro.ServiceInfo(
                id=self.service_id(),
                name=self.service_name(),
                version=self.service_version(),
                description="",
                endpoints=[
                    micro.EndpointInfo(
                        name="endpoint1",
                        subject="group1.endpoint1",
                        queue_group="q1",
                        metadata={},
                    )
                ],
                metadata={},
                type="io.nats.micro.v1.info_response",
            )

    async def test_stats(self) -> None:
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            now=self.now,
            generate_id=self.service_id,
        ) as service:
            group = service.add_group("group1", queue_group="q1")
            await group.add_endpoint(
                "endpoint1",
                self.handler,
            )
            result = (
                await self.micro_client.service(self.service_name())
                .instance(self.service_id())
                .stats()
            )
            assert result == micro.ServiceStats(
                name=self.service_name(),
                version=self.service_version(),
                id=self.service_id(),
                endpoints=[
                    micro.EndpointStats(
                        name="endpoint1",
                        subject="group1.endpoint1",
                        queue_group="q1",
                        num_errors=0,
                        num_requests=0,
                        last_error="",
                        processing_time=0,
                        average_processing_time=0,
                        data={},
                    )
                ],
                metadata={},
                type="io.nats.micro.v1.stats_response",
                started="1970-01-01T00:00:00",
            )
