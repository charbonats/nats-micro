from __future__ import annotations

import pydantic

from .interface import T, TypeAdapter, TypeAdapterFactory


class PydanticV2JSONAdapter(TypeAdapter[T]):
    """A type adapter for Pydantic v1 models."""

    def __init__(self, typ: type[T]) -> None:
        self.typ = typ
        self.adapter = pydantic.TypeAdapter(typ)

    def encode(self, message: T) -> bytes:
        if self.typ is type(None):
            if message is not None:
                raise ValueError("No value expected")
            return b""
        return self.adapter.dump_json(message)

    def decode(self, data: bytes) -> T:
        if self.typ is type(None):
            if data:
                raise ValueError("No value expected")
            return None  # type: ignore
        return self.adapter.validate_json(data)


class PydanticV2JSONAdapterFactory(TypeAdapterFactory):
    """A type adapter factory for Pydantic v1 models."""

    def __call__(self, schema: type[T]) -> TypeAdapter[T]:
        return PydanticV2JSONAdapter(schema)
