"""Minimal example of NATS micro usage."""

from nats_contrib import micro
from nats_contrib.micro.middleware import NextHandler, Response


async def echo(req: micro.Request) -> None:
    """Echo the request data back to the client."""
    print("Echoing request data")
    await req.respond(req.data())


async def my_middleware(req: micro.Request, handler: NextHandler) -> Response:
    """A middleware that logs the request data."""
    print("Request data:", req.data())
    print("Request headers:", req.headers())
    response = await handler(req)
    print("Response data:", response.data())
    print("Response headers:", response.headers())
    return response


async def my_middleware2(req: micro.Request, handler: NextHandler) -> Response:
    """A middleware that logs handler usage."""
    print("Before the handler", req.data())
    response = await handler(req)
    print("After the handler", response.data())
    return response


async def setup(ctx: micro.Context) -> None:
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
    await service.add_endpoint(
        name="echo",
        subject="ECHO",
        handler=echo,
        middlewares=[
            my_middleware,
            my_middleware2,
        ],
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
