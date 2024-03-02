from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse
from starlette.routing import Route

from .builder import build_spec

if TYPE_CHECKING:
    from ..application import Application


def create_docs_app(
    app: Application,
    docs_path: str = "/",
    asyncapi_path: str = "/asyncapi.json",
) -> Starlette:
    schema = build_spec(app)

    async def get_async_api(request: Request) -> PlainTextResponse:
        return PlainTextResponse(
            schema.export_json(indent=0), media_type="application/json"
        )

    async def get_docs(request: Request) -> HTMLResponse:
        return HTMLResponse(DOCS_CONTENT)

    return Starlette(
        debug=True,
        routes=[
            Route(asyncapi_path, get_async_api),
            Route(docs_path, get_docs),
        ],
    )


def create_docs_server(
    app: Application,
    port: int = 8000,
) -> Server:
    asgi_app = create_docs_app(app)
    cfg = uvicorn.Config(
        app=asgi_app,
        port=port,
        loop="asyncio",
        access_log=True,
        log_level=None,
        log_config=None,
    )
    server = Server(cfg)
    return server


class Server(uvicorn.Server):
    """A custom Uvicorn server that can be used as an async context manager."""

    def __init__(self, config: uvicorn.Config) -> None:
        super().__init__(config)
        # Track the asyncio task used to run the server
        self.task: asyncio.Task[None] | None = None

    # Override because we're catching signals ourselves
    def install_signal_handlers(self) -> None:
        pass

    async def __aenter__(self) -> "Server":
        self.task = asyncio.create_task(self.serve())
        return self

    async def __aexit__(self, *args: object, **kwargs: object) -> None:
        self.should_exit = True
        if self.task:
            await asyncio.wait([self.task])
            if self.task.cancelled():
                return
            err = self.task.exception()
            if err:
                raise err


DOCS_CONTENT = """
<html>
<style>
  body {
    margin: 0;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
      'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
      sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  code {
    font-family: source-code-pro, Menlo, Monaco, Consolas, 'Courier New',
      monospace;
  }
</style>

<body>
  <asyncapi-component schemaUrl="/asyncapi.json"
    cssImportPath="https://unpkg.com/@asyncapi/react-component@latest/styles/default.min.css">
  </asyncapi-component>
  <script src="https://unpkg.com/@asyncapi/web-component@latest/lib/asyncapi-web-component.js" defer></script>
</body>

</html>
"""
