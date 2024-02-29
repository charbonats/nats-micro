from __future__ import annotations

import abc
from dataclasses import dataclass, is_dataclass
from types import new_class
from typing import Any, Callable, Coroutine, Generic, Protocol, TypeVar, cast, overload

from typing_extensions import ParamSpec, TypeAlias


from .address import Address, ParamsT, R, T, new_address
from .type_adapter import TypeAdapter

S = ParamSpec("S")
P = TypeVar("P", covariant=True)
E = TypeVar("E")


TypedHandler: TypeAlias = Callable[
    ["TypedRequest[ParamsT, T, R, E]"], Coroutine[Any, Any, None]
]


class TypedRequest(Generic[ParamsT, T, R, E], metaclass=abc.ABCMeta):
    def params(self) -> ParamsT: ...

    def data(self) -> T: ...

    def headers(self) -> dict[str, str]: ...

    async def respond(self, data: R, headers: dict[str, str] | None = None) -> None: ...

    async def respond_error(
        self, data: E, headers: dict[str, str] | None = None
    ) -> None: ...


class EndpointProtocol(Generic[ParamsT, T, R, E], Protocol):
    def handle(
        self, request: TypedRequest[ParamsT, T, R, E]
    ) -> Coroutine[Any, Any, None]: ...


class ParametersFactory(Generic[S, P], Protocol):
    def __call__(
        self,
        *args: S.args,
        **kwargs: S.kwargs,
    ) -> P: ...


@dataclass
class Schema(Generic[T]):
    """Schema type."""

    type: type[T]
    content_type: str
    type_adapter: TypeAdapter[T]


