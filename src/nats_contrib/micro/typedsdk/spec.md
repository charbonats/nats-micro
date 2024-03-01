# Typed SDK

This document describes the typed SDK API.

## Overview

NATS Micro leverages concept such as:


- Endpoints: A function called when a message is received on a specific subject.

- Services: A collection of endpoints.

One of the constraints (but also one of the advantages) of NATS micro, and of NATS in general, is that messages are sent as bytes. This means that the developer has to handle the serialization and deserialization of the messages. This is usually done using a library such as `protobuf` or `json`.

The goal of the typed SDK is to allow developers to easily define services and endpoints using python objects as request type and response type rather than bytes.

## Glossary

- `Application`: A collection of endpoints.

- `Channel`: An addressable destination for messages.

- `Operation`: A function called when a message is received on a specific subject.

If we try to map the concepts of the typed SDK to the concepts of the regular SDK, we can say that:

- `Application` is the equivalent of `Service`.

- `Channel` is the equivalent of `Subject`.

- `Operation` is the equivalent of `Endpoint`.

