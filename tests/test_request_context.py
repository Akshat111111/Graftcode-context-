"""
tests/test_request_context.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for RequestContext.

Tests cover:
  - Default empty context
  - Header storage and retrieval
  - Case-insensitive header lookup
  - Context binding and unbinding
  - Context isolation between threads
"""

import threading

import pytest

from graftcode.context import GraftConfig, RequestContext, _request_context_var


@pytest.fixture(autouse=True)
def clean_context():
    """Ensure each test starts with a clean slate."""
    GraftConfig.clear_global_headers()
    token = _request_context_var.set(None)
    yield
    _request_context_var.reset(token)
    GraftConfig.clear_global_headers()


# ---------------------------------------------------------------------------
# Basic construction
# ---------------------------------------------------------------------------


class TestRequestContextConstruction:
    def test_empty_context_returns_empty_headers(self):
        ctx = RequestContext()
        assert ctx.get_headers() == {}

    def test_headers_stored_correctly(self):
        headers = {"Authorization": "Bearer tok", "X-Tenant-Id": "acme"}
        ctx = RequestContext(headers)
        # Keys are preserved with original casing
        assert ctx.get_headers() == {"Authorization": "Bearer tok", "X-Tenant-Id": "acme"}

    def test_get_headers_returns_copy(self):
        ctx = RequestContext({"Authorization": "Bearer tok"})
        copy = ctx.get_headers()
        copy["Injected"] = "should-not-affect-ctx"
        assert "Injected" not in ctx.get_headers()

    def test_none_headers_treated_as_empty(self):
        ctx = RequestContext(None)
        assert ctx.get_headers() == {}


# ---------------------------------------------------------------------------
# get_header
# ---------------------------------------------------------------------------


class TestGetHeader:
    def test_exact_key_match(self):
        ctx = RequestContext({"Authorization": "Bearer tok"})
        assert ctx.get_header("Authorization") == "Bearer tok"

    def test_lowercase_key_match(self):
        ctx = RequestContext({"Authorization": "Bearer tok"})
        assert ctx.get_header("authorization") == "Bearer tok"

    def test_missing_key_returns_default(self):
        ctx = RequestContext({})
        assert ctx.get_header("X-Missing") is None
        assert ctx.get_header("X-Missing", "fallback") == "fallback"


# ---------------------------------------------------------------------------
# RequestContext.current()
# ---------------------------------------------------------------------------


class TestCurrentContext:
    def test_current_returns_empty_when_no_context_set(self):
        ctx = RequestContext.current()
        assert ctx.get_headers() == {}

    def test_current_returns_bound_context(self):
        expected = RequestContext({"Authorization": "Bearer xyz"})
        token = RequestContext._bind(expected)
        try:
            assert RequestContext.current() is expected
        finally:
            RequestContext._unbind(token)

    def test_current_reflects_global_headers_outside_request(self):
        GraftConfig.set_headers({"X-Service-Name": "test-svc"})
        ctx = RequestContext.current()
        # Keys retain the casing they were set with
        assert ctx.get_headers().get("X-Service-Name") == "test-svc"

    def test_bind_and_unbind_restores_previous(self):
        outer = RequestContext({"X-Stage": "outer"})
        token_outer = RequestContext._bind(outer)

        inner = RequestContext({"X-Stage": "inner"})
        token_inner = RequestContext._bind(inner)
        assert RequestContext.current() is inner

        RequestContext._unbind(token_inner)
        assert RequestContext.current() is outer

        RequestContext._unbind(token_outer)


# ---------------------------------------------------------------------------
# Thread isolation
# ---------------------------------------------------------------------------


class TestThreadIsolation:
    def test_contexts_isolated_across_threads(self):
        results: dict = {}
        barrier = threading.Barrier(2)

        def thread_fn(name: str, tenant: str):
            ctx = RequestContext({"X-Tenant-Id": tenant})
            token = RequestContext._bind(ctx)
            barrier.wait()  # both threads in context simultaneously
            # Key is preserved with original casing
            results[name] = RequestContext.current().get_headers().get("X-Tenant-Id")
            RequestContext._unbind(token)

        t1 = threading.Thread(target=thread_fn, args=("t1", "tenant-alpha"))
        t2 = threading.Thread(target=thread_fn, args=("t2", "tenant-beta"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results["t1"] == "tenant-alpha"
        assert results["t2"] == "tenant-beta"


# ---------------------------------------------------------------------------
# __eq__
# ---------------------------------------------------------------------------


class TestEquality:
    def test_equal_contexts(self):
        a = RequestContext({"Authorization": "tok"})
        b = RequestContext({"Authorization": "tok"})
        assert a == b

    def test_unequal_contexts(self):
        a = RequestContext({"Authorization": "tok-a"})
        b = RequestContext({"Authorization": "tok-b"})
        assert a != b

    def test_not_equal_to_non_context(self):
        ctx = RequestContext({"Authorization": "tok"})
        assert ctx != "not-a-context"
