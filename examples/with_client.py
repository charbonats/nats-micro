"""Minimal example of NATS micro usage."""

from nats.aio.client import Client as NATS

from nats_contrib import micro


async def echo(req: micro.Request) -> None:
    """Echo the request data back to the client."""
    await req.respond(req.data())


class App:

    def __init__(self, nc: NATS) -> None:
        self.nc = nc

    async def setup(self, ctx: micro.sdk.Context) -> None:
        """Configure the service."""
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
    # Create a new NATS client (it might be useful to pass it to other components)
    nc = NATS()
    # Create a new app instance
    app = App(nc)
    # Run the app
    micro.sdk.run(
        # The setup function to call after the connection is established
        app.setup,
        # The NATS client to use. It must not be closed or connected.
        client=nc,
        # Trap OS signals (SIGTERM/SIGINT by default)
        trap_signals=True,
    )
