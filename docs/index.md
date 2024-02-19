# NATS Micro for Python

!!!warning "This is not an official NATS project"
    This is a personal project and is not endorsed by the NATS.io community. It is not guaranteed to be maintained or supported.

!!!bug "This is an experimental project"
    This project is a prototype and should not be used for anything serious. It is not tested, nor is it guaranteed to be correct.

The [micro](https://pkg.go.dev/github.com/nats-io/nats.go/micro) package in the [NATS.go](https://github.com/nats-io/nats.go) library provides a simple way to create microservices that leverage NATS for scalability, load management and observability.

This project is an attempt to implement the same API in Python.

## References

- The reference document for NATS Micro is the [ADR-32: Service API](https://github.com/nats-io/nats-architecture-and-design/blob/main/adr/ADR-32.md).

- The reference implementation is the [Go micro package](https://pkg.go.dev/github.com/nats-io/nats.go/micro).

- A typescript implementation is available in [nats.deno](https://github.com/nats-io/nats.deno/blob/main/nats-base-client/service.ts)

## Why does this exist ?

- I wanted to give a try to implementing the [ADR-32](https://github.com/nats-io/nats-architecture-and-design/blob/main/adr/ADR-32.md) in Python.

- Maybe this can help getting an official implementation [in the NATS Python client](https://github.com/nats-io/nats.py/discussions/532#discussioncomment-8509804).

## What's lacking ?

- There is no test, and it may not be correct.

## How to install

<!-- termynal -->

```bash
$ pip install git+https://github.com/charbonnierg/nats-micro.git
```

## API Proposal

The API is inspired by the [Go micro package](https://pkg.go.dev/github.com/nats-io/nats.go/micro):

- In order to use the package, you need to create a NATS connection using the [nats-py](https://nats-io.github.io/nats.py/) package:

``` py
from nats.aio.client import Client

# Somewhere in an async function
nc = await Client().connect("nats://localhost:4222")
```

- Create a new service with [`micro.add_service`](https://charbonnierg.github.io/nats-micro/reference/micro/#micro.add_service):

``` py
import micro


service = micro.add_service(
    nc,
    name="demo-service",
    version="1.0.0",
    description="Demo service",
)
```

- Unlike the Go implementation, the service is not started automatically. You need to call [`service.start`](https://charbonnierg.github.io/nats-micro/reference/micro/#micro.Service.start) to start the service, or use the service as an async context manager which allows to both create and start the service in a single line:

``` py
async with micro.add_service(
    nc,
    name="demo-service",
    version="1.0.0",
    description="Demo service",
) as service:
    ...
```

- Once service is started, you can add endpoints to the service using [`Service.add_endpoint`](https://charbonnierg.github.io/nats-micro/reference/micro/#micro.Service.add_endpoint):

``` py
async def echo(req: micro.Request) -> None:
    """Echo the request data back to the client."""
    await req.respond(req.data())


await service.add_endpoint(
    name="echo",
    handler=echo,
)
```

As [defined in the ADR](https://github.com/nats-io/nats-architecture-and-design/blob/main/adr/ADR-32.md#endpoints), an endpoint must provide at least a name and a handler. The handler is a coroutine that takes a [`micro.Request`](https://charbonnierg.github.io/nats-micro/reference/micro/#micro.Request) as its only argument and returns `None`.

If no subject is provided, the endpoint will use the service name as the subject. It's possible to provide a subject with the `subject` argument:

``` py
await service.add_endpoint(
    name="echo",
    handler=echo,
    subject="ECHO",
)
```

- You can also add [groups](https://charbonnierg.github.io/nats-micro/reference/micro/#micro.Group) to the service:

``` py
group = service.add_group("demo")
```

As [defined in the ADR](https://github.com/nats-io/nats-architecture-and-design/blob/main/adr/ADR-32.md#groups), a [group](https://charbonnierg.github.io/nats-micro/reference/micro/#micro.Group) serves as a common prefix to all endpoints registered in it.

- You can add endpoints to a group using [`Group.add_endpoint`](https://charbonnierg.github.io/nats-micro/reference/micro/#micro.Group.add_endpoint)

``` py
await group.add_endpoint(
    name="echo",
    handler=echo,
)
```

This is equivalent to adding an endpoint to the service with the subject prefixed by the group name.

- Once you're done, you can stop the service with [`service.stop()`](https://charbonnierg.github.io/nats-micro/reference/micro/#micro.Service.stop) if it was not used as an async context manager:

``` py
await service.stop()
```

- You can check if the stop() method was called with [`service.stopped`](https://charbonnierg.github.io/nats-micro/reference/micro/#micro.Service.stopped):

``` py
assert service.stopped
```

## Example usage

This example shows how to create a simple service that echoes the request data back to the client and to run it until the application receives a SIGINT or a SIGTERM signal.


``` py linenums="1" hl_lines="145-147" title="examples/minimal.py"
import asyncio
import contextlib
import signal

from nats.aio.client import Client

import micro


async def echo(req: micro.Request) -> None:
    """Echo the request data back to the client."""
    await req.respond(req.data())


async def main():
    # Define an event to signal when to quit
    quit_event = asyncio.Event()
    # Attach signal handler to the event loop
    loop = asyncio.get_event_loop()
    for sig in (signal.Signals.SIGINT, signal.Signals.SIGTERM):
        loop.add_signal_handler(sig, lambda *_: quit_event.set())
    # Create an async exit stack
    async with contextlib.AsyncExitStack() as stack:
        # Create a NATS client
        nc = Client()
        # Connect to NATS
        await nc.connect("nats://localhost:4222")
        # Push the client.close() method into the stack to be called on exit
        stack.push_async_callback(nc.close)
        # Push a new micro service into the stack to be stopped on exit
        # The service will be stopped and drain its subscriptions before
        # closing the connection.
        service = await stack.enter_async_context(
            micro.add_service(
                nc,
                name="demo-service",
                version="1.0.0",
                description="Demo service",
            )
        )
        group = service.add_group("demo")
        # Add an endpoint to the service
        await group.add_endpoint(
            name="echo",
            handler=echo,
        )
        # Wait for the quit event
        await quit_event.wait()


if __name__ == "__main__":
    asyncio.run(main())
```

After you've cloned the repo, you can run the example above with

<!-- termynal -->

```bash
$ python examples/minimal.py
```

Once the service is running, you can use the `nats` CLI tool to send a request to the `demo.echo` subject:

<!-- termynal -->

```bash
$ nats req demo.echo "Hello, world!"

21:14:34 Sending request on "demo.echo"
21:14:34 Received with rtt 5.1048ms
Hello, World!
```

You should receive the same message back from the service.

You can also use the `nats` CLI tool to discover the service:

<!-- termynal -->

```bash
$ nats micro ls

╭──────────────────────────────────────────────────────────────────╮
│                        All Micro Services                        │
├──────────────┬─────────┬──────────────────────────┬──────────────┤
│ Name         │ Version │ ID                       │ Description  │
├──────────────┼─────────┼──────────────────────────┼──────────────┤
│ demo-service │ 1.0.0   │ ec17c596d93a7f3dafce9570 │ Demo service │
╰──────────────┴─────────┴──────────────────────────┴──────────────╯
```


You can also use the `nats` CLI tool to request service stats:

<!-- termynal -->

```bash
$ nats micro info demo-service

Service Information

        Service: demo-service (ec17c596d93a7f3dafce9570)
    Description: Demo service
        Version: 1.0.0

Endpoints:

            Name: echo
            Subject: demo.echo
        Queue Group: q

Statistics for 1 Endpoint(s):

echo Endpoint Statistics:

        Requests: 0 in group q
    Processing Time: 0s (average 0s)
            Started: 2024-02-17 13:51:46 (51.15s ago)
            Errors: 0

Endpoint Specific Statistics:
```
