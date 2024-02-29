from __future__ import annotations

from nats_contrib.micro.typedsdk import TypedService

from my_endpoint import MyEndpoint


my_service = TypedService(
    name="test",
    version="0.0.1",
    description="Test service",
    endpoints=[MyEndpoint],
)
