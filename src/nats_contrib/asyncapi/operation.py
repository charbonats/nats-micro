from __future__ import annotations

import abc
from dataclasses import dataclass, is_dataclass
from types import new_class
from typing import Any, Callable, Coroutine, Generic, Iterable, Protocol, cast, overload

from .address import Address, new_address
from .message import Message
from .type_adapter import TypeAdapter, sniff_type_adapter
from .types import E, P, ParamsT, R, S, T


class OperationProtocol(Generic[ParamsT, T, R, E], Protocol):
    def handle(
        self, request: Message[ParamsT, T, R, E]
    ) -> Coroutine[Any, Any, None]: ...


class ParametersFactory(Generic[S, P], Protocol):
    def __call__(
        self,
        *args: S.args,
        **kwargs: S.kwargs,
    ) -> P: ...


@dataclass
class ErrorHandler(Generic[E]):
    origin: type[BaseException]
    code: int
    description: str
    fmt: Callable[[BaseException], E] | None = None


@dataclass
class Schema(Generic[T]):
    """Schema type."""

    type: type[T]
    content_type: str
    type_adapter: TypeAdapter[T]


def schema(
    type: type[T],
    content_type: str | None = None,
    type_adapter: TypeAdapter[T] | None = None,
) -> Schema[T]:
    if not content_type:
        content_type = _sniff_content_type(type)
    if not type_adapter:
        type_adapter = sniff_type_adapter(type)
    return Schema(type, content_type, type_adapter)


@dataclass
class OperationSpec(Generic[S, ParamsT, T, R, E]):
    """Endpoint specification."""

    def __init__(
        self,
        address: str,
        name: str,
        parameters: ParametersFactory[S, ParamsT],
        request: Schema[T],
        response: Schema[R],
        error: Schema[E],
        catch: Iterable[ErrorHandler[E]] | None = None,
        metadata: dict[str, Any] | None = None,
        status_code: int = 200,
    ) -> None:
        self.address = cast(Address[ParamsT], new_address(address, parameters))  # type: ignore
        self.name = name
        self.parameters = parameters
        self.request = request
        self.response = response
        self.error = error
        self.catch = catch or []
        self.metadata = metadata or {}
        self.status_code = status_code


@dataclass
class OperationRequest(Generic[ParamsT, T, R, E]):
    """Endpoint request."""

    subject: str
    params: ParamsT
    payload: T
    spec: OperationSpec[Any, ParamsT, T, R, E]


class Operation(Generic[S, ParamsT, T, R, E], metaclass=abc.ABCMeta):
    _spec: OperationSpec[S, ParamsT, T, R, E]

    def __init_subclass__(
        cls, spec: OperationSpec[S, ParamsT, T, R, E] | None = None
    ) -> None:
        super().__init_subclass__()
        if not hasattr(cls, "_spec") and spec is None:
            raise TypeError("Missing spec")
        if not spec:
            return
        cls._spec = spec

    @abc.abstractmethod
    def handle(self, request: Message[ParamsT, T, R, E]) -> Coroutine[Any, Any, None]:
        raise NotImplementedError

    @property
    def spec(self) -> OperationSpec[S, ParamsT, T, R, E]:
        return self._spec

    @overload
    @classmethod
    def request(
        cls: type[OperationSpec[S, None, None, R, E]]
    ) -> OperationRequest[ParamsT, T, R, E]: ...

    @overload
    @classmethod
    def request(
        cls: type[OperationSpec[S, None, T, R, E]], data: T
    ) -> OperationRequest[ParamsT, T, R, E]: ...

    @overload
    @classmethod
    def request(
        cls: type[OperationSpec[S, ParamsT, None, R, E]],
        *args: S.args,
        **kwargs: S.kwargs,
    ) -> OperationRequest[ParamsT, T, R, E]: ...

    @overload
    @classmethod
    def request(
        cls, data: T, *args: S.args, **kwargs: S.kwargs
    ) -> OperationRequest[ParamsT, T, R, E]: ...

    @classmethod
    def request(
        cls, data: Any = ..., *args: Any, **kwargs: Any
    ) -> OperationRequest[ParamsT, T, R, E]:
        spec = cls._spec  # pyright: ignore[reportGeneralTypeIssues]
        if data is ...:
            if spec.request.type is not type(None):
                raise TypeError("Missing request data")
        params = spec.parameters(*args, **kwargs)
        subject = spec.address.get_subject(params)
        return OperationRequest(
            subject=subject,
            params=params,
            payload=data,
            spec=spec,
        )


