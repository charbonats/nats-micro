from __future__ import annotations

import re
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Generic, TypeVar, overload

T = TypeVar("T")
R = TypeVar("R")
ParamsT = TypeVar("ParamsT")

MATCH_ALL = ">"
MATCH_ONE = "*"
SEPARATOR = "."

# Regular expression used to identify placeholders within event names
regex = r"\{(.*?)\}"
pattern = re.compile(regex)


def _get_fields(obj: object) -> list[str]:
    """Get all fields of an object."""
    # Dataclasses (standard library)
    if is_dataclass(obj):
        return [field.name for field in fields(obj)]
    # Pydantic V2
    if hasattr(obj, "model_fields"):
        return list(obj.model_fields.keys())  # type: ignore
    # Pydantic V1
    if hasattr(obj, "__fields__"):
        return list(obj.__fields__.keys())  # type: ignore
    raise TypeError(f"Cannot get fields of object: {obj} ({type(obj)})")


@overload
def new_address(subject: str) -> Address[None]: ...


@overload
def new_address(subject: str, parameters: type[ParamsT]) -> Address[ParamsT]: ...


def new_address(subject: str, parameters: type[Any] | None = None) -> Address[Any]:
    """Create a new address with parameters.

    Args:
        subject: The subject filter.
        parameters: The parameters expected to be found on each valid subject matching subject filter.
            Parameters must be a dataclass or a class with a `__fields__` attribute such as `pydantic.BaseModel`.

    Returns:
        A new address.
    """
    return Address(subject, parameters)


class Address(Generic[ParamsT]):
    """Address for a channel.

    An address is represented as a string and is generic over a set of parameters.
    `ParamsT` is the type of the parameters expected to be found on each valid subject matching subject filter.
    Parameters (`ParamsT`) must be a dataclass or a class with a `__fields__` attribute such as `pydantic.BaseModel`.

    The string representation of the address can contain placeholders for parameters:

    - `{param}`: Matches any value for parameter `param`
    - `{param...}`: Matches any remaining values for parameter `param`. This can only be used once, and must be the last parameter.

    An example address is `foo.{bar}.baz.{qux...}`.

    The associated parameters could be:

    ```python
    @dataclass
    class Params:
        bar: str
        qux: list[str]

    address = Address("foo.{bar}.baz.{qux...}", Params)
    ```

    Such address would match `foo.abc.baz.123.456.789` and would extract the following parameters:

    ```python
    address.get_params("foo.abc.baz.123.456.789") == Params(
        bar="abc",
        qux=["123", "456", "789"],
    )
    ```
    """

    subject: str
    parameters: type[ParamsT]

    @overload
    def __init__(self: Address[None], subject: str) -> None:
        """Create a new address without parameter.

        Args:
            subject: The subject filter.
        """

    @overload
    def __init__(self, subject: str, parameters: type[ParamsT]) -> None:
        """Create a new address.

        Args:
            subject: The subject filter.
            parameters: The parameters expected to be found on each valid subject matching subject filter.
                Parameters must be a dataclass or a class with a `__fields__` attribute such as `pydantic.BaseModel`.
        """

    def __init__(self, subject: str, parameters: Any = None) -> None:
        self.subject = subject
        self.parameters = parameters
        self.placeholders = Placeholders.from_subject(subject, parameters)
        self._verify()

    def __str__(self) -> str:
        return self.subject

    def __repr__(self) -> str:
        if self.parameters:
            return f"Address({self.subject}, parameters={self.parameters.__name__})"
        return f"Address({self.subject})"

    def _verify(self) -> None:
        # Verify according to parameters
        if self.parameters is type(None) and self.placeholders.mapping:
            raise ValueError("Parameters are required")
        if self.parameters is type(None) and self.placeholders.wildcard:
            raise ValueError("Parameters are required")
        if self.parameters is type(None):
            return
        parameters_fields = _get_fields(self.parameters)
        # Verify that all parameters are present
        for param_field in parameters_fields:
            if param_field not in self.placeholders.mapping and not (
                self.placeholders.wildcard
                and self.placeholders.wildcard[0] == param_field
            ):
                raise ValueError(f"Missing parameter: '{param_field}'")
        # Verify that no extra parameters are present
        for param_field in self.placeholders.mapping.keys():
            if param_field not in parameters_fields:
                raise ValueError(f"Unknown parameter: '{param_field}'")
        # Verify that wildcard exist
        if (
            self.placeholders.wildcard
            and self.placeholders.wildcard[0] not in parameters_fields
        ):
            raise ValueError(f"Unknown parameter: '{self.placeholders.wildcard}'")

    def get_params(self, subject: str) -> ParamsT:
        """Extract parameters from subject.

        Args:
            subject: The subject to extract parameters from.

        Returns:
            The extracted parameters.
        """
        return self.placeholders.extract_parameters(subject)

    def get_subject(self, parameters: ParamsT | None = None) -> str:
        """Get a valid NATS subject for given parameters.

        Args:
            parameters: The parameters to use. If not provided, wildcards will be used for all parameters.

        Returns:
            A valid NATS subject.
        """
        if parameters is None:
            return self.placeholders.subject
        tokens = self.placeholders.subject.split(".")
        for name, pos in self.placeholders.mapping.items():
            tokens[pos] = getattr(parameters, name)
        if self.placeholders.wildcard:
            values = getattr(parameters, self.placeholders.wildcard[0])
            wildcard_start = self.placeholders.wildcard[1]
            tokens[wildcard_start] = values[0]
            for value in values[1:]:
                tokens.append(value)
        return ".".join(tokens)


