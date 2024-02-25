"""Minimal example of NATS micro usage."""

from nats_contrib import micro


async def echo(req: micro.Request) -> None:
    """Echo the request data back to the client."""
    await req.respond(req.data())


async def connect(ctx: micro.sdk.Context) -> None:
    """Connect to the NATS server."""
    # Connect to the NATS server
    await ctx.connect(servers=["nats://localhost:4222"])


async def setup(ctx: micro.sdk.Context) -> None:
    """Configure the service."""
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


if __name__ == "__main__":
    micro.sdk.run(
        connect=connect,
        setup=setup,
        trap_signals=True,
    )
