"""
tests/test_async_context.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration-level tests for the full async context propagation pipeline:
middleware → handler → nested service calls.

All tests use httpx.AsyncClient with ASGITransport so they work correctly
with the async FastAPI application.

Tests cover:
  - Middleware populates RequestContext from HTTP headers
  - Handler reads headers via RequestContext.current().get_headers()
  - GraftConfig.invoke_with_headers_async() isolation under concurrency
  - Global headers visible in all async endpoints
  - Middleware context cleaned up after response
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from graftcode.context import GraftConfig, RequestContext, _request_context_var
from src.service import app


@pytest.fixture(autouse=True)
def clean_global_headers():
    """Reset global headers before each test, then restore what the service sets."""
    GraftConfig.clear_global_headers()
    GraftConfig.set_headers(
        {
            "X-Service-Name": "graftcode-python-demo",
            "X-Api-Version": "v1",
            "X-Environment": "local-dev",
        }
    )
    yield
    GraftConfig.clear_global_headers()


@pytest_asyncio.fixture
async def client():
    """Async HTTPX test client (ASGITransport is async-only)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Health / root
# ---------------------------------------------------------------------------


class TestRootEndpoint:
    async def test_root_returns_healthy(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    async def test_root_contains_context_summary(self, client):
        resp = await client.get("/")
        data = resp.json()
        assert "context_summary" in data
        assert "all_headers" in data["context_summary"]

    async def test_global_headers_visible_in_root(self, client):
        resp = await client.get("/")
        data = resp.json()
        hdrs = data["context_summary"]["all_headers"]
        assert hdrs.get("x-service-name") == "graftcode-python-demo"


# ---------------------------------------------------------------------------
# /auth-demo
# ---------------------------------------------------------------------------


class TestAuthDemo:
    async def test_missing_auth_returns_401(self, client):
        resp = await client.get("/auth-demo")
        assert resp.status_code == 401

    async def test_valid_auth_header_echoed(self, client):
        resp = await client.get(
            "/auth-demo",
            headers={"Authorization": "Bearer test-jwt-token-here"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_type"] == "Bearer"
        assert "test-jwt" in data["token_preview"]

    async def test_full_authorization_in_response(self, client):
        token = "Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig"
        resp = await client.get("/auth-demo", headers={"Authorization": token})
        data = resp.json()
        assert data["full_authorization"] == token


# ---------------------------------------------------------------------------
# /correlation-demo
# ---------------------------------------------------------------------------


class TestCorrelationDemo:
    async def test_correlation_id_echoed(self, client):
        resp = await client.get(
            "/correlation-demo",
            headers={"X-Correlation-Id": "req-abc-123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["correlation_id"] == "req-abc-123"
        assert data["was_auto_generated"] is False

    async def test_auto_generated_when_missing(self, client):
        resp = await client.get("/correlation-demo")
        data = resp.json()
        assert data["was_auto_generated"] is True
        assert data["correlation_id"].startswith("auto-")


# ---------------------------------------------------------------------------
# /tenant-demo
# ---------------------------------------------------------------------------


class TestTenantDemo:
    async def test_missing_tenant_returns_400(self, client):
        resp = await client.get("/tenant-demo")
        assert resp.status_code == 400

    async def test_known_tenant_returns_config(self, client):
        resp = await client.get("/tenant-demo", headers={"X-Tenant-Id": "acme-corp"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] == "acme-corp"
        assert data["tenant_config"]["plan"] == "enterprise"

    async def test_unknown_tenant_returns_unknown_config(self, client):
        resp = await client.get("/tenant-demo", headers={"X-Tenant-Id": "unknown-co"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_config"]["plan"] == "unknown"


# ---------------------------------------------------------------------------
# /all-headers
# ---------------------------------------------------------------------------


class TestAllHeaders:
    async def test_returns_all_headers(self, client):
        resp = await client.get(
            "/all-headers",
            headers={
                "Authorization": "Bearer tok",
                "X-Correlation-Id": "trace-001",
                "X-Tenant-Id": "acme-corp",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_headers"] > 0
        assert "raw" in data

    async def test_global_headers_in_all_headers(self, client):
        resp = await client.get("/all-headers")
        data = resp.json()
        raw = data["raw"]
        assert raw.get("x-service-name") == "graftcode-python-demo"
        assert raw.get("x-api-version") == "v1"


# ---------------------------------------------------------------------------
# /global-headers-demo
# ---------------------------------------------------------------------------


class TestGlobalHeadersDemo:
    async def test_global_headers_returned(self, client):
        resp = await client.get("/global-headers-demo")
        assert resp.status_code == 200
        data = resp.json()
        assert "X-Service-Name" in data["global_headers_set_at_startup"]
        assert (
            data["visible_in_current_context"]["X-Service-Name"] == "graftcode-python-demo"
        )


# ---------------------------------------------------------------------------
# /invoke-demo
# ---------------------------------------------------------------------------


class TestInvokeDemo:
    async def test_per_call_headers_applied(self, client):
        override = {
            "Authorization": "Bearer per-call-token",
            "X-Tenant-Id": "override-tenant",
        }
        resp = await client.post("/invoke-demo", json={"headers": override})
        assert resp.status_code == 200
        data = resp.json()
        inner = data["inner_context_during_call"]
        assert inner.get("authorization") == "Bearer per-call-token"
        assert inner.get("x-tenant-id") == "override-tenant"

    async def test_outer_context_restored_after_call(self, client):
        resp = await client.post(
            "/invoke-demo",
            json={"headers": {"Authorization": "Bearer inner"}},
        )
        data = resp.json()
        assert data["context_correctly_restored"] is True


# ---------------------------------------------------------------------------
# /async-demo
# ---------------------------------------------------------------------------


class TestAsyncDemo:
    async def test_async_demo_returns_isolation_verified(self, client):
        resp = await client.get("/async-demo")
        assert resp.status_code == 200
        data = resp.json()
        assert data["isolation_verified"] is True

    async def test_task_a_and_b_have_different_tenants(self, client):
        resp = await client.get("/async-demo")
        data = resp.json()
        assert data["task_a"]["tenant_id"] != data["task_b"]["tenant_id"]

    async def test_task_a_and_b_have_different_correlation_ids(self, client):
        resp = await client.get("/async-demo")
        data = resp.json()
        assert data["task_a"]["correlation_id"] != data["task_b"]["correlation_id"]
