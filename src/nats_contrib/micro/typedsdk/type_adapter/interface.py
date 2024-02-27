from __future__ import annotations

from typing import Generic, Protocol, TypeVar

T = TypeVar("T")


class TypeAdapterFactory(Protocol):
    """A type adapter factory is a class providing methods to create type adapters."""

    def __call__(self, schema: type[T]) -> TypeAdapter[T]: ...


class TypeAdapter(Protocol, Generic[T]):
    """A type adapter is a class providing methods to encode and decode data."""

    def encode(self, message: T) -> bytes: ...

    def decode(self, data: bytes) -> T: ...


def default_type_adapter() -> TypeAdapterFactory:
    try:
        import pydantic
    except ImportError:
        raise NotImplementedError("Pydantic is not installed")
    if pydantic.__version__.startswith("1."):
        from .pydantic_v1 import PydanticV1AdapterFactory

        return PydanticV1AdapterFactory()
    elif pydantic.__version__.startswith("2."):
        from .pydantic_v2 import PydanticV2AdapterFactory

        return PydanticV2AdapterFactory()
    else:
        from .standard import StandardJSONAdapterFactory

        return StandardJSONAdapterFactory()
