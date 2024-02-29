from __future__ import annotations

from typing import Any

from .endpoint import DecoratedEndpoint


class TypedService:
    """Typed service definition."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str | None = None,
        metadata: dict[str, str] | None = None,
        endpoints: list[type[DecoratedEndpoint[Any, Any, Any, Any, Any]]] | None = None,
    ) -> None:
        """Create a new typed service.

        Args:
            name: Service name.
            version: Service version.
            description: Service description.
            metadata: Service metadata.
            endpoints: List of supported endpoints.
        """
        self.name = name
        self.version = version
        self.description = description
        self.metadata = metadata or {}
        self.endpoints = endpoints or []
        self._registered_endpoints: list[DecoratedEndpoint[Any, Any, Any, Any, Any]] = (
            []
        )

    def register_endpoint(
        self, endpoint: DecoratedEndpoint[Any, Any, Any, Any, Any]
    ) -> None:
        """Register an implementation of a supported endpoint."""
        for candidate in self.endpoints:
            if isinstance(endpoint, candidate):
                break
        else:
            raise ValueError(f"Endpoint {endpoint} is not supported by the service")
        for existing in self._registered_endpoints:
            if existing.spec.address.subject == endpoint.spec.address.subject:
                raise ValueError(
                    f"Endpoint {endpoint} has the same address as {existing}"
                )
        self._registered_endpoints.append(endpoint)
