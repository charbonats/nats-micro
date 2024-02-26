from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass
class Flag(Generic[T]):
    """A command line flag."""

    name: str
    metavar: str
    type: type[T]
    help: str
    env: str | None = None
    env_transform: Callable[[str], T] | None = None
    repeat: bool = False
    default: T = ...  # type: ignore
    alias: list[str] | None = None
    short_option: str | None = None

    def add_as_global_option(self, parser: argparse.ArgumentParser) -> None:
        """Add the argument to the parser."""
        kwargs: dict[str, Any] = {}
        args: list[str] = []
        if self.alias:
            args.extend(self.alias)
        if self.short_option:
            args.append(self.short_option)
        if self.repeat:
            kwargs["action"] = "append"
            kwargs["nargs"] = "?"
        if self.default is not ...:
            kwargs["help"] = f"{self.help} (default: {self.default})"
        else:
            kwargs["help"] = self.help
        parser.add_argument(
            f"--{self.name}",
            *args,
            metavar=self.metavar,
            type=self.type,
            **kwargs,
        )

    def add_as_subcommand_option(self, parser: argparse.ArgumentParser) -> None:
        """Add the argument to the parser."""
        kwargs: dict[str, Any] = {}
        if self.repeat:
            kwargs["action"] = "append"
            kwargs["nargs"] = "?"
        extras: list[str] = []
        if self.default is not ...:
            extras.append(f"(default: {self.default})")
        if self.env is not None:
            extras.append(f"(env: {self.env})")
        if extras:
            kwargs["help"] = f"{self.help} {' '.join(extras)}"
        else:
            kwargs["help"] = self.help
        parser.add_argument(
            f"--{self.name}",
            metavar=self.metavar,
            type=self.type,
            dest=f"{self.name}_",
            **kwargs,
        )

    def get(self, args: argparse.Namespace) -> T:
        """Get the value of the argument from the namespace."""
        local = getattr(args, f"{self.name}_", None)
        if local is not None:
            return local
        value = getattr(args, self.name, None)
        if value is not None:
            return value
        if self.env is not None:
            value = os.environ.get(self.env, None)
            if value is not None:
                if self.env_transform is not None:
                    return self.env_transform(value)
                return self.type(value)
        if self.default is not ...:
            return self.default

        raise ValueError(f"missing argument: {self.name}")

    def get_list(self, args: argparse.Namespace) -> list[T]:
        """Get the value of the argument from the namespace."""
        values = getattr(args, f"{self.name}_", None)
        if values:
            return values
        values = getattr(args, self.name, None)
        if values:
            return values
        if self.env is not None:
            value = os.environ.get(self.env, None)
            if value is not None:
                values = [v.strip() for v in value.split(",") if v]
                if self.env_transform is not None:
                    return [self.env_transform(v) for v in values]
                return [self.type(v) for v in values]

        return []
