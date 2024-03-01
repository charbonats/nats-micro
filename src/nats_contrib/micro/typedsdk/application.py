from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .operation import Operation


@dataclass
class Contact:
    """Contact information for the exposed API."""

    name: str | None = None
    url: str | None = None
    email: str | None = None


@dataclass
class License:
    """License information for the exposed API."""

    name: str | None = None
    url: str | None = None


@dataclass
class Tag:
    """A tag for application API documentation control."""

    name: str
    description: str | None = None
    external_docs: str | None = None


class Application:
    """Typed service definition."""

    def __init__(
        self,
        id: str,
        name: str,
        version: str,
        description: str | None = None,
        metadata: dict[str, str] | None = None,
        terms_of_service: str | None = None,
        operations: list[type[Operation[Any, Any, Any, Any, Any]]] | None = None,
        contact: Contact | None = None,
        license: License | None = None,
        tags: list[Tag] | None = None,
        external_docs: str | None = None,
    ) -> None:
        """Create a new typed service.

        Args:
            id: Application id
            name: Application name.
            version: Application version.
            description: Application description.
            metadata: Application metadata.
            operations: List of operations that this application must implement.
            terms_of_service: A URL to the Terms of Service for the API. This MUST be in the form of an absolute URL.
            contact: The contact information for the exposed API.
            license: The license information for the exposed API.
            tags: A list of tags for application API documentation control. Tags can be used for logical grouping of applications.
            external_docs: Additional external documentation.
        """
        self.id = id
        self.name = name
        self.version = version
        self.description = description
        self.metadata = metadata or {}
        self.terms_of_service = terms_of_service
        self.endpoints = operations or []
        self.contact = contact
        self.license = license
        self.tags = tags or []
        self.external_docs = external_docs
        self._registered_endpoints: list[Operation[Any, Any, Any, Any, Any]] = []

    def with_endpoints(
        self, *endpoint: Operation[Any, Any, Any, Any, Any]
    ) -> Application:
        service = self.__copy__()
        for ep in endpoint:
            service._add_endpoints(ep)
        return service

    def _add_endpoints(self, endpoint: Operation[Any, Any, Any, Any, Any]) -> None:
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

    def __copy__(self) -> Application:
        new_instance = Application(
            id=self.id,
            name=self.name,
            version=self.version,
            description=self.description,
            metadata=self.metadata,
            operations=[ep for ep in self.endpoints],
        )
        for ep in self._registered_endpoints:
            new_instance._registered_endpoints.append(ep)
        return new_instance
