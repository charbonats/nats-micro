from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any, TypeVar

T = TypeVar("T", bound="Base")


@dataclass
class Base:
    @classmethod
    def from_response(cls: type[T], resp: dict[str, Any]) -> T:
        """Read the class instance from a server response.

        Unknown fields are ignored ("open-world assumption").
        """
        params = {}
        for field in fields(cls):
            if field.name in resp:
                params[field.name] = resp[field.name]
        return cls(**params)

    def as_dict(self) -> dict[str, Any]:
        """Return the object converted into an API-friendly dict."""
        result: dict[str, Any] = {}
        for field in fields(self):
            val = getattr(self, field.name)
            if val is None:
                continue
            result[field.name] = val
        return result


@dataclass
class EndpointStats(Base):
    """
    Statistics about a specific service endpoint
    """

    name: str
    """
    The endpoint name
    """
    subject: str
    """
    The subject the endpoint listens on
    """
    num_requests: int
    """
    The number of requests this endpoint received
    """
    num_errors: int
    """
    The number of errors this endpoint encountered
    """
    last_error: str
    """
    The last error the service encountered
    """
    processing_time: int
    """
    How long, in total, was spent processing requests in the handler
    """
    average_processing_time: int
    """
    The average time spent processing requests
    """
    queue_group: str | None = None
    """
    The queue group this endpoint listens on for requests
    """
    data: dict[str, object] | None = None
    """
    Additional statistics the endpoint makes available
    """

    def copy(self) -> EndpointStats:
        return replace(self, data=None if self.data is None else self.data.copy())


@dataclass
class ServiceStats(Base):
    """The statistics of a service."""

    name: str
    """
    The kind of the service. Shared by all the services that have the same name
    """
    id: str
    """
    A unique ID for this instance of a service
    """
    version: str
    """
    The version of the service
    """
    started: str
    """
    The time the service was stated in RFC3339 format
    """
    endpoints: list[EndpointStats]
    """
    Statistics for each known endpoint
    """
    metadata: dict[str, str] | None = None
    """Service metadata."""

    type: str = "io.nats.micro.v1.stats_response"

    def copy(self) -> ServiceStats:
        return replace(
            self,
            endpoints=[ep.copy() for ep in self.endpoints],
            metadata=None if self.metadata is None else self.metadata.copy(),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return the object converted into an API-friendly dict."""
        result = super().as_dict()
        result["endpoints"] = [ep.as_dict() for ep in self.endpoints]
        return result

    @classmethod
    def from_response(cls, resp: dict[str, Any]) -> ServiceStats:
        """Read the class instance from a server response.

        Unknown fields are ignored ("open-world assumption").
        """
        stats = super().from_response(resp)
        stats.endpoints = [EndpointStats.from_response(ep) for ep in resp["endpoints"]]
        return stats


@dataclass
class EndpointInfo(Base):
    """The information of an endpoint."""

    name: str
    """
    The endopoint name
    """
    subject: str
    """
    The subject the endpoint listens on
    """
    metadata: dict[str, str] | None = None
    """
    The endpoint metadata.
    """
    queue_group: str | None = None
    """
    The queue group this endpoint listens on for requests
    """

    def copy(self) -> EndpointInfo:
        return replace(
            self,
            metadata=None if self.metadata is None else self.metadata.copy(),
        )


@dataclass
class ServiceInfo(Base):
    """The information of a service."""

    name: str
    """
    The kind of the service. Shared by all the services that have the same name
    """
    id: str
    """
    A unique ID for this instance of a service
    """
    version: str
    """
    The version of the service
    """
    description: str
    """
    The description of the service supplied as configuration while creating the service
    """
    metadata: dict[str, str]
    """
    The service metadata
    """
    endpoints: list[EndpointInfo]
    """
    Information for all service endpoints
    """
    type: str = "io.nats.micro.v1.info_response"

    def copy(self) -> ServiceInfo:
        return replace(
            self,
            endpoints=[ep.copy() for ep in self.endpoints],
            metadata=self.metadata.copy(),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return the object converted into an API-friendly dict."""
        result = super().as_dict()
        result["endpoints"] = [ep.as_dict() for ep in self.endpoints]
        return result

    @classmethod
    def from_response(cls, resp: dict[str, Any]) -> ServiceInfo:
        """Read the class instance from a server response.

        Unknown fields are ignored ("open-world assumption").
        """
        info = super().from_response(resp)
        info.endpoints = [EndpointInfo(**ep) for ep in resp["endpoints"]]
        return info


@dataclass
class PingInfo(Base):
    """The response to a ping message."""

    name: str
    id: str
    version: str
    metadata: dict[str, str]
    type: str = "io.nats.micro.v1.ping_response"

    def copy(self) -> PingInfo:
        return replace(self, metadata=self.metadata.copy())
