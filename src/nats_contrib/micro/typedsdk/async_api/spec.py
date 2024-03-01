from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AsyncAPI(BaseModel):
    asyncapi: str
    """The version of the AsyncAPI specification that the AsyncAPI document uses."""

    id: str
    """This field represents a unique universal identifier of the application the AsyncAPI document is defining. It must conform to the URI format, according to RFC3986."""

    info: Info
    """Provides metadata about the API. The metadata can be used by the clients if needed."""

    components: Components = Field(default_factory=lambda: Components())
    """An element to hold various reusable objects for the specification."""

    servers: dict[str, Reference] = Field(default_factory=dict)
    """Provides connection details of servers."""

    defaultContentType: str | None = None
    """Default content type to use when encoding/decoding a message's payload."""

    channels: dict[str, Reference] = Field(default_factory=dict)
    """The channels used by this application."""

    operations: dict[str, Reference] = Field(default_factory=dict)
    """The operations this application MUST implement."""

    def export(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True, by_alias=True)

    def export_json(self, indent: int | None = None) -> str:
        return self.model_dump_json(indent=indent, exclude_none=True, by_alias=True)


class Server(BaseModel):
    """An object representing a message broker, a server or any other kind of computer program capable of sending and/or receiving data."""

    host: str
    """The server host name. It MAY include the port."""

    protocol: str
    """The protocol this server supports for connection."""

    protocolVersion: str | None = None
    """The version of the protocol used for connection."""

    pathName: str | None = None
    """The path to a resource in the host."""

    description: str | None = None
    """An optional string describing the host designated by the URL."""

    title: str | None = None
    """A human-friendly name for the server."""

    summary: str | None = None
    """A short summary of the server."""

    variables: dict[str, ServerVariable] | None = None
    """A map between a variable name and its value. The value is used for substitution in the server's host and pathname template."""

    tags: list[str] | None = None
    """A list of tags for logical grouping and categorization of servers."""

    externalDocs: str | None = None
    """Additional external documentation for this server."""

    bindings: dict[str, Any] | None = None
    """A map where the keys describe the name of the protocol and the values describe protocol-specific definitions for the server."""

    security: dict[str, Any] | None = None
    """A declaration of which security schemes can be used with this server."""


class ServerVariable(BaseModel):
    enum: list[str] | None = None
    """An enumeration of string values to be used if the substitution options are from a limited set."""

    default: str | None = None
    """The default value to use for substitution, which SHALL be sent if an alternate value is not supplied."""

    description: str | None = None
    """An optional description for the server variable."""

    examples: list[str] | None = None
    """An array of examples of the server variable."""


class Info(BaseModel):
    title: str
    """The title of the application."""

    version: str
    """Provides the version of the application API (not to be confused with the specification version)."""

    description: str | None = None
    """A short description of the application. CommonMark syntax can be used for rich text representation."""

    termsOfService: str | None = None
    """The Terms of Service for the API."""

    contact: Contact | None = None
    """The contact information for the exposed API."""

    license: License | None = None
    """The license information for the exposed API."""

    tags: list[Tag] | None = None
    """"A list of tags for application API documentation control. Tags can be used for logical grouping of applications."""

    externalDocs: str | None = None
    """Additional external documentation."""


class Tag(BaseModel):
    """A tag for application API documentation control."""

    name: str
    """The name of the tag."""

    description: str | None = None
    """A short description of the tag. CommonMark syntax can be used for rich text representation."""

    externalDocs: str | None = None
    """Additional external documentation for this tag."""


class License(BaseModel):
    """License information for the exposed API."""

    name: str | None = None
    """The license name used for the API."""

    url: str | None = None
    """A URL to the license used for the API. MUST be in the format of a URL."""


class Contact(BaseModel):
    """Contact information for the exposed API."""

    name: str | None = None
    """The identifying name of the contact person/organization."""

    url: str | None = None
    """The URL pointing to the contact information. MUST be in the format of a URL."""

    email: str | None = None
    """The email address of the contact person/organization. MUST be in the format of an email address."""


class Reference(BaseModel):
    """A simple object to allow referencing other components in the specification, within the same or external AsyncAPI document. By using JSON pointers (i.e. `{"$ref": "#/components/schemas/MySchema"}`), the properties of the referenced structure can be practically re-used in the specification."""

    model_config = ConfigDict(populate_by_name=True)
    ref: str = Field(alias="$ref")

    @classmethod
    def from_ref(cls, ref: str) -> Reference:
        return cls(ref=ref)  # type: ignore


