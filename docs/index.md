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

## Code Complexity

I used [scc](https://github.com/boyter/scc) to count line of codes and get an idea of the complexity of the project:

<table id="scc-table">
	<thead><tr>
		<th>Language</th>
		<th>Files</th>
		<th>Lines</th>
		<th>Blank</th>
		<th>Comment</th>
		<th>Code</th>
		<th>Complexity</th>
		<th>Bytes</th>
	</tr></thead>
	<tbody><tr>
		<th>Python</th>
		<th>7</th>
		<th>1013</th>
		<th>107</th>
		<th>213</th>
		<th>693</th>
		<th>36</th>
		<th>33264</th>
	</tr><tr>
        <td><a href="https://github.com/charbonnierg/nats-micro/blob/main/src/micro/api.py" target="_blank">src/micro/api.py</a></td>
		<td></td>
		<td>450</td>
		<td>39</td>
		<td>135</td>
		<td>276</td>
		<td>21</td>
	    <td>16881</td>
	</tr><tr>
        <td><a href="https://github.com/charbonnierg/nats-micro/blob/main/src/micro/internal.py" target="_blank">src/micro/internal.py</a></td>
		<td></td>
		<td>256</td>
		<td>30</td>
		<td>39</td>
		<td>187</td>
		<td>7</td>
	    <td>7245</td>
	</tr><tr>
        <td><a href="https://github.com/charbonnierg/nats-micro/blob/main/src/micro/request.py" target="_blank">src/micro/request.py</a></td>
		<td></td>
		<td>124</td>
		<td>10</td>
		<td>29</td>
		<td>85</td>
		<td>2</td>
	    <td>3826</td>
	</tr><tr>
		<td><a href="https://github.com/charbonnierg/nats-micro/blob/main/src/micro/models.py" target="_blank">src/micro/models.py</a></td>
		<td></td>
		<td>87</td>
		<td>20</td>
		<td>5</td>
		<td>62</td>
		<td>2</td>
	    <td>1834</td>
	</tr><tr>
        <td><a href="https://github.com/charbonnierg/nats-micro/blob/main/src/micro/testing.py" target="_blank">src/micro/testing.py</a></td>
		<td></td>
		<td>80</td>
		<td>7</td>
		<td>5</td>
		<td>68</td>
		<td>4</td>
	    <td>3120</td>
	</tr><tr>
        <td><a href="https://github.com/charbonnierg/nats-micro/blob/main/src/micro/__init__.py" target="_blank">src/micro/__init__.py</a></td>
		<td></td>
		<td>15</td>
		<td>1</td>
		<td>0</td>
		<td>14</td>
		<td>0</td>
	    <td>332</td>
	</tr><tr>
        <td><a href="https://github.com/charbonnierg/nats-micro/blob/main/src/micro/__about__.py" target="_blank">src/micro/__about__.py</a></td>
		<td></td>
		<td>1</td>
		<td>0</td>
		<td>0</td>
		<td>1</td>
		<td>0</td>
	    <td>26</td>
	</tr></tbody>
	<tfoot><tr>
		<th>Total</th>
		<th>7</th>
		<th>1013</th>
		<th>107</th>
		<th>213</th>
		<th>693</th>
		<th>36</th>
    	<th>33264</th>
	</tr></tfoot>
</table>

As of now, the project is less than 1000 lines of code, with a cyclomatic complexity of 36. The [`api.py`](https://github.com/charbonnierg/nats-micro/blob/main/src/micro/api.py) file is the most complex but should still be easy to understand.


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

## Other works

- [NATS Request Many](https://charbonats.github.io/nats-request-many)

- [NATS Connect Opts](https://charbonats.github.io/nats-connect-opts)
