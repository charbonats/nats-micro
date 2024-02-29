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

    def with_endpoints(
        self, *endpoint: DecoratedEndpoint[Any, Any, Any, Any, Any]
    ) -> TypedService:
        service = self.__copy__()
        for ep in endpoint:
            service._add_endpoints(ep)
        return service

    def _add_endpoints(
        self, endpoint: DecoratedEndpoint[Any, Any, Any, Any, Any]
    ) -> None:
        """Return a new service instance with an additional endpoint registered."""
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

    def __copy__(self) -> TypedService:
        new_instance = TypedService(
            name=self.name,
            version=self.version,
            description=self.description,
            metadata=self.metadata,
            endpoints=[ep for ep in self.endpoints],
        )
        for ep in self._registered_endpoints:
            new_instance._registered_endpoints.append(ep)
        return new_instance
