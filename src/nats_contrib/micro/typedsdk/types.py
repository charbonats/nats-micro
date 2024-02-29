from __future__ import annotations

from typing import TypeVar

from typing_extensions import ParamSpec

T = TypeVar("T")
R = TypeVar("R")
ParamsT = TypeVar("ParamsT")

S = ParamSpec("S")
P = TypeVar("P", covariant=True)
E = TypeVar("E")

__all__ = [
    "T",
    "R",
    "ParamsT",
]
