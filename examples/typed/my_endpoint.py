from __future__ import annotations

from dataclasses import dataclass

from nats_contrib.micro.typedsdk import endpoint
from nats_contrib.micro.typedsdk.endpoint import ErrorHandler


@dataclass
class MyParams:
    """Parameters found in endpoint request subject."""

    device_id: str


@dataclass
class MyRequest:
    """Fields expected in endpoint request payload."""

    value: int


@dataclass
class MyResponse:
    """Fields expected in endpoint reply payload."""

    result: int


@endpoint(
    address="foo.{device_id}",
    parameters=MyParams,
    request_schema=MyRequest,
    response_schema=MyResponse,
    error_schema=str,
    catch=[
        ErrorHandler(
            ValueError,
            400,
            "Bad request",
            lambda err: "Request failed due to malformed request data",
        ),
    ],
)
class MyEndpoint:
    """This is an example endpoint definition."""
