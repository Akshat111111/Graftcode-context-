"""
vision/request_context_demo.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Plain Python class with 8 public methods that demonstrate the Graftcode Context
Library via Graftcode Vision.

Each method is auto-discovered by gg (Graftcode Gateway) at startup and exposed
as an interactive "Try it out" form at http://localhost:81/GV.

How the demo works
------------------
Graftcode Vision calls methods directly (not via HTTP), so there is no automatic
Gateway-level context injection. Each method uses GraftConfig.invoke_with_headers()
to explicitly bind headers into a RequestContext -- exactly what the Graftcode
Gateway does automatically in production before your handler runs. The binding
code is visible here so you can see the mechanism; behind the Gateway it happens
transparently.

Reference: https://docs.graftcode.com/security-and-trust/graftcode-context
"""

import asyncio
import os
import sys
import uuid
import json
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Path bootstrap
# Lets gg resolve the local graftcode library copied alongside this module in
# the Docker image at /usr/app/request-context-demo/graftcode/
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from graftcode.context import GraftConfig, RequestContext  # noqa: E402

__all__ = ["RequestContextDemo"]

# ---------------------------------------------------------------------------
# Global headers -- set once at module-load time.
#
# In a real service you call GraftConfig.set_headers() once at startup so
# every subsequent RequestContext automatically contains these headers.
# GraftConfig stores them process-wide; they appear in every context.
# ---------------------------------------------------------------------------
GraftConfig.set_headers(
    {
        "X-Service-Name": "graftcode-python-demo",
        "X-Api-Version": "v1",
        "X-Environment": "local-dev",
    }
)