@dataclass
class EndpointSpec(Generic[S, ParamsT, T, R, E]):
    """Endpoint specification."""

    def __init__(
        self,
        address: str,
        name: str,
        parameters: ParametersFactory[S, ParamsT],
        request: Schema[T],
        response: Schema[R],
        error: Schema[E],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.address = cast(Address[ParamsT], new_address(address, parameters))  # type: ignore
        self.name = name
        self.parameters = parameters
        self.request = request
        self.response = response
        self.error = error
        self.metadata = metadata or {}


@dataclass
class RequestToSend(Generic[ParamsT, T, R, E]):
    """Endpoint request."""

    subject: str
    params: ParamsT
    request: T
    params_type: type[ParamsT]
    request_type: type[T]
    response_type: type[R]
    error_type: type[E]


class DecoratedEndpoint(Generic[S, ParamsT, T, R, E], metaclass=abc.ABCMeta):
    _spec: EndpointSpec[S, ParamsT, T, R, E]

    def __init_subclass__(
        cls, spec: EndpointSpec[S, ParamsT, T, R, E] | None = None
    ) -> None:
        super().__init_subclass__()
        if not hasattr(cls, "_spec") and spec is None:
            raise TypeError("Missing spec")
        if not spec:
            return
        cls._spec = spec

    @abc.abstractmethod
    def handle(
        self, request: TypedRequest[ParamsT, T, R, E]
    ) -> Coroutine[Any, Any, None]:
        raise NotImplementedError

    @property
    def spec(self) -> EndpointSpec[S, ParamsT, T, R, E]:
        return self._spec

    @overload
    @classmethod
    def request(
        cls: type[EndpointSpec[S, None, None, R, E]]
    ) -> RequestToSend[ParamsT, T, R, E]: ...

    @overload
    @classmethod
    def request(
        cls: type[EndpointSpec[S, None, T, R, E]], data: T
    ) -> RequestToSend[ParamsT, T, R, E]: ...

    @overload
    @classmethod
    def request(
        cls: type[EndpointSpec[S, ParamsT, None, R, E]],
        *args: S.args,
        **kwargs: S.kwargs,
    ) -> RequestToSend[ParamsT, T, R, E]: ...

    @overload
    @classmethod
    def request(
        cls, data: T, *args: S.args, **kwargs: S.kwargs
    ) -> RequestToSend[ParamsT, T, R, E]: ...

    @classmethod
    def request(
        cls, data: Any = ..., *args: Any, **kwargs: Any
    ) -> RequestToSend[ParamsT, T, R, E]:
        spec = cls._spec  # pyright: ignore[reportGeneralTypeIssues]
        if data is ...:
            if spec.request.type is not type(None):
                raise TypeError("Missing request data")
        params = spec.parameters(*args, **kwargs)
        subject = spec.address.get_subject(params)
        return RequestToSend(
            subject=subject,
            params=params,
            request=data,
            params_type=spec.parameters,  # pyright: ignore[reportArgumentType]
            request_type=spec.request.type,
            response_type=spec.response.type,
            error_type=spec.error.type,
        )


class EndpointDecorator(Generic[S, ParamsT, T, R, E]):
    def __init__(
        self,
        address: str,
        parameters: ParametersFactory[S, ParamsT],
        request: Schema[T],
        response: Schema[R],
        error: Schema[E],
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.address = address
        self.name = name
        self.parameters = parameters
        self.request = request
        self.response = response
        self.error = error
        self.metadata = metadata or {}

    @overload
    def __call__(
        self,
        cls: type[EndpointProtocol[ParamsT, T, R, E]],
    ) -> type[DecoratedEndpoint[S, ParamsT, T, R, E]]: ...

    @overload
    def __call__(
        self,
        cls: type[object],
    ) -> type[DecoratedEndpoint[S, ParamsT, T, R, E]]: ...

    def __call__(self, cls: type[Any]) -> type[DecoratedEndpoint[S, ParamsT, T, R, E]]:
        name = self.name or cls.__name__
        spec = EndpointSpec(
            address=self.address,
            name=name,
            parameters=self.parameters,
            request=self.request,
            response=self.response,
            error=self.error,
            metadata=self.metadata,
        )
        new_cls = new_class(cls.__name__, (DecoratedEndpoint, cls), kwds={"spec": spec})
        return cast(type[DecoratedEndpoint[S, ParamsT, T, R, E]], new_cls)


@overload
def endpoint(
    address: str,
    *,
    parameters: None = None,
    response_schema: type[R] | Schema[R],
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> EndpointDecorator[Any, None, None, R, None]: ...


@overload
def endpoint(
    address: str,
    *,
    parameters: None = None,
    response_schema: type[R] | Schema[R],
    error_schema: type[E] | Schema[E],
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> EndpointDecorator[Any, None, None, R, E]: ...


@overload
def endpoint(
    address: str,
    *,
    parameters: None = None,
    request_schema: type[T] | Schema[T],
    response_schema: type[R] | Schema[R],
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> EndpointDecorator[Any, None, T, R, None]: ...


@overload
def endpoint(
    address: str,
    *,
    parameters: None = None,
    request_schema: type[T] | Schema[T],
    response_schema: type[R] | Schema[R],
    error_schema: type[E] | Schema[E],
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> EndpointDecorator[Any, None, T, R, E]: ...


@overload
def endpoint(
    address: str,
    *,
    parameters: ParametersFactory[S, ParamsT],
    request_schema: None = None,
    response_schema: type[R] | Schema[R],
    error_schema: type[E] | Schema[E],
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> EndpointDecorator[S, ParamsT, None, R, E]: ...


@overload
def endpoint(
    address: str,
    *,
    parameters: ParametersFactory[S, ParamsT],
    request_schema: type[T] | Schema[T],
    response_schema: None = None,
    error_schema: type[E] | Schema[E],
    name: str | None = None,
) -> EndpointDecorator[S, ParamsT, T, None, E]: ...


@overload
def endpoint(
    address: str,
    *,
    parameters: ParametersFactory[S, ParamsT],
    request_schema: type[T] | Schema[T],
    response_schema: type[R] | Schema[R],
    error_schema: None = None,
    name: str | None = None,
) -> EndpointDecorator[S, ParamsT, T, R, None]: ...


@overload
def endpoint(
    address: str,
    *,
    parameters: ParametersFactory[S, ParamsT],
    request_schema: type[T] | Schema[T],
    response_schema: type[R] | Schema[R],
    error_schema: type[E] | Schema[E],
    name: str | None = None,
) -> EndpointDecorator[S, ParamsT, T, R, E]: ...


def endpoint(
    address: str,
    *,
    parameters: Any = type(None),
    request_schema: Any = type(None),
    response_schema: Any = type(None),
    error_schema: Any = type(None),
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> EndpointDecorator[Any, Any, Any, Any, Any]:
    if not isinstance(request_schema, Schema):
        request_schema = Schema(
            type=request_schema,
            content_type=_sniff_content_type(request_schema),
            type_adapter=_sniff_type_adapter(request_schema),
        )
    if not isinstance(response_schema, Schema):
        response_schema = Schema(
            type=response_schema,
            content_type=_sniff_content_type(response_schema),
            type_adapter=_sniff_type_adapter(response_schema),
        )
    if not isinstance(error_schema, Schema):
        error_schema = Schema(
            type=error_schema,
            content_type=_sniff_content_type(error_schema),
            type_adapter=_sniff_type_adapter(error_schema),
        )
    return EndpointDecorator(
        address=address,
        parameters=parameters,
        request=request_schema,  # pyright: ignore[reportUnknownArgumentType]
        response=response_schema,  # pyright: ignore[reportUnknownArgumentType]
        error=error_schema,  # pyright: ignore[reportUnknownArgumentType]
        name=name,
        metadata=metadata,
    )


def _sniff_content_type(typ: type[Any]) -> str:
    if is_dataclass(typ):
        return "application/json"
    if hasattr(typ, "model_fields"):
        return "application/json"
    if hasattr(typ, "__fields__"):
        return "application/json"
    if typ is type(None):
        return ""
    if typ is str:
        return "text/plain"
    if typ is int:
        return "text/plain"
    if typ is float:
        return "text/plain"
    if typ is bytes:
        return "application/octet-stream"
    if typ is dict:
        return "application/json"
    if typ is list:
        return "application/json"
    raise TypeError(
        f"Cannot guess content-type for class {typ}. "
        "Please specify the content-type explicitly."
    )


def _sniff_type_adapter(typ: type[T]) -> TypeAdapter[T]:
    raise NotImplementedError
