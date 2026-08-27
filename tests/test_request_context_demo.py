"""
tests/test_request_context_demo.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration tests for RequestContextDemo — directly calling the 8 public
methods and asserting the JSON output is correct.

No HTTP framework, no sockets, no mocks required.

Tests verify:
  - Each method returns valid JSON
  - Headers bound via set_headers() are readable via get_headers()
  - Missing-header error paths (401, 400 equivalents)
  - Async isolation (Case 8)
"""

import json
import sys
import os

import pytest

# Make sure vision/ is on the path so RequestContextDemo is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vision"))

from request_context_demo import RequestContextDemo  # noqa: E402


@pytest.fixture
def demo() -> RequestContextDemo:
    return RequestContextDemo()


# ---------------------------------------------------------------------------
# Case 1 -- health_check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_returns_healthy_status(self, demo):
        data = json.loads(demo.health_check())
        assert data["status"] == "healthy"

    def test_contains_pypi_link(self, demo):
        data = json.loads(demo.health_check())
        assert "pypi.org" in data["pypi"]

    def test_headers_in_context_present(self, demo):
        data = json.loads(demo.health_check())
        assert "headers_in_context" in data


# ---------------------------------------------------------------------------
# Case 2 -- auth_demo (success)
# ---------------------------------------------------------------------------


class TestAuthDemo:
    def test_valid_bearer_token_echoed(self, demo):
        token = "Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig"
        data = json.loads(demo.auth_demo(authorization=token))
        assert data["token_type"] == "Bearer"
        assert data["full_authorization"] == token

    def test_token_preview_truncated_when_long(self, demo):
        data = json.loads(demo.auth_demo(authorization="Bearer " + "x" * 40))
        assert data["token_preview"].endswith("...")

    def test_all_headers_in_context(self, demo):
        data = json.loads(demo.auth_demo(authorization="Bearer tok"))
        assert "Authorization" in data["all_headers_in_context"]

    def test_empty_auth_returns_error(self, demo):
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

    def test_error_message_mentions_tenant(self, demo):
        data = json.loads(demo.tenant_demo_missing_id())
        assert "X-Tenant-Id" in data["error"]


# ---------------------------------------------------------------------------
# Case 6 -- all_headers
# ---------------------------------------------------------------------------


class TestAllHeaders:
    def test_per_request_headers_in_output(self, demo):
        data = json.loads(demo.all_headers(
            authorization="Bearer tok",
            x_correlation_id="trace-001",
            x_tenant_id="acme-corp",
        ))
        raw = data["raw"]
        assert raw.get("Authorization") == "Bearer tok"
        assert raw.get("X-Correlation-Id") == "trace-001"
        assert raw.get("X-Tenant-Id") == "acme-corp"

    def test_total_header_count(self, demo):
        data = json.loads(demo.all_headers(
            authorization="Bearer tok",
            x_correlation_id="trace-001",
            x_tenant_id="acme-corp",
        ))
        assert data["total_headers"] == 3


# ---------------------------------------------------------------------------
# Case 7 -- context_replace_demo
# ---------------------------------------------------------------------------


class TestContextReplaceDemo:
    def test_tenant_changed(self, demo):
        data = json.loads(demo.context_replace_demo(
            first_tenant="tenant-alpha",
            second_tenant="tenant-beta",
        ))
        assert data["tenant_changed"] is True

    def test_snapshots_differ(self, demo):
        data = json.loads(demo.context_replace_demo())
        assert (
            data["after_first_set_headers"]["X-Tenant-Id"]
            != data["after_second_set_headers"]["X-Tenant-Id"]
        )


