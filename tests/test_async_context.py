"""
tests/test_async_context.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration-level tests for the Graftcode Context pipeline using the
Vision class (RequestContextDemo).

Tests directly call the 8 public methods on RequestContextDemo and assert
that GraftConfig / RequestContext behaviour is correct.  No HTTP framework,
no sockets, no service.py required.

Tests cover:
  - Context injection populates RequestContext from supplied headers
  - Handler reads headers via RequestContext.current().get_headers()
  - GraftConfig.invoke_with_headers_async() isolation under concurrency
  - Global headers visible in all handlers
  - Context is cleaned up after each handler call
"""

import sys
import os
import json

# Add vision/ to path so RequestContextDemo can import graftcode from there
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vision"))

import pytest

from graftcode.context import GraftConfig, RequestContext, _request_context_var
from request_context_demo import RequestContextDemo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_global_headers():
    """Reset and restore global headers around every test."""
    GraftConfig.clear_global_headers()
    GraftConfig.set_headers(
        {
            "X-Service-Name": "graftcode-python-demo",
            "X-Api-Version": "v1",
            "X-Environment": "local-dev",
        }
    )
    token = _request_context_var.set(None)
    yield
    _request_context_var.reset(token)
    GraftConfig.clear_global_headers()


@pytest.fixture
def demo():
    return RequestContextDemo()


# ---------------------------------------------------------------------------
# Case 1 -- health_check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_returns_healthy(self, demo):
        data = json.loads(demo.health_check())
        assert data["status"] == "healthy"

    def test_global_headers_present(self, demo):
        data = json.loads(demo.health_check())
        hdrs = data["global_headers_always_present"]
        assert hdrs.get("X-Service-Name") == "graftcode-python-demo"
        assert hdrs.get("X-Api-Version") == "v1"
        assert hdrs.get("X-Environment") == "local-dev"

    def test_contains_docs_url(self, demo):
        data = json.loads(demo.health_check())
        assert "docs.graftcode.com" in data["docs"]


# ---------------------------------------------------------------------------
# Case 2 -- auth_demo (success)
# ---------------------------------------------------------------------------


class TestAuthDemo:
    def test_valid_bearer_token_echoed(self, demo):
        token = "Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig"
        data = json.loads(demo.auth_demo(authorization=token))
        assert data["token_type"] == "Bearer"
        assert data["full_authorization"] == token

    def test_token_preview_truncated(self, demo):
        data = json.loads(demo.auth_demo(authorization="Bearer " + "x" * 40))
        assert data["token_preview"].endswith("...")

    def test_global_headers_in_context(self, demo):
        data = json.loads(demo.auth_demo())
        assert data["all_headers_in_context"]["X-Service-Name"] == "graftcode-python-demo"

    def test_missing_auth_returns_error_key(self, demo):
        # Pass empty string to force the no-auth code path
        data = json.loads(demo.auth_demo(authorization=""))
        assert "error" in data


# ---------------------------------------------------------------------------
# Case 3 -- auth_demo_missing_token
# ---------------------------------------------------------------------------


class TestAuthDemoMissingToken:
    def test_401_status_equivalent(self, demo):
        data = json.loads(demo.auth_demo_missing_token())
        assert data["http_status_equivalent"] == 401

    def test_authorization_value_is_none(self, demo):
        data = json.loads(demo.auth_demo_missing_token())
        assert data["authorization_value"] is None

    def test_global_headers_still_available(self, demo):
        data = json.loads(demo.auth_demo_missing_token())
        assert "X-Service-Name" in data["available_headers"]


# ---------------------------------------------------------------------------
# Case 4 -- correlation_demo
# ---------------------------------------------------------------------------


class TestCorrelationDemo:
    def test_provided_id_echoed(self, demo):
        data = json.loads(demo.correlation_demo(x_correlation_id="req-abc-123"))
        assert data["correlation_id"] == "req-abc-123"
        assert data["was_auto_generated"] is False

    def test_auto_generated_when_blank(self, demo):
        data = json.loads(demo.correlation_demo(x_correlation_id=""))
        assert data["was_auto_generated"] is True
        assert data["correlation_id"].startswith("auto-")

    def test_global_headers_in_context(self, demo):
        data = json.loads(demo.correlation_demo(x_correlation_id="trace-x"))
        assert data["all_headers_in_context"]["X-Api-Version"] == "v1"


# ---------------------------------------------------------------------------
# Case 5 -- tenant_demo_missing_id
# ---------------------------------------------------------------------------


class TestTenantDemoMissingId:
    def test_400_status_equivalent(self, demo):
        data = json.loads(demo.tenant_demo_missing_id())
        assert data["http_status_equivalent"] == 400

    def test_tenant_id_value_is_none(self, demo):
        data = json.loads(demo.tenant_demo_missing_id())
        assert data["tenant_id_value"] is None

    def test_error_message_present(self, demo):
        data = json.loads(demo.tenant_demo_missing_id())
        assert "X-Tenant-Id" in data["error"]