@dataclass
class Placeholders(Generic[ParamsT]):
    typ: type[ParamsT]
    subject: str
    mapping: dict[str, int] = field(default_factory=dict)
    wildcard: tuple[str, int] | None = None

    def __repr__(self) -> str:
        return f"Placeholders({self.mapping}, wildcard={self.wildcard})"

    def extract_parameters(self, subject: str) -> ParamsT:
        kwargs = {}
        tokens = subject.split(".")
        for name, pos in self.mapping.items():
            kwargs[name] = tokens[pos]
        if self.wildcard:
            wildcard_start = self.wildcard[1]
            kwargs[self.wildcard[0]] = tokens[wildcard_start:]
        return self.typ(**kwargs)

    @classmethod
    def from_subject(
        cls,
        subject: str,
        parameters: type[ParamsT] | None = None,
    ) -> Placeholders[ParamsT]:
        placeholders = cls(typ=parameters or type(None), subject="")
        sanitized_subject = str(subject)
        is_wildcard = False
        for match in list(pattern.finditer(sanitized_subject)):
            start = match.start()
            end = match.end()
            placeholder = subject[start:end]
            # Get placeholder name
            placeholder_name = placeholder[1:-1]
            if placeholder_name.endswith("..."):
                if is_wildcard:
                    raise ValueError("Only one match_all wildcard is allowed")
                # Replace in sanitized subject
                sanitized_subject = sanitized_subject.replace(placeholder, MATCH_ALL)
                placeholder_name = placeholder_name[:-3]
                is_wildcard = True
            else:
                # Replace in sanitized subject
                sanitized_subject = sanitized_subject.replace(placeholder, MATCH_ONE)
            if not placeholder_name:
                raise ValueError(f"Placeholder cannot be empty: '{subject}'")
            if SEPARATOR in placeholder_name:
                raise ValueError(f"Invalid placeholder name: Contains '{SEPARATOR}'")
            # Check that placeholder is indeed a whole token and not just a part
            try:
                next_char = subject[end]
            except IndexError:
                next_char = ""
            if start:
                previous_char = subject[start - 1]
            else:
                previous_char = ""
            if previous_char and previous_char != SEPARATOR:
                raise ValueError("Placeholder must occupy whole token")
            if next_char and next_char != SEPARATOR:
                raise ValueError("Placeholder must occupy whole token")

            # Append placeholder
            pos = (
                subject.replace("...", MATCH_ONE)
                .split(".")
                .index(placeholder.replace("...", MATCH_ALL))
            )
            if is_wildcard:
                placeholders.wildcard = (placeholder_name, pos)
            else:
                placeholders.mapping[placeholder_name] = pos
        placeholders.subject = sanitized_subject
        return placeholders