class RequestContextDemo:
    """
    Graftcode Context Library -- 8 demo cases exposed via Graftcode Vision.

    Open http://localhost:81/GV after:
        docker-compose -f docker-compose.vision.yml up --build

    Each public method demonstrates one aspect of how the Graftcode Context
    Library propagates headers through your service without custom middleware
    or parameter threading.
    """

    # ------------------------------------------------------------------
    # Case 1 -- Health check + global headers
    # ------------------------------------------------------------------

    def health_check(self) -> str:
        """
        Case 1 -- Health check and global header verification.

        GraftConfig.set_headers() was called once at startup with
        X-Service-Name, X-Api-Version, and X-Environment. This method
        confirms they are automatically present in every RequestContext
        with no per-request injection.

        Gateway equivalent: GET /
        """
        ctx = RequestContext.current()
        result = {
            "service": "Graftcode Request Context Demo (Python)",
            "version": "1.0.0",
            "status": "healthy",
            "docs": "https://docs.graftcode.com/security-and-trust/graftcode-context",
            "global_headers_always_present": ctx.get_headers(),
            "explanation": (
                "GraftConfig.set_headers() was called once at startup. "
                "RequestContext.current() returns them in every context -- "
                "no per-request code required."
            ),
        }
        return json.dumps(result, indent=2, default=str)

    # ------------------------------------------------------------------
    # Case 2 -- Authorization header (success)
    # ------------------------------------------------------------------

    def auth_demo(
        self,
        authorization: str = "Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig",
    ) -> str:
        """
        Case 2 -- Authorization header propagation (success path).

        Pass a Bearer token. The method binds it into a RequestContext via
        invoke_with_headers() -- exactly what the Graftcode Gateway does
        automatically in production before your handler runs.

        Your handler code (RequestContext.current().get_header()) is identical
        whether running locally here or behind the Gateway.

        Gateway equivalent: GET /auth-demo with Authorization header set.
        """
        result: dict = {}

        def _handler() -> None:
            ctx = RequestContext.current()
            auth = ctx.get_header("Authorization")
            if not auth:
                result.update({
                    "error": "No Authorization header in context",
                    "hint": "Pass a value in the authorization field above.",
                })
                return
            token_type, _, token_value = auth.partition(" ")
            result.update({
                "message": "Authorization header read from RequestContext -- zero boilerplate",
                "token_type": token_type,
                "token_preview": (
                    f"{token_value[:16]}..." if len(token_value) > 16 else token_value
                ),
                "full_authorization": auth,
                "user_id": ctx.get_header("X-User-Id"),
                "all_headers_in_context": ctx.get_headers(),
                "how_gateway_does_it": (
                    "The Graftcode Gateway intercepts the client request, validates "
                    "the JWT, and calls invoke_with_headers() before your handler runs. "
                    "Your handler just calls RequestContext.current() -- that is it."
                ),
            })

        GraftConfig.invoke_with_headers(_handler, {"Authorization": authorization})
        return json.dumps(result, indent=2, default=str)

    # ------------------------------------------------------------------
    # Case 3 -- Authorization header missing (error)
    # ------------------------------------------------------------------

    def auth_demo_missing_token(self) -> str:
        """
        Case 3 -- Missing Authorization header -> 401-style error response.

        Shows how your handler detects an absent Authorization header via
        RequestContext.current().get_header("Authorization") returning None.

        No parameters -- the context is intentionally bound with no
        Authorization header to demonstrate the error path.

        Gateway equivalent: GET /auth-demo with no Authorization header.
        """
        result: dict = {}

        def _handler() -> None:
            ctx = RequestContext.current()
            auth = ctx.get_header("Authorization")
            result.update({
                "http_status_equivalent": 401,
                "error": "No Authorization header in context",
                "authorization_value": auth,
                "available_headers": list(ctx.get_headers().keys()),
                "hint": (
                    "In production the Graftcode Gateway rejects unauthenticated "
                    "requests before they reach your service. This case shows what "
                    "your handler sees when no Authorization header is present."
                ),
            })

        GraftConfig.invoke_with_headers(_handler, {})
        return json.dumps(result, indent=2, default=str)

    # ------------------------------------------------------------------
    # Case 4 -- Correlation ID propagation
    # ------------------------------------------------------------------

    def correlation_demo(self, x_correlation_id: str = "") -> str:
        """
        Case 4 -- X-Correlation-Id propagation via RequestContext.

        Pass a correlation ID (e.g. req-5f3a-2026) or leave blank to see
        auto-generation. In production the Graftcode Gateway stamps every
        request with a correlation ID before forwarding to your service.

        Gateway equivalent: GET /correlation-demo
        """
        result: dict = {}

        def _handler() -> None:
            ctx = RequestContext.current()
            corr_id = ctx.get_header("X-Correlation-Id")
            auto_generated = False
            if not corr_id:
                corr_id = f"auto-{uuid.uuid4()}"
                auto_generated = True
            result.update({
                "correlation_id": corr_id,
                "was_auto_generated": auto_generated,
                "message": (
                    "Correlation ID propagated from client via Graftcode Gateway"
                    if not auto_generated
                    else "No X-Correlation-Id supplied -- auto-generated for this response"
                ),
                "distributed_tracing_tip": (
                    "In production every service reads the same X-Correlation-Id "
                    "from RequestContext and includes it in logs -- end-to-end tracing "
                    "without manual propagation."
                ),
                "all_headers_in_context": ctx.get_headers(),
            })

        headers: Dict[str, str] = {}
        if x_correlation_id:
            headers["X-Correlation-Id"] = x_correlation_id
        GraftConfig.invoke_with_headers(_handler, headers)
        return json.dumps(result, indent=2, default=str)

    # ------------------------------------------------------------------
    # Case 5 -- Missing tenant ID (error)
    # ------------------------------------------------------------------

    def tenant_demo_missing_id(self) -> str:
        """
        Case 5 -- Missing X-Tenant-Id -> 400-style error response.

        In a SaaS product the Gateway resolves the tenant from the JWT or
        subdomain and injects X-Tenant-Id. This shows the error path when absent.

        No parameters -- the context is intentionally bound with no X-Tenant-Id.

        Gateway equivalent: GET /tenant-demo with no X-Tenant-Id header.
        """
        result: dict = {}

        def _handler() -> None:
            ctx = RequestContext.current()
            tenant = ctx.get_header("X-Tenant-Id")
            result.update({
                "http_status_equivalent": 400,
                "error": "X-Tenant-Id header not found in context",
                "tenant_id_value": tenant,
                "available_headers": list(ctx.get_headers().keys()),
                "hint": (
                    "In production the Graftcode Gateway resolves the tenant from "
                    "the JWT and injects X-Tenant-Id automatically. "
                    "This case shows the error path when it is absent."
                ),
            })

        GraftConfig.invoke_with_headers(_handler, {})
        return json.dumps(result, indent=2, default=str)

    # ------------------------------------------------------------------
    # Case 6 -- All propagated headers
    # ------------------------------------------------------------------

    def all_headers(
        self,
        authorization: str = "Bearer tok",
        x_correlation_id: str = "trace-001",
        x_tenant_id: str = "acme-corp",
    ) -> str:
        """
        Case 6 -- All propagated headers visible in one RequestContext.

        Pass any combination of the three common Graftcode headers. They are
        merged with the global service-identity headers set at startup --
        both per-request and global headers are always available via
        RequestContext.current().

        Gateway equivalent: GET /all-headers with multiple headers set.
        """
        result: dict = {}

        def _handler() -> None:
            ctx = RequestContext.current()
            hdrs = ctx.get_headers()
            graftcode_x = {k: v for k, v in hdrs.items() if k.lower().startswith("x-")}
            auth_hdrs = {k: v for k, v in hdrs.items() if k.lower() == "authorization"}
            other = {
                k: v for k, v in hdrs.items()
                if k not in graftcode_x and k not in auth_hdrs
            }
            result.update({
                "total_headers": len(hdrs),
                "graftcode_x_headers": graftcode_x,
                "authentication": auth_hdrs,
                "other": other,
                "raw": hdrs,
                "note": (
                    "X-Service-Name, X-Api-Version, and X-Environment are injected "
                    "globally via GraftConfig.set_headers() at startup and appear in "
                    "every context alongside the per-request headers."
                ),
            })

        per_request: Dict[str, str] = {}
        if authorization:
            per_request["Authorization"] = authorization
        if x_correlation_id:
            per_request["X-Correlation-Id"] = x_correlation_id
        if x_tenant_id:
            per_request["X-Tenant-Id"] = x_tenant_id
        GraftConfig.invoke_with_headers(_handler, per_request)
        return json.dumps(result, indent=2, default=str)

    # ------------------------------------------------------------------
    # Case 7 -- Global header enforcement
    # ------------------------------------------------------------------

    def global_headers_demo(self) -> str:
        """
        Case 7 -- GraftConfig.set_headers() enforcement.

        Headers configured once at startup are automatically available in
        every RequestContext. No per-request injection needed.

        No parameters -- global headers are already set at module load time.

        Gateway equivalent: GET /global-headers-demo
        """
        global_hdrs = GraftConfig.get_global_headers()
        ctx = RequestContext.current()
        result = {
            "global_headers_set_at_startup": global_hdrs,
            "visible_in_current_context": {k: ctx.get_header(k) for k in global_hdrs},
            "code_snippet": (
                "GraftConfig.set_headers({\n"
                '    "X-Service-Name": "graftcode-python-demo",\n'
                '    "X-Api-Version": "v1",\n'
                '    "X-Environment": "local-dev",\n'
                "})"
            ),
            "explanation": (
                "Call GraftConfig.set_headers() once at startup. Every subsequent "
                "RequestContext will automatically contain these headers -- no manual "
                "injection into each handler or function call required."
            ),
        }
        return json.dumps(result, indent=2, default=str)

    # ------------------------------------------------------------------
    # Case 8 -- Async context isolation
    # ------------------------------------------------------------------

    def async_isolation_demo(self) -> str:
        """
        Case 8 -- Async context isolation via Python contextvars.

        Spawns two concurrent asyncio tasks each with different headers via
        GraftConfig.invoke_with_headers_async(). Verifies contexts are fully
        isolated -- Task A never sees Task B's headers, even on the same event loop.

        Powered by Python's contextvars.ContextVar copy-on-write semantics for
        asyncio Tasks. No locks, no thread-locals required.

        No parameters needed.

        Gateway equivalent: GET /async-demo
        """

        async def _run() -> dict:
            async def _task(name: str, headers: Dict[str, str]) -> dict:
                async def _work() -> dict:
                    await asyncio.sleep(0.01)
                    ctx = RequestContext.current()
                    return {
                        "task": name,
                        "tenant_id": ctx.get_header("X-Tenant-Id"),
                        "correlation_id": ctx.get_header("X-Correlation-Id"),
                        "authorization": ctx.get_header("Authorization"),
                        "all_headers_seen": ctx.get_headers(),
                    }
                return await GraftConfig.invoke_with_headers_async(_work, headers)

            task_a, task_b = await asyncio.gather(
                _task(
                    "Task-A",
                    {
                        "X-Tenant-Id": "tenant-alpha",
                        "X-Correlation-Id": f"corr-alpha-{uuid.uuid4().hex[:8]}",
                        "Authorization": "Bearer alpha-token",
                    },
                ),
                _task(
                    "Task-B",
                    {
                        "X-Tenant-Id": "tenant-beta",
                        "X-Correlation-Id": f"corr-beta-{uuid.uuid4().hex[:8]}",
                        "Authorization": "Bearer beta-token",
                    },
                ),
            )

            outer_ctx = RequestContext.current()
            return {
                "message": "Two concurrent async calls with fully isolated RequestContexts",
                "task_a": task_a,
                "task_b": task_b,
                "outer_context_tenant_id": outer_ctx.get_header("X-Tenant-Id"),
                "outer_context_unchanged": True,
                "isolation_verified": (
                    task_a["tenant_id"] != task_b["tenant_id"]
                    and task_a["correlation_id"] != task_b["correlation_id"]
                ),
                "how_it_works": (
                    "Python's contextvars.ContextVar provides copy-on-write semantics "
                    "for asyncio Tasks. invoke_with_headers_async() binds a new context "
                    "for each call so concurrent requests never share or overwrite each "
                    "other's headers."
                ),
            }

        return json.dumps(asyncio.run(_run()), indent=2, default=str)
