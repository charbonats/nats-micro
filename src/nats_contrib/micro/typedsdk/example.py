from __future__ import annotations

from dataclasses import dataclass

from nats.aio.client import Client as NATS

from nats_contrib import micro
from nats_contrib.micro.typedsdk import Client, TypedService, endpoint, mount
from nats_contrib.micro.typedsdk.endpoint import TypedRequest

# Example usage: Common
# This code should be available to both the client and the server


@dataclass
class MyParams:
    device_id: str


@endpoint(
    address="foo.{device_id}",
    parameters=MyParams,
    request_schema=str,
    response_schema=int,
)
class MyEndpoint:
    """Test endpoint definition.

    Parameters are verified together with address on
    class definition.

    Schemas are used to verify that server implements the
    correct interface and that client sends the correct
    data and receive the correct data.
    """


service = TypedService(
    name="test",
    version="0.0.1",
    description="Test service",
    endpoints=[MyEndpoint],
)

# Example usage: Server
# This code is required to "run the application" as a server


@dataclass
class MyEndpointImplementation(MyEndpoint):
    """An implementation of the MyEndpoint."""

    foo: int

    async def handle(
        self,
        request: TypedRequest[MyParams, str, int, None],
    ) -> None:
        """Signature is the same as the parent class."""
        # Parameters are extracted from the message subject
        params = request.params()
        print(params.device_id)
        # Request.data() is the message payload decoded as a string
        value = request.data()
        print(value)
        # The returned value is sent back to the client as a reply
        # There is no way to send headers at the moment
        # There is no way to send an error at the moment (though
        # this could already be implemented using middlewares)
        await request.respond(len(value) + self.foo)


async def setup(ctx: micro.sdk.Context) -> None:
    """An example setup function to start a micro service."""
    # Register the endpoint using a valid implementation
    service.register_endpoint(MyEndpointImplementation(12))
    # Mount the app
    await mount(ctx, service)


# Examle usage: Client
# This code is required to "interact with the application" as a client


async def request(
    nats_client: NATS,
) -> None:
    """An example function to send a request to a micro service."""
    # Usage:
    # 1. Create a client
    client = Client(nats_client)
    # 2. Send a request
    response = await client.send(
        MyEndpoint.request("foo", "123"),
        headers={"foo": "bar"},
        timeout=2.5,
    )
    # 3. Get the data and headers
    data = response.data()
    headers = response.headers()
    print(data, headers)
