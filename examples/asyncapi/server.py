from __future__ import annotations

import logging

from nats_contrib import micro, asyncapi


from my_endpoint_implementation import MyEndpointImplementation

from app import app


logger = logging.getLogger("app")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def setup(ctx: micro.Context) -> None:
    """An example setup function to start a micro service."""

    # Push a function to be called when the service is stopped
    ctx.push(lambda: logger.warning("Exiting the service"))

    logger.info("Configuring the service")

    # Mount the app
    await asyncapi.micro.add_application(
        ctx,
        app=app.with_endpoints(
            MyEndpointImplementation(12),
        ),
        http_port=8000,
    )

    logger.info("Service is ready and listening to requests")
