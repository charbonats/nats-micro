"""Minimal example of NATS micro usage."""

from nats_contrib import micro


@micro.sdk.group(name="demo")
class DemoEndpoints:
    """A group of endpoints."""

    @micro.sdk.endpoint(subject="ECHO")
    async def echo(self, req: micro.Request) -> None:
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
    print("Configuring service")
    # Register the group
    await ctx.register_group(service, DemoEndpoints())
    print("Service is ready to accept requests")
