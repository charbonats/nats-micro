from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import pydantic

from .asyncapi import (
    Action,
    AsyncAPI,
    Channel,
    Components,
    Contact,
    Info,
    License,
    Message,
    Operation,
    OperationReply,
    Parameter,
    Reference,
    Tag,
)

if TYPE_CHECKING:
    from ..application import Application


if pydantic.__version__.startswith("1."):
    default_schema_of: SchemaAdapter = pydantic.schema_of  # type: ignore
elif pydantic.__version__.startswith("2."):

    def default_schema_of(obj: Any) -> dict[str, Any]:
        """Return the schema of an object."""
        return pydantic.TypeAdapter(obj).json_schema()

else:
    raise ImportError("Unsupported pydantic version")


class SchemaAdapter(Protocol):
    """Schema adapter protocol."""

    def __call__(self, obj: Any) -> dict[str, Any]:
        """Return the schema of an object."""
        ...


def build_spec(
    app: Application, schema_adapter: SchemaAdapter | None = None
) -> AsyncAPI:
    """Build an AsyncAPI specification from an application."""
    schema_adapter = schema_adapter or default_schema_of
    # Start be building app info
    info = Info(
        title=app.name,
        version=app.version,
        description=app.description,
        termsOfService=app.terms_of_service,
        contact=(
            Contact(name=app.contact.name, url=app.contact.url, email=app.contact.email)
            if app.contact
            else None
        ),
        license=(
            License(name=app.license.name, url=app.license.url) if app.license else None
        ),
        tags=[
            Tag(
                name=tag.name,
                description=tag.description,
                externalDocs=tag.external_docs,
            )
            for tag in app.tags
        ],
        externalDocs=app.external_docs,
    )
    # Then create a spec
    spec = AsyncAPI(asyncapi="3.0.0", id=app.id, info=info, components=Components())
    # Now add the channels
    # For each channel, first add a component, then add the channel
    for ep in app.endpoints:
        ep_spec = (
            ep._spec  # pyright: ignore[reportPrivateUsage,reportGeneralTypeIssues]
        )
        # Add request schema
        request = (
            ep._spec.request  # pyright: ignore[reportPrivateUsage,reportGeneralTypeIssues]
        )
        schema = schema_adapter(request.type)
        spec.components.schemas[request.type.__name__] = schema
        request_ref = Reference.from_ref(
            f"#/components/schemas/{request.type.__name__}"
        )
        # Add response schema
        response = ep_spec.response
        schema = schema_adapter(response.type)
        spec.components.schemas[response.type.__name__] = schema
        response_ref = Reference.from_ref(
            f"#/components/schemas/{response.type.__name__}"
        )
        # Add parameters
        params = ep_spec.address._fields  # pyright: ignore[reportPrivateUsage]
        params_refs: dict[str, Reference] = {}
        for param in params:
            spec.components.parameters[param] = Parameter()
            params_refs[param] = Reference.from_ref(f"#/components/parameters/{param}")

        # Add request message
        message = Message(
            name=request.type.__name__,
            description=request.__doc__,
            payload=request_ref,
        )
        spec.components.messages[request.type.__name__] = message
        request_message_ref = Reference.from_ref(
            f"#/components/messages/{request.type.__name__}"
        )
        # Add response message
        message = Message(
            name=response.type.__name__,
            description=response.__doc__,
            payload=response_ref,
        )
        spec.components.messages[response.type.__name__] = message
        response_message_ref = Reference.from_ref(
            f"#/components/messages/{response.type.__name__}"
        )
        # Add channel
        spec.components.channels[ep_spec.name + "_request"] = Channel(
            address=ep_spec.address.subject,
            parameters=params_refs,
            messages={
                request.type.__name__: request_message_ref,
            },
        )
        channel_ref = Reference.from_ref(
            f"#/components/channels/{ep_spec.name + '_request'}"
        )
        # Add reply channel
        spec.components.channels[ep_spec.name + "_reply"] = Channel(
            address=None,
            summary=f"Reply channel for {ep_spec.name} operation",
            messages={
                response.type.__name__: response_message_ref,
            },
        )
        reply_channel_ref = Reference.from_ref(
            f"#/components/channels/{ep_spec.name + '_reply'}"
        )
        # Add reply object
        reply = OperationReply(
            channel=reply_channel_ref,
        )
        # Add operation
        spec.components.operations[ep_spec.name] = Operation(
            action=Action.RECEIVE,
            channel=channel_ref,
            description=ep.__doc__,
            reply=reply,
        )
        operation_ref = Reference.from_ref(
            ref=f"#/components/operations/{ep_spec.name}"
        )
        # Add the channel and the operations to the root spec
        spec.channels[ep_spec.name + "_request"] = channel_ref
        spec.channels[ep_spec.name + "_reply"] = reply_channel_ref
        spec.operations[ep_spec.name] = operation_ref

    return spec
