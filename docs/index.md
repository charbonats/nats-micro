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
$ pip install git+https://github.com/charbonats/nats-micro.git
```

## API Proposal

The API is inspired by the [Go micro package](https://pkg.go.dev/github.com/nats-io/nats.go/micro):

- In order to use the package, you need to create a NATS connection using the [nats-py](https://nats-io.github.io/nats.py/) package:

``` py
from nats.aio.client import Client

# Somewhere in an async function
nc = await Client().connect("nats://localhost:4222")
```

- Create a new service with [`micro.add_service`](https://charbonats.github.io/nats-micro/reference/micro/#micro.add_service):

``` py
from nats_contrib import micro


service = micro.add_service(
    nc,
    name="demo-service",
    version="1.0.0",
    description="Demo service",
)
```

- Unlike the Go implementation, the service is not started automatically. You need to call [`service.start`](https://charbonats.github.io/nats-micro/reference/micro/#micro.Service.start) to start the service, or use the service as an async context manager which allows to both create and start the service in a single line:

``` py
async with micro.add_service(
    nc,
    name="demo-service",
    version="1.0.0",
    description="Demo service",
) as service:
    ...
```

- Once service is started, you can add endpoints to the service using [`Service.add_endpoint`](https://charbonats.github.io/nats-micro/reference/micro/#micro.Service.add_endpoint):

``` py
async def echo(req: micro.Request) -> None:
    """Echo the request data back to the client."""
    await req.respond(req.data())


await service.add_endpoint(
    name="echo",
    handler=echo,
)
```

As [defined in the ADR](https://github.com/nats-io/nats-architecture-and-design/blob/main/adr/ADR-32.md#endpoints), an endpoint must provide at least a name and a handler. The handler is a coroutine that takes a [`micro.Request`](https://charbonats.github.io/nats-micro/reference/micro/#micro.Request) as its only argument and returns `None`.

If no subject is provided, the endpoint will use the service name as the subject. It's possible to provide a subject with the `subject` argument:

``` py
await service.add_endpoint(
    name="echo",
    handler=echo,
    subject="ECHO",
)
```

- You can also add [groups](https://charbonats.github.io/nats-micro/reference/micro/#micro.Group) to the service:

``` py
group = service.add_group("demo")
```

As [defined in the ADR](https://github.com/nats-io/nats-architecture-and-design/blob/main/adr/ADR-32.md#groups), a [group](https://charbonats.github.io/nats-micro/reference/micro/#micro.Group) serves as a common prefix to all endpoints registered in it.

- You can add endpoints to a group using [`Group.add_endpoint`](https://charbonats.github.io/nats-micro/reference/micro/#micro.Group.add_endpoint)

``` py
await group.add_endpoint(
    name="echo",
    handler=echo,
)
```

This is equivalent to adding an endpoint to the service with the subject prefixed by the group name.

- Once you're done, you can stop the service with [`service.stop()`](https://charbonats.github.io/nats-micro/reference/micro/#micro.Service.stop) if it was not used as an async context manager:

``` py
await service.stop()
```

- You can check if the stop() method was called with [`service.stopped`](https://charbonats.github.io/nats-micro/reference/micro/#micro.Service.stopped):

``` py
assert service.stopped
```

## Example usage

This example shows how to create a simple service that echoes the request data back to the client and to run it until the application receives a SIGINT or a SIGTERM signal.


``` py linenums="1" title="examples/minimal.py"
from nats_contrib import micro


async def echo(req: micro.Request) -> None:
    """Echo the request data back to the client."""
    await req.respond(req.data())


async def setup(ctx: micro.sdk.Context) -> None:
    """Configure the service.

    This function is executed after the NATS connection is established.
    """
    # Connect to NATS and close it when the context is closed
    # micro.add_service returns an AsyncContextManager that will
    # start the service when entered and stop it when exited.
    service = await ctx.add_service(
        name="demo-service",
        version="1.0.0",
        description="Demo service",
    )
    # A group is a collection of endpoints with
    # the same subject prefix.
    group = service.add_group("demo")
    # Add an endpoint to the service
    await group.add_endpoint(
        name="echo",
        subject="ECHO",
        handler=echo,
    )
```

After you've cloned the repo and install the project, you can run the example above with the help of the `micro` CLI tool:

<!-- termynal -->

```bash
$ micro run examples/minimal.py
```

Once the service is running, you can use the `micro` CLI tool to send a request to the `demo.ECHO` subject:

<!-- termynal -->

```bash
$ micro request demo.ECHO "Hello, world!"

Hello, World!
```

You should receive the same message back from the service.

You can also use the `micro` CLI tool to discover the service:

<!-- termynal -->

```bash
$ micro ping

[
  {
    "name": "demo-service",
    "id": "c9538e45b3739a339a217d26f3bcb376",
    "version": "1.0.0",
    "metadata": {},
    "type": "io.nats.micro.v1.ping_response"
  }
]
```


You can also use the `micro` CLI tool to request service stats:

<!-- termynal -->

```bash
$ micro info demo-service

[
  {
    "name": "demo-service",
    "id": "c9538e45b3739a339a217d26f3bcb376",
    "version": "1.0.0",
    "description": "Demo service",
    "metadata": {},
    "endpoints": [
      {
        "name": "echo",
        "subject": "demo.ECHO",
        "metadata": {},
        "queue_group": "q"
      }
    ],
    "type": "io.nats.micro.v1.info_response"
  }
]
```

You can also use the `micro` CLI tool to request service stats:

<!-- termynal -->

```bash
$ micro stats demo-service

[
  {
    "name": "demo-service",
    "id": "c9538e45b3739a339a217d26f3bcb376",
    "version": "1.0.0",
    "started": "2024-02-27T00:01:31.555469Z",
    "endpoints": [
      {
        "name": "echo",
        "subject": "demo.ECHO",
        "num_requests": 4,
        "num_errors": 0,
        "last_error": "",
        "processing_time": 875900,
        "average_processing_time": 218975,
        "queue_group": "q",
        "data": {}
      }
    ],
    "metadata": {},
    "type": "io.nats.micro.v1.stats_response"
  }
]
```

## Other works

- [NATS Request Many](https://charbonats.github.io/nats-request-many)

- [NATS Connect Opts](https://charbonats.github.io/nats-connect-opts)
