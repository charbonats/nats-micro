from __future__ import annotations

import logging
from dataclasses import dataclass

from my_endpoint import MyEndpointRequest, MyEndpoint, MyResponse


logger = logging.getLogger("my-endpoint")


@dataclass
class MyEndpointImplementation(MyEndpoint):
    """An implementation of the MyEndpoint.

    Usage of @dataclass is purely optional.
    Endpoint implementation only needs to inherit from the endpoint class.
    """

    foo: int

    async def handle(self, request: MyEndpointRequest) -> None:
        """Signature is constrained by endpoint definition."""

        # Parameters are extracted from the message subject
        params = request.params()
        logger.debug(f"Received request for device: {params.device_id}")

        # Request.data() is the message payload decoded as a string
        data = request.data()
        logger.debug(f"Request data is: {data}")

        # Reply to the request
        await request.respond(MyResponse(result=data.value + self.foo))
        # We could also respond with an error
        # await request.respond_error(409, "Conflict", data="Some error data")
