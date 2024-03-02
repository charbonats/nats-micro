from __future__ import annotations

from dataclasses import is_dataclass
from typing import Generic, Protocol, TypeVar

T = TypeVar("T")


class TypeAdapterFactory(Protocol):
    """A type adapter factory is a class providing methods to create type adapters."""

    def __call__(self, schema: type[T]) -> TypeAdapter[T]: ...


class TypeAdapter(Protocol, Generic[T]):
    """A type adapter is a class providing methods to encode and decode data."""

    def encode(self, message: T) -> bytes: ...

    def decode(self, data: bytes) -> T: ...


def default_json_adapter() -> TypeAdapterFactory:
    try:
        import pydantic
    except ImportError:
        from .standard import StandardJSONAdapterFactory

        return StandardJSONAdapterFactory()

    if pydantic.__version__.startswith("1."):
        from .pydantic_v1 import PydanticV1JSONAdapterFactory

        return PydanticV1JSONAdapterFactory()
    elif pydantic.__version__.startswith("2."):
        from .pydantic_v2 import PydanticV2JSONAdapterFactory

        return PydanticV2JSONAdapterFactory()


def sniff_type_adapter(typ: type[T]) -> TypeAdapter[T]:
    from .standard import RawTypeAdapter

    if typ is bytes:
        return RawTypeAdapter(typ)
    if typ is str:
        return RawTypeAdapter(typ)
    if typ is int:
        return RawTypeAdapter(typ)
    if typ is float:
        return RawTypeAdapter(typ)
    if typ is bool:
        return RawTypeAdapter(typ)
    if typ is type(None):
        return RawTypeAdapter(typ)
    if is_dataclass(typ):
        return default_json_adapter()(typ)
    if hasattr(typ, "model_fields"):
        return default_json_adapter()(typ)
    if hasattr(typ, "__fields__"):
        return default_json_adapter()(typ)
    raise TypeError(f"Cannot find a type adapter for the given type: {typ}")