class OperationDecorator(Generic[S, ParamsT, T, R, E]):
    def __init__(
        self,
        address: str,
        parameters: ParametersFactory[S, ParamsT],
        request: Schema[T],
        response: Schema[R],
        error: Schema[E],
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
        catch: Iterable[ErrorHandler[E]] | None = None,
        status_code: int = 200,
    ) -> None:
        self.address = address
        self.name = name
        self.parameters = parameters
        self.request = request
        self.response = response
        self.error = error
        self.metadata = metadata or {}
        self.catch = catch or []
        self.status_code = status_code

    @overload
    def __call__(
        self,
        cls: type[OperationProtocol[ParamsT, T, R, E]],
    ) -> type[Operation[S, ParamsT, T, R, E]]: ...

    @overload
    def __call__(
        self,
        cls: type[object],
    ) -> type[Operation[S, ParamsT, T, R, E]]: ...

    def __call__(self, cls: type[Any]) -> type[Operation[S, ParamsT, T, R, E]]:
        name = self.name or cls.__name__
        spec = OperationSpec(
            address=self.address,
            name=name,
            parameters=self.parameters,
            request=self.request,
            response=self.response,
            error=self.error,
            metadata=self.metadata,
            catch=self.catch,
            status_code=self.status_code,
        )
        new_cls = new_class(cls.__name__, (cls, Operation), kwds={"spec": spec})
        return cast(type[Operation[S, ParamsT, T, R, E]], new_cls)


@overload
def operation(
    address: str,
    *,
    parameters: None = None,
    request_schema: None = None,
    response_schema: type[R] | Schema[R],
    error_schema: None = None,
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
    catch: Iterable[ErrorHandler[None]] | None = None,
    status_code: int = 200,
) -> OperationDecorator[Any, None, None, R, None]: ...


@overload
def operation(
    address: str,
    *,
    parameters: None = None,
    request_schema: None = None,
    response_schema: type[R] | Schema[R],
    error_schema: type[E] | Schema[E],
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
    catch: Iterable[ErrorHandler[E]] | None = None,
    status_code: int = 200,
) -> OperationDecorator[Any, None, None, R, E]: ...


@overload
def operation(
    address: str,
    *,
    parameters: None = None,
    request_schema: type[T] | Schema[T],
    response_schema: type[R] | Schema[R],
    error_schema: None = None,
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
    catch: Iterable[ErrorHandler[None]] | None = None,
    status_code: int = 200,
) -> OperationDecorator[Any, None, T, R, None]: ...


@overload
def operation(
    address: str,
    *,
    parameters: None = None,
    request_schema: type[T] | Schema[T],
    response_schema: type[R] | Schema[R],
    error_schema: type[E] | Schema[E],
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
    catch: Iterable[ErrorHandler[E]] | None = None,
    status_code: int = 200,
) -> OperationDecorator[Any, None, T, R, E]: ...


@overload
def operation(
    address: str,
    *,
    parameters: ParametersFactory[S, ParamsT],
    request_schema: None = None,
    response_schema: type[R] | Schema[R],
    error_schema: type[E] | Schema[E],
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
    catch: Iterable[ErrorHandler[E]] | None = None,
    status_code: int = 200,
) -> OperationDecorator[S, ParamsT, None, R, E]: ...


@overload
def operation(
    address: str,
    *,
    parameters: ParametersFactory[S, ParamsT],
    request_schema: type[T] | Schema[T],
    response_schema: None = None,
    error_schema: type[E] | Schema[E],
    name: str | None = None,
    catch: Iterable[ErrorHandler[E]] | None = None,
    status_code: int = 200,
) -> OperationDecorator[S, ParamsT, T, None, E]: ...


@overload
def operation(
    address: str,
    *,
    parameters: ParametersFactory[S, ParamsT],
    request_schema: type[T] | Schema[T],
    response_schema: type[R] | Schema[R],
    error_schema: None = None,
    name: str | None = None,
    catch: Iterable[ErrorHandler[None]] | None = None,
    status_code: int = 200,
) -> OperationDecorator[S, ParamsT, T, R, None]: ...


@overload
def operation(
    address: str,
    *,
    parameters: ParametersFactory[S, ParamsT],
    request_schema: type[T] | Schema[T],
    response_schema: type[R] | Schema[R],
    error_schema: type[E] | Schema[E],
    name: str | None = None,
    catch: Iterable[ErrorHandler[E]] | None = None,
    status_code: int = 200,
) -> OperationDecorator[S, ParamsT, T, R, E]: ...


def operation(
    address: str,
    *,
    parameters: Any = type(None),
    request_schema: Any = type(None),
    response_schema: Any = type(None),
    error_schema: Any = type(None),
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
    catch: Iterable[ErrorHandler[Any]] | None = None,
    status_code: int = 200,
) -> OperationDecorator[Any, Any, Any, Any, Any]:
    if not isinstance(request_schema, Schema):
        request_schema = Schema(
            type=request_schema,
            content_type=_sniff_content_type(request_schema),
            type_adapter=sniff_type_adapter(request_schema),
        )
    if not isinstance(response_schema, Schema):
        response_schema = Schema(
            type=response_schema,
            content_type=_sniff_content_type(response_schema),
            type_adapter=sniff_type_adapter(response_schema),
        )
    if not isinstance(error_schema, Schema):
        error_schema = Schema(
            type=error_schema,
            content_type=_sniff_content_type(error_schema),
            type_adapter=sniff_type_adapter(error_schema),
        )
    return OperationDecorator(
        address=address,
        parameters=parameters,
        request=request_schema,  # pyright: ignore[reportUnknownArgumentType]
        response=response_schema,  # pyright: ignore[reportUnknownArgumentType]
        error=error_schema,  # pyright: ignore[reportUnknownArgumentType]
        name=name,
        metadata=metadata,
        catch=catch,
        status_code=status_code,
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
