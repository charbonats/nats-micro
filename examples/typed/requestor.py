from __future__ import annotations

from nats.aio.client import Client as NATS

from nats_contrib import micro
from nats_contrib.micro.typedsdk import Client

from my_endpoint import MyEndpoint, MyRequest


async def request(
    nats_client: NATS,
) -> None:
    """An example function to send a request to a micro service."""
    # Usage:
    # 1. Create a client
    client = Client(nats_client)
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
    except micro.ServiceError:
        # You can access the decoded error in such case
        error = response.error()
        print(error)
    # 4. Headers can always be accessed, even if the reply is an error
    headers = response.headers()
    print(headers)
