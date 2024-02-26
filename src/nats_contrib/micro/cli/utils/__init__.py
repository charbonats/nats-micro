from typing import TYPE_CHECKING

from .flags import Flag

if TYPE_CHECKING:
    from .types import Subparser

__all__ = ["Flag", "Subparser"]
