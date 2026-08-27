"""
vision/request_context_demo.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Plain Python class with 7 public methods that demonstrate the Graftcode Context
Library via Graftcode Vision.

Each method is auto-discovered by gg (Graftcode Gateway) at startup and exposed
as an interactive "Try it out" form at http://localhost:81/GV.

How the demo works
------------------
In production the Graftcode Gateway calls ``RequestContext.current().set_headers()``
before your handler runs, binding the inbound request headers into the active
context. Because Graftcode Vision calls methods directly (not via HTTP), each
method simulates that step explicitly so you can see exactly what the Gateway
does — your handler code (``RequestContext.current().get_headers()``) is
identical in both cases.

API used (graftcode-context 1.0.0)
-----------------------------------
- ``RequestContext.current()``          — returns the active RequestContext
- ``ctx.set_headers(headers)``          — sets headers on the context (Gateway calls this)
- ``ctx.get_headers()``                 — returns the bound headers (your handler calls this)
"""

import uuid
import json

from graftcode import RequestContext

__all__ = ["RequestContextDemo"]


class RequestContextDemo:
    """
    Graftcode Context Library — 7 demo cases exposed via Graftcode Vision.

    Open http://localhost:81/GV after:
        docker-compose -f docker-compose.vision.yml up --build

    Each public method demonstrates one aspect of how the Graftcode Context
    Library propagates headers through your service without custom middleware
    or parameter threading.

    The real API (graftcode-context 1.0.0):

        from graftcode import RequestContext

        ctx = RequestContext.current()
        ctx.set_headers({"Authorization": "Bearer ..."})  # Gateway does this
        headers = ctx.get_headers()                        # Your handler does this
    """

    # ------------------------------------------------------------------
    # Case 1 -- Health check
    # ------------------------------------------------------------------

    def health_check(self) -> str:
        """
        Case 1 — Health check.

        Calls RequestContext.current().get_headers() with no headers set,
        showing the empty default state. In production the Gateway always
        populates the context before your handler runs.

        Gateway equivalent: GET /
        """
        ctx = RequestContext.current()
        result = {
            "service": "Graftcode Request Context Demo (Python)",
            "version": "1.0.0",
            "status": "healthy",
            "pypi": "https://pypi.org/project/graftcode-context/",
            "headers_in_context": ctx.get_headers(),
            "explanation": (
                "No headers set yet — this is the default empty context. "
                "In production the Gateway calls set_headers() before your "
                "handler runs, so get_headers() always returns the real "
                "request headers."
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
        Case 2 — Authorization header propagation (success path).

        Pass a Bearer token. The method binds it into the current
        RequestContext via set_headers() — exactly what the Graftcode
        Gateway does automatically in production before your handler runs.

        Your handler code (get_headers()) is identical whether running
        locally here or behind the Gateway.

        Gateway equivalent: GET /auth-demo with Authorization header set.
        """
        ctx = RequestContext.current()
        ctx.set_headers({"Authorization": authorization})

        headers = ctx.get_headers()
        auth = headers.get("Authorization")

        if not auth:
            result = {
                "error": "No Authorization header in context",
                "hint": "Pass a value in the authorization field above.",
            }
            return json.dumps(result, indent=2, default=str)

        token_type, _, token_value = auth.partition(" ")
        result = {
            "message": "Authorization header read from RequestContext — zero boilerplate",
            "token_type": token_type,
            "token_preview": (
                f"{token_value[:16]}..." if len(token_value) > 16 else token_value
            ),
            "full_authorization": auth,
            "all_headers_in_context": headers,
            "how_gateway_does_it": (
                "The Graftcode Gateway intercepts the client request, validates "
                "the JWT, and calls RequestContext.current().set_headers() before "
                "your handler runs. Your handler just calls get_headers() — that is it."
            ),
        }
        return json.dumps(result, indent=2, default=str)

    # ------------------------------------------------------------------
    # Case 3 -- Authorization header missing (error)
    # ------------------------------------------------------------------

    def auth_demo_missing_token(self) -> str:
        """
        Case 3 — Missing Authorization header → 401-style error response.

        Shows how your handler detects an absent Authorization header via
        get_headers() returning an empty dict (or a dict without the key).

        No parameters — the context is intentionally bound with no headers
        to demonstrate the error path.

        Gateway equivalent: GET /auth-demo with no Authorization header.
        """
        ctx = RequestContext.current()
        ctx.set_headers({})  # Gateway called with no auth header

        headers = ctx.get_headers()
        auth = headers.get("Authorization")

        result = {
            "http_status_equivalent": 401,
            "error": "No Authorization header in context",
            "authorization_value": auth,
            "available_headers": list(headers.keys()),
            "hint": (
                "In production the Graftcode Gateway rejects unauthenticated "
                "requests before they reach your service. This case shows what "
                "your handler sees when no Authorization header is present."
            ),
        }
        return json.dumps(result, indent=2, default=str)

    # ------------------------------------------------------------------
    # Case 4 -- Correlation ID propagation
    # ------------------------------------------------------------------

    def correlation_demo(self, x_correlation_id: str = "") -> str:
        """
        Case 4 — X-Correlation-Id propagation via RequestContext.

        Pass a correlation ID (e.g. req-5f3a-2026) or leave blank to see
        auto-generation. In production the Graftcode Gateway stamps every
        request with a correlation ID before forwarding to your service.

        Gateway equivalent: GET /correlation-demo
        """
        incoming: Dict[str, str] = {}
        if x_correlation_id:
            incoming["X-Correlation-Id"] = x_correlation_id

        ctx = RequestContext.current()
        ctx.set_headers(incoming)

        headers = ctx.get_headers()
        corr_id = headers.get("X-Correlation-Id")
        auto_generated = False

        if not corr_id:
            corr_id = f"auto-{uuid.uuid4()}"
            auto_generated = True

        result = {
            "correlation_id": corr_id,
            "was_auto_generated": auto_generated,
            "message": (
                "Correlation ID propagated from client via Graftcode Gateway"
                if not auto_generated
                else "No X-Correlation-Id supplied — auto-generated for this response"
            ),
            "distributed_tracing_tip": (
                "In production every service reads the same X-Correlation-Id "
                "from RequestContext and includes it in logs — end-to-end tracing "
                "without manual propagation."
            ),
            "all_headers_in_context": headers,
        }
        return json.dumps(result, indent=2, default=str)

    # ------------------------------------------------------------------
    # Case 5 -- Missing tenant ID (error)
    # ------------------------------------------------------------------

    def tenant_demo_missing_id(self) -> str:
        """
        Case 5 — Missing X-Tenant-Id → 400-style error response.

        In a SaaS product the Gateway resolves the tenant from the JWT or
        subdomain and injects X-Tenant-Id. This shows the error path when absent.

        No parameters — the context is intentionally bound with no X-Tenant-Id.

        Gateway equivalent: GET /tenant-demo with no X-Tenant-Id header.
        """
        ctx = RequestContext.current()
        ctx.set_headers({})  # Gateway sent no tenant header

        headers = ctx.get_headers()
        tenant = headers.get("X-Tenant-Id")

        result = {
            "http_status_equivalent": 400,
            "error": "X-Tenant-Id header not found in context",
            "tenant_id_value": tenant,
            "available_headers": list(headers.keys()),
            "hint": (
                "In production the Graftcode Gateway resolves the tenant from "
                "the JWT and injects X-Tenant-Id automatically. "
                "This case shows the error path when it is absent."
            ),
        }
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
        Case 6 — All propagated headers visible in one RequestContext.

        Pass any combination of the three common Graftcode headers and see
        them all reflected back via get_headers().

        Gateway equivalent: GET /all-headers with multiple headers set.
        """
        incoming: Dict[str, str] = {}
        if authorization:
            incoming["Authorization"] = authorization
        if x_correlation_id:
            incoming["X-Correlation-Id"] = x_correlation_id
        if x_tenant_id:
            incoming["X-Tenant-Id"] = x_tenant_id

        ctx = RequestContext.current()
        ctx.set_headers(incoming)

        hdrs = ctx.get_headers()
        graftcode_x = {k: v for k, v in hdrs.items() if k.lower().startswith("x-")}
        auth_hdrs = {k: v for k, v in hdrs.items() if k.lower() == "authorization"}
        other = {
            k: v for k, v in hdrs.items()
            if k not in graftcode_x and k not in auth_hdrs
        }

        result = {
            "total_headers": len(hdrs),
            "graftcode_x_headers": graftcode_x,
            "authentication": auth_hdrs,
            "other": other,
            "raw": hdrs,
            "note": (
                "All three headers are visible in a single RequestContext.current() "
                "call — no middleware wiring, no dependency injection, no parameter "
                "threading required."
            ),
        }
        return json.dumps(result, indent=2, default=str)

    # ------------------------------------------------------------------
    # Case 7 -- Context replace
    # ------------------------------------------------------------------

    def context_replace_demo(
        self,
        first_tenant: str = "tenant-alpha",
        second_tenant: str = "tenant-beta",
    ) -> str:
        """
        Case 7 — set_headers() replaces the full context.

        Demonstrates that calling set_headers() again on the same context
        replaces the previous headers entirely. This mirrors what happens
        when the Gateway sets a new request context for each inbound call.

        Gateway equivalent: two sequential requests with different tenants.
        """
        ctx = RequestContext.current()

        ctx.set_headers({"X-Tenant-Id": first_tenant, "X-Request": "first"})
        first_snapshot = dict(ctx.get_headers())

        ctx.set_headers({"X-Tenant-Id": second_tenant, "X-Request": "second"})
        second_snapshot = dict(ctx.get_headers())

        result = {
            "after_first_set_headers": first_snapshot,
            "after_second_set_headers": second_snapshot,
            "tenant_changed": first_snapshot.get("X-Tenant-Id") != second_snapshot.get("X-Tenant-Id"),
            "explanation": (
                "set_headers() replaces all headers on the RequestContext instance. "
                "The Gateway calls this once per request before your handler runs, "
                "so each request always starts with a fresh, correct context."
            ),
        }
        return json.dumps(result, indent=2, default=str)

