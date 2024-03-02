from __future__ import annotations

from nats_contrib import asyncapi

from my_endpoint import MyEndpoint, MyRequest


async def request(
    client: asyncapi.Client,
) -> None:
    """An example function to send a request to a micro service."""
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
