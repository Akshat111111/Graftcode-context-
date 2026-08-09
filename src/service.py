"""
service.py
~~~~~~~~~~

FastAPI demo service showcasing the Graftcode Context Library for Python.

This service demonstrates how Graftcode Context propagates HTTP request
headers (authentication tokens, correlation IDs, tenant IDs) into your
service handlers without any custom middleware or boilerplate.

Official docs: https://docs.graftcode.com/security-and-trust/graftcode-context
Python package: https://pypi.org/project/graftcode-context/

Endpoints
---------
GET  /                      — Health check + context summary
GET  /auth-demo             — Reading Authorization header
GET  /correlation-demo      — Reading X-Correlation-Id header
GET  /tenant-demo           — Reading X-Tenant-Id header
GET  /all-headers           — All propagated headers
GET  /global-headers-demo   — GraftConfig.set_headers() demonstration
GET  /async-demo            — Async context isolation
POST /invoke-demo           — GraftConfig.invoke_with_headers() demonstration

Run locally
-----------
    uvicorn src.service:app --reload --port 8000

With Docker
-----------
    docker-compose up
"""

import asyncio
import uuid
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class InvokeRequest(BaseModel):
    """Request body for the /invoke-demo endpoint."""
    headers: Dict[str, str] = {
        "Authorization": "Bearer per-call-token",
        "X-Tenant-Id": "demo-tenant",
        "X-Correlation-Id": "per-call-corr-999",
    }

    model_config = {
        "json_schema_extra": {
            "example": {
                "headers": {
                    "Authorization": "Bearer per-call-token",
                    "X-Tenant-Id": "demo-tenant",
                    "X-Correlation-Id": "per-call-corr-999",
                }
            }
        }
    }

