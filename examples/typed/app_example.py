from __future__ import annotations

import logging

from nats_contrib import micro
from nats_contrib.micro.typedsdk import mount

from my_endpoint_implementation import MyEndpointImplementation
from my_service import my_service


logger = logging.getLogger("micro")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def setup(ctx: micro.sdk.Context) -> None:
    """An example setup function to start a micro service."""

    # Push a function to be called when the service is stopped
    ctx.push(lambda: logger.warning("Exiting the service"))

    logger.info("Configuring the service")

    # Create a new service instance
    service = my_service.with_endpoints(
        MyEndpointImplementation(12),
    )

    # Mount the app
    await mount(ctx, service)

    logger.info("Service is ready and listening to requests")
