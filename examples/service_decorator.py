from __future__ import annotations

from nats_contrib import micro


@micro.sdk.service(
    name="echo-service",
    version="1.0.0",
    description="Echo service",
    metadata={"author": "me"},
)
class EchoService:
    """An example micro service."""

    some_configuration: str

    @micro.sdk.endpoint(
        name="echo",
        subject="demo.ECHO",
        pending_msgs_limit=100,
        pending_bytes_limit=1000,
    )
    async def something(self, msg: micro.Request) -> None:
        """Reply same content as received message."""
        await msg.respond(
            data=msg.data(),
            headers={
                "X-My-Header": self.some_configuration,
            },
        )


async def setup(ctx: micro.sdk.Context) -> None:
    """Configure the service."""

    await ctx.register_service(
        EchoService(some_configuration="some value"),
    )
