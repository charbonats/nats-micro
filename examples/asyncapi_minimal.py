from __future__ import annotations

from dataclasses import dataclass

from nats.aio.client import Client as NATS

from nats_contrib import micro, asyncapi


@dataclass
class MyParams:
    device_id: str


@dataclass
class MyRequest:
    value: int


@asyncapi.operation(
    address="foo.{device_id}",
    parameters=MyParams,
    request_schema=MyRequest,
    response_schema=int,
    error_schema=str,
    catch=[
        asyncapi.ErrorHandler(
            ValueError,
            400,
            "Bad request",
            lambda err: "Request failed due to malformed request data",
        ),
    ],
)
class MyEndpoint:
    """Test endpoint definition.

    Parameters are verified together with address on
    class definition.

    Schemas are used to verify that server implements the
    correct interface and that client sends the correct
    data and receive the correct data.
    """

    def __init__(self, constant: int) -> None:
        self.constant = constant

    async def handle(
        self,
        msg: asyncapi.Message[MyParams, MyRequest, int, str],
    ) -> None:
        """Signature is the same as the parent class."""
        # Parameters are extracted from the message subject
        params = msg.params()
        print(params.device_id)
        # Request.data() is the message payload decoded as a string
        data = msg.payload()
        print(data.value)
        # Send a reply
        await msg.respond(data.value * self.constant)
        # We could also respond with an error
        # await request.respond_error(409, "Conflict", data="Some error data")


# Example usage: App definition
# This code should be available to both the client and the server

service = asyncapi.Application(
    id="https://github.com/charbonats/nats-micro/examples/typed",
    name="test",
    version="0.0.1",
    description="Test service",
    operations=[MyEndpoint],
)

# Example usage: Server
# This code is required to "run the application" as a server


async def setup(ctx: micro.Context) -> None:
    """An example setup function to start a micro service."""
    # Mount the app
    await asyncapi.micro.add_application(ctx, service.with_endpoints(MyEndpoint(2)))


# Examle usage: Client
# This code is required to "interact with the application" as a client


async def request(
    nats_client: NATS,
) -> None:
    """An example function to send a request to a micro service."""
    # Usage:
    # 1. Create a client
    client = asyncapi.micro.Client(nats_client)
    # 2. Send a request
    # This will not raise an error if the reply received indicates
    # an error through the status code
    response = await client.send(
        MyEndpoint.request(MyRequest(value=2), "123"),
        headers={"foo": "bar"},
        timeout=2.5,
    )
    # 3. Get the data
    # This will raise an error if the reply received indicates an
    # error through the status code
    try:
        data = response.data()
        print(data)
    except asyncapi.OperationError:
        # You can access the decoded error in such case
        error = response.error()
        print(error)
    # 4. Headers can always be accessed, even if the reply is an error
    headers = response.headers()
    print(headers)
