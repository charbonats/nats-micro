from __future__ import annotations

from dataclasses import dataclass

from nats_contrib.micro.typedsdk.client import Client
from nats_contrib.micro.typedsdk.endpoint import endpoint


@endpoint(
    address="foo",
    parameters=type(None),
    request_schema=str,
    response_schema=type(None),
    error_schema=str,
)
class Test:
    """Test endpoint definition."""


@dataclass
class TestImplementation(Test):
    """An implementation of the Test endpoint."""

    foo: int

    async def handle(self, params: None, request: str) -> int:
        """Signature is the same as the parent class."""
        return 42 + self.foo


async def request() -> None:
    client = Client()
    response = await client.send(Test.request("hello"))
    data = response.data
    headers = response.headers
    print(data, headers)
