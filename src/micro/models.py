from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass
class EndpointStats:
    """The statistics of an endpoint."""

    name: str
    subject: str
    num_requests: int
    num_errors: int
    last_error: str
    processing_time: int
    average_processing_time: int
    queue_group: str
    data: dict[str, object]

    def copy(self) -> EndpointStats:
        """Create a copy of the endpoint stats."""
        return replace(self, data=self.data.copy())


@dataclass
class ServiceStats:
    """The statistics of a service."""

    name: str
    id: str
    version: str
    started: str
    endpoints: list[EndpointStats]
    metadata: dict[str, str]
    type: str = "io.nats.micro.v1.stats_response"

    def copy(self) -> ServiceStats:
        """Create a copy of the service stats."""
        return replace(
            self,
            endpoints=[ep.copy() for ep in self.endpoints],
            metadata=self.metadata.copy(),
        )


@dataclass
class EndpointInfo:
    """The information of an endpoint."""

    name: str
    subject: str
    metadata: dict[str, str]
    queue_group: str

    def copy(self) -> EndpointInfo:
        """Create a copy of the endpoint info."""
        return replace(self, metadata=self.metadata.copy())


@dataclass
class ServiceInfo:
    """The information of a service."""

    name: str
    id: str
    version: str
    description: str
    metadata: dict[str, str]
    endpoints: list[EndpointInfo]
    data: dict[str, object]
    type: str = "io.nats.micro.v1.info_response"

    def copy(self) -> ServiceInfo:
        """Create a copy of the service info."""
        return replace(
            self,
            endpoints=[ep.copy() for ep in self.endpoints],
            metadata=self.metadata.copy(),
            data=self.data.copy(),
        )


@dataclass
class PingInfo:
    """The response to a ping message."""

    name: str
    id: str
    version: str
    metadata: dict[str, str]
    type: str = "io.nats.micro.v1.ping_response"
