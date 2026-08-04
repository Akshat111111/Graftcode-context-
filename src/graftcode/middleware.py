"""
graftcode.middleware
~~~~~~~~~~~~~~~~~~~~

ASGI middleware that simulates what the Graftcode Gateway does automatically
on the server side: reads incoming HTTP headers and binds them as a
:class:`RequestContext` for the duration of each request.

When your service is deployed behind the Graftcode Gateway this middleware
is not needed — the Gateway handles it for you.  Include it here only for
local development / testing without the Gateway.

Usage::

    from fastapi import FastAPI
    from graftcode.middleware import GraftcodeMiddleware

    app = FastAPI()
    app.add_middleware(GraftcodeMiddleware)

Reference: https://docs.graftcode.com/security-and-trust/graftcode-context
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from .context import GraftConfig, RequestContext, _global_headers, _global_headers_lock


class GraftcodeMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that mirrors the Graftcode Gateway's header propagation.

    For every request it:

    1. Collects all incoming HTTP headers.
    2. Merges them with any global headers set via ``GraftConfig.set_headers()``.
    3. Binds a :class:`RequestContext` scoped to the current asyncio Task so
       concurrent requests never interfere.

    The context is automatically cleared when the response is sent.

    Parameters
    ----------
    app:
        The ASGI application to wrap.
    propagate_all_headers:
        When ``True`` (default), every incoming header is forwarded.
        When ``False``, only Graftcode-standard headers are forwarded.
    """

    # Headers the Graftcode Gateway propagates by default
    GRAFTCODE_HEADERS = {
        "authorization",
        "x-correlation-id",
        "x-tenant-id",
        "x-user-id",
        "x-request-id",
        "x-trace-id",
        "x-api-key",
        "x-client-id",
        "x-session-id",
        "x-feature-flags",
        "x-forwarded-for",
        "content-type",
        "accept",
        "user-agent",
    }

    def __init__(
        self,
        app: ASGIApp,
        propagate_all_headers: bool = True,
    ) -> None:
        super().__init__(app)
        self.propagate_all_headers = propagate_all_headers

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. Collect headers
        if self.propagate_all_headers:
            incoming: dict[str, str] = dict(request.headers)
        else:
            incoming = {
                k: v
                for k, v in request.headers.items()
                if k.lower() in self.GRAFTCODE_HEADERS
            }

        # 2. Merge with global defaults (request headers win on collision)
        with _global_headers_lock:
            merged = dict(_global_headers)
        merged.update(incoming)

        # 3. Bind context for this async task
        ctx = RequestContext(merged)
        token = RequestContext._bind(ctx)
        try:
            response = await call_next(request)
        finally:
            RequestContext._unbind(token)

        return response
