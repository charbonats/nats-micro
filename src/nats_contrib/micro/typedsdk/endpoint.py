from __future__ import annotations

import abc
from dataclasses import dataclass
from types import new_class
from typing import Any, Coroutine, Generic, NoReturn, Protocol, TypeVar, cast, overload

from typing_extensions import ParamSpec

from .address import Address, ParamsT, R, T, new_address

S = ParamSpec("S")
P = TypeVar("P", covariant=True)
E = TypeVar("E")

P_ = TypeVar("P_", contravariant=True)
T_ = TypeVar("T_", contravariant=True)
R_ = TypeVar("R_", covariant=True)


class ParametersFactory(Generic[S, P], Protocol):
    def __call__(
        self,
        *args: S.args,
        **kwargs: S.kwargs,
    ) -> P: ...


@dataclass
class EndpointSpec(Generic[S, ParamsT, T, R, E]):
    """Endpoint specification."""

    def __init__(
        self,
        address: str,
        name: str,
        parameters: ParametersFactory[S, ParamsT],
        request_schema: type[T],
        response_schema: type[R],
        error_schema: type[E],
    ) -> None:
        self.address = cast(Address[ParamsT], new_address(address, parameters))  # type: ignore
        self.name = name
        self.parameters = parameters
        self.request_schema = request_schema
        self.response_schema = response_schema
        self.error_schema = error_schema

    @overload
    def request(
        self: type[EndpointSpec[S, None, None, R, E]]
    ) -> EndpointRequest[ParamsT, T, R, E]: ...

    @overload
    def request(
        self: type[EndpointSpec[S, None, T, R, E]], data: T
    ) -> EndpointRequest[ParamsT, T, R, E]: ...

    @overload
    def request(
        self: type[EndpointSpec[S, ParamsT, None, R, E]],
        *args: S.args,
        **kwargs: S.kwargs,
    ) -> EndpointRequest[ParamsT, T, R, E]: ...

    @overload
    def request(
        self, data: T, *args: S.args, **kwargs: S.kwargs
    ) -> EndpointRequest[ParamsT, T, R, E]: ...

    def request(
        self, data: Any = ..., *args: Any, **kwargs: Any
    ) -> EndpointRequest[ParamsT, T, R, E]:
        if data is ...:
            if self.request_schema is not type(None):
                raise TypeError("Missing request data")
        params = self.parameters(*args, **kwargs)
        subject = self.address.get_subject(params)
        return EndpointRequest(
            subject=subject,
            params=params,
            request=data,
            params_type=self.parameters,  # pyright: ignore[reportArgumentType]
            request_type=self.request_schema,
            response_type=self.response_schema,
            error_type=self.error_schema,
        )


@dataclass
class EndpointRequest(Generic[ParamsT, T, R, E]):
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
    def handle(self, params: ParamsT, request: T) -> Coroutine[Any, Any, R]:
        raise NotImplementedError

    @property
    def spec(self) -> EndpointSpec[S, ParamsT, T, R, E]:
        return self._spec

    @overload
    @classmethod
    def request(
        cls: type[EndpointSpec[S, None, None, R, E]]
    ) -> EndpointRequest[ParamsT, T, R, E]: ...

    @overload
    @classmethod
    def request(
        cls: type[EndpointSpec[S, None, T, R, E]], data: T
    ) -> EndpointRequest[ParamsT, T, R, E]: ...

    @overload
    @classmethod
    def request(
        cls: type[EndpointSpec[S, ParamsT, None, R, E]],
        *args: S.args,
        **kwargs: S.kwargs,
    ) -> EndpointRequest[ParamsT, T, R, E]: ...

    @overload
    @classmethod
    def request(
        cls, data: T, *args: S.args, **kwargs: S.kwargs
    ) -> EndpointRequest[ParamsT, T, R, E]: ...

    @classmethod
    def request(
        cls, data: Any = ..., *args: Any, **kwargs: Any
    ) -> EndpointRequest[ParamsT, T, R, E]:
        spec = cls._spec  # pyright: ignore[reportGeneralTypeIssues]
        if data is ...:
            if spec.request_schema is not type(None):
                raise TypeError("Missing request data")
        params = spec.parameters(*args, **kwargs)
        subject = spec.address.get_subject(params)
        return EndpointRequest(
            subject=subject,
            params=params,
            request=data,
            params_type=spec.parameters,  # pyright: ignore[reportArgumentType]
            request_type=spec.request_schema,
            response_type=spec.response_schema,
            error_type=spec.error_schema,
        )


class EndpointProtocol(Generic[P_, T_, R_], Protocol):
    def handle(self, params: P_, request: T_) -> Coroutine[Any, Any, R_]: ...


class EndpointDecorator(Generic[S, ParamsT, T, R, E]):
    def __init__(
        self,
        address: str,
        parameters: ParametersFactory[S, ParamsT],
        request_schema: type[T],
        response_schema: type[R],
        error_schema: type[E],
        name: str | None = None,
    ) -> None:
        self.address = address
        self.name = name
        self.parameters = parameters
        self.request_schema = request_schema
        self.response_schema = response_schema
        self.error_schema = error_schema

    @overload
    def __call__(
        self,
        cls: type[EndpointProtocol[ParamsT, T, R]],
    ) -> type[DecoratedEndpoint[S, ParamsT, T, R, E]]: ...

    @overload
    def __call__(
        self,
        cls: type[EndpointProtocol[Any, Any, Any]],
    ) -> NoReturn: ...

    @overload
    def __call__(
        self,
        cls: type[object],
    ) -> type[DecoratedEndpoint[S, ParamsT, T, R, E]]: ...

    def __call__(self, cls: type[Any]) -> type[DecoratedEndpoint[S, ParamsT, T, R, E]]:
        name = self.name or cls.__name__
        spec = EndpointSpec(
            self.address,
            name,
            self.parameters,
            self.request_schema,
            self.response_schema,
            self.error_schema,
        )
        new_cls = new_class(cls.__name__, (DecoratedEndpoint, cls), kwds={"spec": spec})
        return cast(type[DecoratedEndpoint[S, ParamsT, T, R, E]], new_cls)


def endpoint(
    address: str,
    parameters: ParametersFactory[S, ParamsT],
    request_schema: type[T],
    response_schema: type[R],
    error_schema: type[E],
) -> EndpointDecorator[S, ParamsT, T, R, E]:

    return EndpointDecorator(
        address, parameters, request_schema, response_schema, error_schema
    )