from graftcode import GraftConfig, RequestContext
from graftcode.middleware import GraftcodeMiddleware

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Graftcode Request Context Demo",
    description=(
        "Demonstrates how **Graftcode Context** propagates HTTP request headers "
        "(auth tokens, correlation IDs, tenant IDs) through Python services.\n\n"
        "Reference: https://docs.graftcode.com/security-and-trust/graftcode-context\n"
        "Package: https://pypi.org/project/graftcode-context/"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# GraftcodeMiddleware simulates what the Graftcode Gateway does automatically:
# it reads incoming HTTP headers and populates RequestContext before your
# handler runs.  When deployed behind the Gateway, this is not needed.
app.add_middleware(GraftcodeMiddleware, propagate_all_headers=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# GraftConfig.set_headers() — Global headers (set once at startup)
#
# These are injected into every RequestContext.  Typically used for
# service identity metadata that never changes between requests.
# ---------------------------------------------------------------------------
GraftConfig.set_headers(
    {
        "X-Service-Name": "graftcode-python-demo",
        "X-Api-Version": "v1",
        "X-Environment": "local-dev",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _summarise(ctx: RequestContext) -> Dict[str, Any]:
    """Serialise a RequestContext to a JSON-friendly dict."""
    return {
        "authorization": ctx.get_header("Authorization"),
        "correlation_id": ctx.get_header("X-Correlation-Id"),
        "tenant_id": ctx.get_header("X-Tenant-Id"),
        "user_id": ctx.get_header("X-User-Id"),
        "all_headers": ctx.get_headers(),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/", tags=["Health"])
async def root():
    """
    Health-check.  Returns service info and a summary of the active
    RequestContext so you can verify that global headers are injected.
    """
    ctx = RequestContext.current()
    return {
        "service": "Graftcode Request Context Demo (Python)",
        "version": "1.0.0",
        "status": "healthy",
        "docs": "https://docs.graftcode.com/security-and-trust/graftcode-context",
        "context_summary": _summarise(ctx),
    }


# ---------------------------------------------------------------------------
# 1. Authentication header demo
# ---------------------------------------------------------------------------


@app.get("/auth-demo", tags=["Demos"])
async def auth_demo():
    """
    Reads the ``Authorization`` header via ``RequestContext.current().get_headers()``.

    Graftcode Gateway automatically forwards this header from the original
    client request — no middleware configuration or function parameters needed.

    ```
    curl -H "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9..." \\
         http://localhost:8000/auth-demo
    ```
    """
    # The single line every handler needs — no dependency injection required
    ctx = RequestContext.current()
    headers = ctx.get_headers()

    auth = ctx.get_header("Authorization")

    if not auth:
        return JSONResponse(
            status_code=401,
            content={
                "error": "No Authorization header in context",
                "hint": 'Add -H "Authorization: Bearer <token>" to your request',
                "available_headers": list(headers.keys()),
            },
        )

    token_type, _, token_value = auth.partition(" ")
    return {
        "message": "Authorization header read from RequestContext — zero boilerplate",
        "token_type": token_type,
        "token_preview": (
            f"{token_value[:16]}..." if len(token_value) > 16 else token_value
        ),
        "full_authorization": auth,
        "user_id": ctx.get_header("X-User-Id"),
        "how_graftcode_works": (
            "The Graftcode Gateway intercepts the client request, validates the JWT, "
            "and forwards the Authorization header to your service.  Inside the handler "
            "you call RequestContext.current().get_headers() — that's it."
        ),
    }


# ---------------------------------------------------------------------------
# 2. Correlation ID demo
# ---------------------------------------------------------------------------


@app.get("/correlation-demo", tags=["Demos"])
async def correlation_demo():
    """
    Reads ``X-Correlation-Id`` via ``RequestContext.current().get_headers()``.

    Correlation IDs let you trace one logical operation across dozens of
    microservices.  Graftcode Gateway stamps every request automatically.

    ```
    curl -H "X-Correlation-Id: req-5f3a-2026" \\
         http://localhost:8000/correlation-demo
    ```
    """
    ctx = RequestContext.current()
    corr_id = ctx.get_header("X-Correlation-Id")

    auto_generated = False
    if not corr_id:
        corr_id = f"auto-{uuid.uuid4()}"
        auto_generated = True

    return {
        "correlation_id": corr_id,
        "was_auto_generated": auto_generated,
        "message": (
            "Correlation ID propagated from client via Graftcode Gateway"
            if not auto_generated
            else "No X-Correlation-Id supplied — auto-generated for this response"
        ),
        "distributed_tracing_tip": (
            "In production every service in the call chain reads the same "
            "X-Correlation-Id from RequestContext and includes it in logs, "
            "enabling end-to-end request tracing without manual propagation."
        ),
    }


# ---------------------------------------------------------------------------
# 3. Tenant ID demo
# ---------------------------------------------------------------------------


@app.get("/tenant-demo", tags=["Demos"])
async def tenant_demo():
    """
    Reads ``X-Tenant-Id`` via ``RequestContext.current().get_headers()``.

    In a SaaS product the Gateway resolves the tenant from the JWT or
    sub-domain and injects ``X-Tenant-Id`` before forwarding to your service.

    ```
    curl -H "X-Tenant-Id: acme-corp" \\
         http://localhost:8000/tenant-demo
    ```
    """
    ctx = RequestContext.current()
    tenant = ctx.get_header("X-Tenant-Id")

    if not tenant:
        return JSONResponse(
            status_code=400,
            content={
                "error": "X-Tenant-Id header not found in context",
                "hint": 'Add -H "X-Tenant-Id: your-tenant" to your request',
            },
        )

    # Simulate per-tenant configuration look-up
    tenant_configs = {
        "acme-corp": {"plan": "enterprise", "region": "us-east-1", "sla": "99.99%"},
        "startup-co": {"plan": "growth", "region": "eu-west-1", "sla": "99.9%"},
        "demo-tenant": {"plan": "free", "region": "us-west-2", "sla": "99%"},
    }

    config = tenant_configs.get(
        tenant, {"plan": "unknown", "region": "unknown", "sla": "N/A"}
    )

    return {
        "tenant_id": tenant,
        "tenant_config": config,
        "message": f"Serving request for tenant '{tenant}'",
        "how_graftcode_works": (
            "RequestContext.current().get_headers() gives you X-Tenant-Id anywhere "
            "in the call stack — no need to thread it through every function parameter."
        ),
    }


# ---------------------------------------------------------------------------
# 4. All-headers demo
# ---------------------------------------------------------------------------


@app.get("/all-headers", tags=["Demos"])
async def all_headers_demo():
    """
    Returns **every** header in the current RequestContext — including the
    global headers injected via ``GraftConfig.set_headers()`` at startup.

    ```
    curl -H "Authorization: Bearer token" \\
         -H "X-Correlation-Id: trace-001" \\
         -H "X-Tenant-Id: acme-corp" \\
         http://localhost:8000/all-headers
    ```
    """
    headers = RequestContext.current().get_headers()

    graftcode_x_headers = {k: v for k, v in headers.items() if k.lower().startswith("x-")}
    auth_headers = {k: v for k, v in headers.items() if k.lower() == "authorization"}
    other_headers = {
        k: v
        for k, v in headers.items()
        if k not in graftcode_x_headers and k not in auth_headers
    }

    return {
        "total_headers": len(headers),
        "graftcode_x_headers": graftcode_x_headers,
        "authentication": auth_headers,
        "other": other_headers,
        "raw": headers,
        "note": (
            "X-Service-Name, X-Api-Version, and X-Environment are injected globally "
            "via GraftConfig.set_headers() at service startup and appear in every context."
        ),
    }


# ---------------------------------------------------------------------------
# 5. Global headers demo
# ---------------------------------------------------------------------------


@app.get("/global-headers-demo", tags=["Demos"])
async def global_headers_demo():
    """
    Demonstrates ``GraftConfig.set_headers()`` — headers configured once at
    startup that are available in every RequestContext automatically.

    ```
    curl http://localhost:8000/global-headers-demo
    ```
    """
    global_hdrs = GraftConfig.get_global_headers()
    ctx = RequestContext.current()
    headers = ctx.get_headers()

    return {
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
            "Call GraftConfig.set_headers() once at startup.  Every subsequent "
            "RequestContext will automatically contain these headers — no manual "
            "injection into each handler or function call required."
        ),
    }


# ---------------------------------------------------------------------------
# 6. invoke_with_headers demo (per-call override)
# ---------------------------------------------------------------------------


@app.post("/invoke-demo", tags=["Demos"])
async def invoke_demo(body: InvokeRequest):
    """
    Demonstrates ``GraftConfig.invoke_with_headers()`` — the per-call
    header override API.

    Send ``{"headers": {...}}`` in the request body.  The endpoint will
    invoke a simulated service call with those headers merged on top of
    the current context, then return both the outer and inner header sets
    so you can see the isolation.

    ```
    curl -X POST http://localhost:8000/invoke-demo \\
         -H "Content-Type: application/json" \\
         -d '{"headers": {"Authorization": "Bearer per-call-token", "X-Tenant-Id": "demo"}}'
    ```
    """
    override_headers: Dict[str, str] = body.headers

    # Capture the outer (request-scoped) context
    outer_headers = RequestContext.current().get_headers()

    # ------------------------------------------------------------------
    # GraftConfig.invoke_with_headers(callable, headers)
    #
    # The official API takes a callable and a headers dict.
    # The callable is invoked with the merged context active.
    # The outer context is automatically restored afterwards.
    # ------------------------------------------------------------------
    inner_headers: Dict[str, str] = {}

    def _capture_inner_context():
        """Simulates a downstream Graft call — reads headers from context."""
        ctx = RequestContext.current()
        inner_headers.update(ctx.get_headers())
        return {"status": "ok", "headers_seen": dict(inner_headers)}

    result = GraftConfig.invoke_with_headers(_capture_inner_context, override_headers)

    # Verify outer context was restored
    restored_headers = RequestContext.current().get_headers()

    return {
        "outer_context_before_call": outer_headers,
        "per_call_override_applied": override_headers,
        "inner_context_during_call": inner_headers,
        "outer_context_after_call": restored_headers,
        "context_correctly_restored": outer_headers == restored_headers,
        "inner_result": result,
        "code_snippet": (
            "result = GraftConfig.invoke_with_headers(\n"
            "    lambda: MyService.do_something(),\n"
            '    {"Authorization": "Bearer per-call-token"},\n'
            ")"
        ),
        "explanation": (
            "invoke_with_headers() creates an isolated context for the duration of "
            "the callable.  Concurrent requests are never affected.  The outer context "
            "is automatically restored when the callable returns."
        ),
    }


# ---------------------------------------------------------------------------
# 7. Async context isolation demo
# ---------------------------------------------------------------------------


@app.get("/async-demo", tags=["Demos"])
async def async_demo():
    """
    Demonstrates that Graftcode Context is fully async-safe.

    Spawns two concurrent tasks, each with different headers via
    ``GraftConfig.invoke_with_headers_async()``, and shows that
    the contexts are completely isolated from each other.

    ```
    curl http://localhost:8000/async-demo
    ```
    """

    async def _simulated_service_call(task_name: str, headers: Dict[str, str]) -> dict:
        """Simulate a downstream async Graft call with its own context."""

        async def _async_work():
            await asyncio.sleep(0.01)  # simulate I/O
            ctx = RequestContext.current()
            hdrs = ctx.get_headers()
            return {
                "task": task_name,
                "headers_seen": hdrs,
                "correlation_id": ctx.get_header("X-Correlation-Id"),
                "tenant_id": ctx.get_header("X-Tenant-Id"),
            }

        # invoke_with_headers_async takes a callable returning a coroutine
        return await GraftConfig.invoke_with_headers_async(_async_work, headers)

    # Launch two concurrent tasks — each has a completely isolated context
    task_a, task_b = await asyncio.gather(
        _simulated_service_call(
            "Task-A",
            {
                "X-Tenant-Id": "tenant-alpha",
                "X-Correlation-Id": f"corr-alpha-{uuid.uuid4().hex[:8]}",
                "Authorization": "Bearer alpha-token",
            },
        ),
        _simulated_service_call(
            "Task-B",
            {
                "X-Tenant-Id": "tenant-beta",
                "X-Correlation-Id": f"corr-beta-{uuid.uuid4().hex[:8]}",
                "Authorization": "Bearer beta-token",
            },
        ),
    )

    outer = RequestContext.current()
    outer_headers = outer.get_headers()

    return {
        "message": "Two concurrent async calls with fully isolated RequestContexts",
        "task_a": task_a,
        "task_b": task_b,
        "outer_context_unchanged": {
            "tenant_id": outer.get_header("X-Tenant-Id"),
            "correlation_id": outer.get_header("X-Correlation-Id"),
        },
        "isolation_verified": (
            task_a["tenant_id"] != task_b["tenant_id"]
            and task_a["correlation_id"] != task_b["correlation_id"]
        ),
        "how_it_works": (
            "Python's contextvars.ContextVar provides copy-on-write semantics for "
            "asyncio Tasks.  invoke_with_headers_async() binds a new context for each "
            "call so concurrent requests never share or overwrite each other's headers."
        ),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.service:app", host="0.0.0.0", port=8000, reload=True)
