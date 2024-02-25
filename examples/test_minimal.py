import pytest

from nats_contrib.micro.testing import make_request

from .with_setup import echo


@pytest.mark.asyncio
async def test_echo_handler():
    request = make_request("echo", b"hello")
    await echo(request)
    assert request.response_data() == b"hello"
    assert request.response_headers() == {}
