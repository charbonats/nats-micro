from __future__ import annotations

import contextlib
import datetime
from typing import AsyncIterator

import pytest
import pytest_asyncio
from nats.aio.client import Client as NATS
from nats_contrib.test_server import NATSD

from nats_contrib import micro
from nats_contrib.micro import testing


@pytest.mark.asyncio
class MicroTestSetup:
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, nats_server: NATSD, nats_client: NATS) -> AsyncIterator[None]:
        self.nats_server = nats_server
        self.nats_client = nats_client
        self.micro_client = micro.Client(nats_client)
        self.test_stack = contextlib.AsyncExitStack()
        self.exception_to_raise = ValueError("error")
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

    async def handler(self, request: micro.Request) -> None:
        await request.respond(b"OK")

    async def handler_with_error(self, request: micro.Request) -> None:
        raise self.exception_to_raise

    def make_handler(
        self,
        subject: str,
        payload: bytes | None = None,
        headers: dict[str, str] | None = None,
        response: bytes | None = None,
        response_headers: dict[str, str] | None = None,
    ) -> micro.Handler:
        async def handler(request: micro.Request) -> None:
            assert request.subject() == subject
            assert request.data() == payload
            assert request.headers() == headers
            await request.respond(response or b"", response_headers)

        return handler


@pytest.mark.asyncio
class TestRequestStub:
    async def test_respond(self) -> None:

        async def respond_and_assert(request: micro.Request) -> None:
            assert request.data() == b"the-paylaod"
            assert request.headers() == {"the": "header"}
            assert request.subject() == "the-subject"
            await request.respond(b"the-response", {"the": "response-header"})

        request = testing.make_request("the-subject", b"the-paylaod", {"the": "header"})
        await respond_and_assert(request)
        assert request.response_data() == b"the-response"
        assert request.response_headers() == {"the": "response-header"}

    async def test_respond_with_error(self) -> None:

        async def respond_and_assert(request: micro.Request) -> None:
            assert request.data() == b"the-paylaod"
            assert request.headers() == {"the": "header"}
            assert request.subject() == "the-subject"
            await request.respond_error(
                400, "bad request", headers={"the": "response-header"}
            )

        request = testing.make_request("the-subject", b"the-paylaod", {"the": "header"})
        await respond_and_assert(request)
        assert request.response_data() == b""
        assert request.response_headers() == {
            "Nats-Service-Error-Code": "400",
            "Nats-Service-Error": "bad request",
            "the": "response-header",
        }

    @pytest.mark.parametrize("headers,", [None, {}, {"the": "response-header"}])
    async def test_respond_with_success(self, headers: dict[str, str] | None) -> None:

        async def respond_and_assert(request: micro.Request) -> None:
            assert request.data() == b"the-paylaod"
            assert request.headers() == {"the": "header"}
            assert request.subject() == "the-subject"
            await request.respond_success(200, b"the-response", headers=headers)

        request = testing.make_request("the-subject", b"the-paylaod", {"the": "header"})
        await respond_and_assert(request)
        assert request.response_data() == b"the-response"
        assert request.response_headers() == {
            "Nats-Service-Success-Code": "200",
            **(headers if headers else {}),
        }


class TestMicroRequest(MicroTestSetup):
    async def test_nats_request(self) -> None:
        handler = self.make_handler(
            "the-subject",
            b"the-payload",
            {"the": "header"},
            b"the-response",
            {"the": "response-header"},
        )
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            generate_id=self.service_id,
        ) as service:
            await service.add_endpoint("the-subject", handler)
            result = await self.nats_client.request(
                "the-subject", b"the-payload", headers={"the": "header"}
            )
            assert result.data == b"the-response"
            assert result.headers == {"the": "response-header"}


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
            result = await self.micro_client.instance(
                self.service_name(), self.service_id()
            ).ping()
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
            result = await self.micro_client.instance(
                self.service_name(), self.service_id()
            ).info()
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
            result = await self.micro_client.instance(
                self.service_name(), self.service_id()
            ).stats()
            assert result == expected

    async def test_info_getter(self) -> None:
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            generate_id=self.service_id,
        ) as service:
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
                endpoints=[],
                metadata={},
                type="io.nats.micro.v1.info_response",
            )
            assert result == service.info()

    async def test_stats_getter(self) -> None:
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            generate_id=self.service_id,
            now=self.now,
        ) as service:
            result = (
                await self.micro_client.service(self.service_name())
                .instance(self.service_id())
                .stats()
            )
            assert result == micro.ServiceStats(
                name=self.service_name(),
                version=self.service_version(),
                id=self.service_id(),
                endpoints=[],
                metadata={},
                type="io.nats.micro.v1.stats_response",
                started="1970-01-01T00:00:00",
            )
            assert result == service.stats()

    async def test_reset_after_request(self) -> None:
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            generate_id=self.service_id,
        ) as service:
            await service.add_endpoint(
                "endpoint1",
                lambda request: request.respond(b"OK"),
            )
            await self.micro_client.request("endpoint1", b"")
            result = (
                await self.micro_client.service(self.service_name())
                .instance(self.service_id())
                .stats()
            )
            assert result.endpoints[0].num_requests == 1
            service._clock = lambda: datetime.datetime(1970, 1, 2)
            service.reset()
            result = (
                await self.micro_client.service(self.service_name())
                .instance(self.service_id())
                .stats()
            )
            assert result.endpoints[0].num_requests == 0
            assert result.started == "1970-01-02T00:00:00"

    async def test_stopped_after_request(self) -> None:
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            generate_id=self.service_id,
        ) as service:
            await service.add_endpoint(
                "endpoint1",
                lambda request: request.respond(b"OK"),
            )
            await self.micro_client.request("endpoint1", b"")
            result = (
                await self.micro_client.service(self.service_name())
                .instance(self.service_id())
                .stats()
            )
            assert result.endpoints[0].num_requests == 1
            service._clock = lambda: datetime.datetime(1970, 1, 2)
            await service.stop()
            results = await self.micro_client.stats(max_count=1, max_wait=0.1)
            assert results == []

    async def test_start_then_stopped(self) -> None:
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            generate_id=self.service_id,
        ) as service:
            assert not service.stopped()
            await service.stop()
            assert service.stopped()
            with pytest.raises(RuntimeError) as exc:
                await service.add_endpoint("endpoint1", self.handler)
            assert str(exc.value) == "Cannot add endpoint to a stopped service"


