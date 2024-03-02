from __future__ import annotations

import datetime
import json
import numbers
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

import pydantic

from .interface import T, TypeAdapter, TypeAdapterFactory


class PydanticV1JSONAdapter(TypeAdapter[T]):
    """A type adapter for Pydantic v1 models."""

    def __init__(self, typ: type[T]) -> None:
        self.typ = typ

    def encode(self, message: T) -> bytes:
        if self.typ is type(None):
            if message:
                raise ValueError("No value expected")
            return b""
        return json.dumps(
            message,
            default=_default_serializer,
            separators=(",", ":"),
        ).encode("utf-8")

    def decode(self, data: bytes) -> T:
        if self.typ is type(None):
            if data:
                raise ValueError("No value expected")
            return None  # type: ignore
        return pydantic.parse_raw_as(self.typ, data)


class PydanticV1JSONAdapterFactory(TypeAdapterFactory):
    """A type adapter factory for Pydantic v1 models."""

    def __call__(self, schema: type[T]) -> TypeAdapter[T]:
        return PydanticV1JSONAdapter(schema)


def _default_serializer(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (bytes, bytearray, set)):
        return list(obj)  # pyright: ignore[reportUnknownArgumentType]
    if isinstance(obj, pydantic.BaseModel):
        return obj.dict()
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, numbers.Integral):
        return int(obj)
    if isinstance(obj, numbers.Real):
        return float(obj)
    raise TypeError
