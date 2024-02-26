"""Minimal example of NATS micro usage."""

from nats_contrib.connect_opts import option

from nats_contrib import micro


async def echo(req: micro.Request) -> None:
    """Echo the request data back to the client."""
    await req.respond(req.data())


async def setup(ctx: micro.sdk.Context) -> None:
    """Configure the service.

    This function is executed after the NATS connection is established.
    """
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
        # The setup function to call after the connection is established
        setup,
        # Add any connect option as required
        option.WithServer("nats://localhost:4222"),
        # Trap OS signals (SIGTERM/SIGINT by default)
        trap_signals=True,
    )