# ---------------------------------------------------------------------------
# Case 6 -- all_headers
# ---------------------------------------------------------------------------


class TestAllHeaders:
    def test_returns_all_per_request_headers(self, demo):
        data = json.loads(demo.all_headers(
            authorization="Bearer tok",
            x_correlation_id="trace-001",
            x_tenant_id="acme-corp",
        ))
        raw = data["raw"]
        assert raw.get("Authorization") == "Bearer tok"
        assert raw.get("X-Correlation-Id") == "trace-001"
        assert raw.get("X-Tenant-Id") == "acme-corp"

    def test_global_headers_merged(self, demo):
        data = json.loads(demo.all_headers())
        raw = data["raw"]
        assert raw.get("X-Service-Name") == "graftcode-python-demo"
        assert raw.get("X-Api-Version") == "v1"

    def test_total_header_count(self, demo):
        data = json.loads(demo.all_headers(
            authorization="Bearer tok",
            x_correlation_id="trace-001",
            x_tenant_id="acme-corp",
        ))
        # 3 per-request + 3 global = 6
        assert data["total_headers"] >= 6


# ---------------------------------------------------------------------------
# Case 7 -- global_headers_demo
# ---------------------------------------------------------------------------


class TestGlobalHeadersDemo:
    def test_global_headers_returned(self, demo):
        data = json.loads(demo.global_headers_demo())
        assert "X-Service-Name" in data["global_headers_set_at_startup"]
        assert (
            data["visible_in_current_context"]["X-Service-Name"]
            == "graftcode-python-demo"
        )

    def test_code_snippet_present(self, demo):
        data = json.loads(demo.global_headers_demo())
        assert "GraftConfig.set_headers" in data["code_snippet"]


# ---------------------------------------------------------------------------
# Case 8 -- async_isolation_demo
# ---------------------------------------------------------------------------


class TestAsyncIsolationDemo:
    def test_isolation_verified(self, demo):
        data = json.loads(demo.async_isolation_demo())
        assert data["isolation_verified"] is True

    def test_task_a_and_b_have_different_tenants(self, demo):
        data = json.loads(demo.async_isolation_demo())
        assert data["task_a"]["tenant_id"] != data["task_b"]["tenant_id"]

    def test_task_a_and_b_have_different_correlation_ids(self, demo):
        data = json.loads(demo.async_isolation_demo())
        assert data["task_a"]["correlation_id"] != data["task_b"]["correlation_id"]

    def test_task_a_and_b_have_different_tokens(self, demo):
        data = json.loads(demo.async_isolation_demo())
        assert data["task_a"]["authorization"] != data["task_b"]["authorization"]

    def test_outer_context_unchanged(self, demo):
        data = json.loads(demo.async_isolation_demo())
        assert data["outer_context_unchanged"] is True
        assert data["outer_context_tenant_id"] is None


# ---------------------------------------------------------------------------
# RequestContext lifecycle -- direct unit tests
# ---------------------------------------------------------------------------


class TestContextInjection:
    def test_invoke_with_headers_binds_headers(self):
        result = {}

        def _fn():
            ctx = RequestContext.current()
            result["auth"] = ctx.get_header("Authorization")
            result["tenant"] = ctx.get_header("X-Tenant-Id")

        GraftConfig.invoke_with_headers(
            _fn, {"Authorization": "Bearer test", "X-Tenant-Id": "demo"}
        )
        assert result["auth"] == "Bearer test"
        assert result["tenant"] == "demo"

    def test_invoke_with_headers_restores_after_exit(self):
        def _fn():
            pass

        GraftConfig.invoke_with_headers(_fn, {"Authorization": "Bearer test"})
        ctx = RequestContext.current()
        assert ctx.get_header("Authorization") is None

    def test_invoke_with_headers_merges_global_headers(self):
        result = {}

        def _fn():
            ctx = RequestContext.current()
            result["svc"] = ctx.get_header("X-Service-Name")
            result["tenant"] = ctx.get_header("X-Tenant-Id")

        GraftConfig.invoke_with_headers(_fn, {"X-Tenant-Id": "acme"})
        assert result["svc"] == "graftcode-python-demo"
        assert result["tenant"] == "acme"

    def test_case_insensitive_header_lookup(self):
        result = {}

        def _fn():
            ctx = RequestContext.current()
            result["auth"] = ctx.get_header("authorization")  # lowercase
            result["tenant"] = ctx.get_header("x-tenant-id")  # lowercase

        GraftConfig.invoke_with_headers(
            _fn, {"Authorization": "Bearer tok", "X-Tenant-Id": "acme"}
        )
        assert result["auth"] == "Bearer tok"
        assert result["tenant"] == "acme"