class TestMicroClientIterators(MicroTestSetup):
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
            async with self.micro_client.ping_iter() as replies:
                pongs = [pong async for pong in replies]
            assert pongs == [expected]
            async with self.micro_client.service(
                self.service_name()
            ).ping_iter() as replies:
                pongs = [pong async for pong in replies]
            assert pongs == [expected]

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
            async with self.micro_client.info_iter() as replies:
                infos = [info async for info in replies]
            assert infos == [expected]
            async with self.micro_client.service(
                self.service_name()
            ).info_iter() as replies:
                infos = [info async for info in replies]
            assert infos == [expected]

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
            async with self.micro_client.stats_iter() as replies:
                stats = [stat async for stat in replies]
            assert stats == [expected]
            async with self.micro_client.service(
                self.service_name()
            ).stats_iter() as replies:
                stats = [stat async for stat in replies]
            assert stats == [expected]


class TestMicroEndpoint(MicroTestSetup):

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

    async def test_handler(self) -> None:
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
            result = await self.nats_client.request("endpoint1", b"")
            assert result.data == b"OK"

    async def test_handler_stats(self) -> None:
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
            await self.nats_client.request("endpoint1", b"")
            result = (
                await self.micro_client.service(self.service_name())
                .instance(self.service_id())
                .stats()
            )
            assert result.endpoints[0].num_requests == 1
            assert result.endpoints[0].num_errors == 0
            assert result.endpoints[0].processing_time > 0
            assert result.endpoints[0].average_processing_time > 0

    async def test_handler_with_error(self) -> None:
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            now=self.now,
            generate_id=self.service_id,
        ) as service:
            await service.add_endpoint(
                "endpoint1",
                self.handler_with_error,
            )
            with pytest.raises(micro.ServiceError) as exc_info:
                await self.micro_client.request("endpoint1", b"")
            assert exc_info.value.code == 500
            assert exc_info.value.description == "Internal Server Error"

    async def test_handler_with_error_stats(self) -> None:
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            now=self.now,
            generate_id=self.service_id,
        ) as service:
            await service.add_endpoint(
                "endpoint1",
                self.handler_with_error,
            )
            with pytest.raises(micro.ServiceError):
                await self.micro_client.request("endpoint1", b"")
            result = (
                await self.micro_client.service(self.service_name())
                .instance(self.service_id())
                .stats()
            )
            assert result.endpoints[0].num_requests == 1
            assert result.endpoints[0].num_errors == 1
            assert result.endpoints[0].last_error == "ValueError('error')"
            assert result.endpoints[0].processing_time > 0
            assert result.endpoints[0].average_processing_time > 0


class TestMicroEndpointWithSubject(MicroTestSetup):

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


class TestMicroGroupWithSubgroup(MicroTestSetup):

    async def test_info(self) -> None:
        async with micro.add_service(
            self.nats_client,
            self.service_name(),
            self.service_version(),
            now=self.now,
            generate_id=self.service_id,
        ) as service:
            group = service.add_group("group1", queue_group="q1")
            subgroup = group.add_group("group2", queue_group="q2")
            await subgroup.add_endpoint(
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
                        subject="group1.group2.endpoint1",
                        queue_group="q2",
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
            subgroup = group.add_group("group2", queue_group="q2")
            await subgroup.add_endpoint(
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
                        subject="group1.group2.endpoint1",
                        queue_group="q2",
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
