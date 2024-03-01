from __future__ import annotations

from nats_contrib.micro.typedsdk import Application

from my_endpoint import MyEndpoint


app = Application(
    id="https://github.com/charbonats/examples/typed",
    name="typed-example",
    version="0.0.1",
    description="Test service",
    operations=[MyEndpoint],
)
