from __future__ import annotations

import contextlib
import tempfile
from typing import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from nats_contrib.request_many import Client as NATS
from nats_contrib.test_server import NATSD


@pytest_asyncio.fixture
async def nats_client() -> AsyncIterator[NATS]:
    client = NATS()
    await client.connect()
    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
def nats_server() -> Iterator[NATSD]:
    with contextlib.ExitStack() as stack:
        tmpdir = stack.enter_context(
            tempfile.TemporaryDirectory(prefix="nats-test-server")
        )
        server = stack.enter_context(
            NATSD(
                port=4222,
                address="localhost",
                client_advertise="localhost:4222",
                server_name="test-server-01",
                server_tags={"region": "test01"},
                with_jetstream=True,
                debug=True,
                trace=True,
                trace_verbose=False,
                http_port=8222,
                websocket_listen_address="localhost",
                websocket_listen_port=10080,
                leafnodes_listen_port=7422,
                store_directory=tmpdir,
            )
        )
        yield server