class Parameter(BaseModel):
    enum: list[str] | None = None
    """An enumeration of string values to be used if the substitution options are from a limited set."""

    default: str | None = None
    """The default value to use for substitution, which SHALL be sent if an alternate value is not supplied."""

    description: str | None = None
    """An optional description for the server variable."""

    examples: list[str] | None = None
    """An array of examples of the server variable."""


class Message(BaseModel):
    headers: Reference | None = None
    """Schema definition of the application headers. Schema MUST be a map of key-value pairs. It MUST NOT define the protocol headers."""

    payload: Reference | None = None
    """Definition of the message payload. It can be of any type but defaults to Schema object. It MUST NOT define the protocol headers."""

    correlationId: dict[str, Any] | None = None
    """Definition of the correlation ID used for message tracing or matching."""

    name: str | None = None
    """A human-friendly name for the message."""

    title: str | None = None
    """A human-friendly title for the message."""

    summary: str | None = None
    """A short summary of the message."""

    description: str | None = None
    """An optional description of the message. CommonMark syntax can be used for rich text representation."""

    tags: list[Tag] | None = None
    """A list of tags for logical grouping and categorization of messages."""

    externalDocs: str | None = None
    """Additional external documentation for this message."""

    bindings: dict[str, Any] | None = None
    """A map where the keys describe the name of the protocol and the values describe protocol-specific definitions for the message."""

    examples: list[dict[str, Any]] | None = None
    """A list of examples for the message."""


class Channel(BaseModel):
    """Describes a shared communication channel."""

    address: str | None = None
    """The address of the channel."""

    title: str | None = None
    """A human-friendly name for the channel."""

    summary: str | None = None
    """A short summary of the channel."""

    description: str | None = None
    """An optional description of this channel. CommonMark syntax can be used for rich text representation."""

    parameters: dict[str, Reference] | None = None
    """A map of the parameters included in the channel address. It MUST be present only when the address contains Channel Address Expressions."""

    messages: dict[str, Reference] | None = None
    """A map of the messages that will be sent to this channel by any application at any time."""

    servers: dict[str, Reference] | None = None
    """A list of server bindings."""

    tags: list[Tag] | None = None
    """A list of tags for logical grouping and categorization of channels."""

    externalDocs: str | None = None
    """Additional external documentation for this channel."""

    bindings: dict[str, Any] | None = None
    """A map where the keys describe the name of the protocol and the values describe protocol-specific definitions for the channel."""


class Action(str, Enum):
    SEND = "send"
    RECEIVE = "receive"


class Operation(BaseModel):
    action: Action
    """Use send when it's expected that the application will send a message to the given channel, and receive when the application should expect receiving messages from the given channel."""

    channel: Reference
    """A $ref pointer to the definition of the channel in which this operation is performed."""

    title: str | None = None
    """A human-friendly name for the operation."""

    summary: str | None = None
    """A short summary of the operation."""

    description: str | None = None
    """An optional description of the operation. CommonMark syntax can be used for rich text representation."""

    tags: list[Tag] | None = None
    """A list of tags for logical grouping and categorization of operations."""

    externalDocs: str | None = None
    """Additional external documentation for this operation."""

    bindings: dict[str, Any] | None = None
    """A map where the keys describe the name of the protocol and the values describe protocol-specific definitions for the operation."""

    messages: list[Reference] | None = None
    """A subset of the messages defined in the channel referenced in this operation."""

    reply: OperationReply | None = None
    """A reference to operation reply object."""


class OperationReply(BaseModel):
    channel: Reference
    """A $ref pointer to the definition of the channel in which this operation is performed."""

    messages: list[Reference] | None = None
    """A subset of the messages defined in the channel referenced in this operation."""


class Components(BaseModel):
    schemas: dict[str, Any] = Field(default_factory=dict)
    """An object to hold reusable Schema Objects."""

    parameters: dict[str, Parameter] = Field(default_factory=dict)
    """An object to hold reusable Parameter Objects."""

    servers: dict[str, Server] = Field(default_factory=dict)
    """An object to hold reusable Server Objects."""

    channels: dict[str, Channel] = Field(default_factory=dict)
    """An object to hold reusable Channel Items."""

    messages: dict[str, Message] = Field(default_factory=dict)
    """An object to hold reusable Message Objects."""

    operations: dict[str, Operation] = Field(default_factory=dict)
    """An object to hold reusable Operation Objects."""

    replies: dict[str, OperationReply] = Field(default_factory=dict)
    """An object to hold reusable Operation Reply Objects."""
