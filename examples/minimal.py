"""Minimal example of NATS micro usage."""

from nats_contrib import micro
from nats_contrib.connect_opts import option


async def echo(req: micro.Request) -> None:
    """Echo the request data back to the client."""
    print("Echoing request data")
    await req.respond(req.data())


async def setup(ctx: micro.sdk.Context) -> None:
    """Configure the service.

    This function is executed after the NATS connection is established.
    """
    print("Connected to NATS")
    # Connect to NATS and close it when the context is closed
    # micro.add_service returns an AsyncContextManager that will
    # start the service when entered and stop it when exited.
    service = await ctx.add_service(
        name="demo-service",
        version="1.0.0",
        description="Demo service",
    )
    # A group is a collection of endpoints with
    # the same subject prefix.
    group = service.add_group("demo")
    # Add an endpoint to the service
    await group.add_endpoint(
        name="echo",
        subject="ECHO",
        handler=echo,
    )
    print("Service is ready to accept requests")


if __name__ == "__main__":
    micro.sdk.run(
        setup,
        # Use options as needed
        option.WithAllowReconnect(
            max_attempts=3,
            delay_seconds=10,
        ),
    )
