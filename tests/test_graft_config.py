"""
tests/test_graft_config.py
~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for GraftConfig.

Tests cover:
  - set_headers() (global headers)
  - get_global_headers() / clear_global_headers()
  - invoke_with_headers() — sync per-call override
  - invoke_with_headers_async() — async per-call override
  - Header precedence (per-call wins over global)
  - Context restoration after call
  - Nested invoke_with_headers() stacking
  - Exception safety (context restored even on error)
"""

import asyncio

import pytest

from graftcode.context import GraftConfig, RequestContext, _request_context_var


@pytest.fixture(autouse=True)
def clean_state():
    """Reset global headers and context before every test."""
    GraftConfig.clear_global_headers()
    token = _request_context_var.set(None)
    yield
    _request_context_var.reset(token)
    GraftConfig.clear_global_headers()


# ---------------------------------------------------------------------------
# Global headers
# ---------------------------------------------------------------------------


class TestSetHeaders:
    def test_set_headers_updates_global_state(self):
        GraftConfig.set_headers({"Authorization": "Bearer global-tok"})
        assert GraftConfig.get_global_headers()["Authorization"] == "Bearer global-tok"

    def test_multiple_set_headers_merge(self):
        GraftConfig.set_headers({"Authorization": "Bearer tok"})
        GraftConfig.set_headers({"X-Tenant-Id": "acme"})
        hdrs = GraftConfig.get_global_headers()
        assert hdrs["Authorization"] == "Bearer tok"
        assert hdrs["X-Tenant-Id"] == "acme"

    def test_clear_global_headers(self):
        GraftConfig.set_headers({"Authorization": "Bearer tok"})
        GraftConfig.clear_global_headers()
        assert GraftConfig.get_global_headers() == {}

    def test_get_global_headers_returns_copy(self):
        GraftConfig.set_headers({"X-Key": "val"})
        copy = GraftConfig.get_global_headers()
        copy["X-Injected"] = "should-not-persist"
        assert "X-Injected" not in GraftConfig.get_global_headers()


# ---------------------------------------------------------------------------
# invoke_with_headers — sync
# ---------------------------------------------------------------------------


class TestInvokeWithHeaders:
    def test_callable_receives_correct_headers(self):
        captured = {}

        def fn():
            captured.update(RequestContext.current().get_headers())
            return "ok"

        result = GraftConfig.invoke_with_headers(
            fn,
            {"Authorization": "Bearer per-call", "X-Correlation-Id": "corr-123"},
        )
        assert result == "ok"
        assert captured["authorization"] == "Bearer per-call"
        assert captured["x-correlation-id"] == "corr-123"

    def test_per_call_headers_override_global(self):
        GraftConfig.set_headers({"Authorization": "Bearer global"})

        captured = {}

        def fn():
            captured.update(RequestContext.current().get_headers())

        GraftConfig.invoke_with_headers(fn, {"Authorization": "Bearer per-call"})
        assert captured["authorization"] == "Bearer per-call"

    def test_global_headers_visible_in_call(self):
        GraftConfig.set_headers({"X-Service-Name": "my-svc"})
        captured = {}

        def fn():
            captured.update(RequestContext.current().get_headers())

        GraftConfig.invoke_with_headers(fn, {"X-Tenant-Id": "acme"})
        assert captured["x-service-name"] == "my-svc"
        assert captured["x-tenant-id"] == "acme"

    def test_context_restored_after_call(self):
        outer_ctx = RequestContext({"X-Stage": "outer"})
        token = RequestContext._bind(outer_ctx)

        GraftConfig.invoke_with_headers(lambda: None, {"X-Stage": "inner"})

        current = RequestContext.current()
        assert current.get_headers().get("x-stage") == "outer"
        RequestContext._unbind(token)

    def test_context_restored_on_exception(self):
        outer_headers = {"X-Stage": "outer"}
        outer_ctx = RequestContext(outer_headers)
        token = RequestContext._bind(outer_ctx)

        with pytest.raises(ValueError, match="boom"):
            GraftConfig.invoke_with_headers(
                lambda: (_ for _ in ()).throw(ValueError("boom")),
                {"X-Stage": "inner"},
            )

        assert RequestContext.current().get_headers().get("x-stage") == "outer"
        RequestContext._unbind(token)

    def test_return_value_propagated(self):
        result = GraftConfig.invoke_with_headers(lambda: 42, {"X-Key": "v"})
        assert result == 42

    def test_nested_invocations_stack_correctly(self):
        captured_inner = {}
        captured_outer = {}

        def inner():
            captured_inner.update(RequestContext.current().get_headers())

        def outer():
            captured_outer.update(RequestContext.current().get_headers())
            GraftConfig.invoke_with_headers(inner, {"Authorization": "Bearer inner"})

        GraftConfig.invoke_with_headers(
            outer,
            {
                "Authorization": "Bearer outer",
                "X-Correlation-Id": "corr-001",
            },
        )

        # Outer call sees outer headers
        assert captured_outer["authorization"] == "Bearer outer"
        assert captured_outer["x-correlation-id"] == "corr-001"

        # Inner call overrides Authorization but inherits Correlation-Id
        assert captured_inner["authorization"] == "Bearer inner"
        assert captured_inner["x-correlation-id"] == "corr-001"


# ---------------------------------------------------------------------------
# invoke_with_headers_async — async
# ---------------------------------------------------------------------------


class TestInvokeWithHeadersAsync:
    def test_async_callable_receives_correct_headers(self):
        captured = {}

        async def fn():
            captured.update(RequestContext.current().get_headers())
            return "async-ok"

        result = asyncio.run(
            GraftConfig.invoke_with_headers_async(
                fn,
                {"Authorization": "Bearer async-tok", "X-Tenant-Id": "tenant-x"},
            )
        )
        assert result == "async-ok"
        assert captured["authorization"] == "Bearer async-tok"
        assert captured["x-tenant-id"] == "tenant-x"

    def test_async_per_call_headers_override_global(self):
        GraftConfig.set_headers({"Authorization": "Bearer global"})
        captured = {}

        async def fn():
            captured.update(RequestContext.current().get_headers())

        asyncio.run(
            GraftConfig.invoke_with_headers_async(fn, {"Authorization": "Bearer async-per-call"})
        )
        assert captured["authorization"] == "Bearer async-per-call"

    def test_async_context_restored_after_call(self):
        outer_ctx = RequestContext({"X-Stage": "async-outer"})

        async def run():
            token = RequestContext._bind(outer_ctx)
            await GraftConfig.invoke_with_headers_async(
                lambda: asyncio.sleep(0), {"X-Stage": "async-inner"}
            )
            result = RequestContext.current().get_headers().get("x-stage")
            RequestContext._unbind(token)
            return result

        stage = asyncio.run(run())
        assert stage == "async-outer"

    def test_concurrent_tasks_are_isolated(self):
        """Two concurrent async tasks must never see each other's headers."""

        async def task(tenant: str) -> str:
            async def _work():
                await asyncio.sleep(0.01)
                return (
                    RequestContext.current().get_headers().get("X-Tenant-Id")
                    or RequestContext.current().get_headers().get("x-tenant-id")
                )

            return await GraftConfig.invoke_with_headers_async(
                _work, {"X-Tenant-Id": tenant}
            )

        async def run():
            results = await asyncio.gather(task("alpha"), task("beta"), task("gamma"))
            return results

        tenants = asyncio.run(run())
        assert set(tenants) == {"alpha", "beta", "gamma"}

    def test_async_global_headers_visible_in_call(self):
        GraftConfig.set_headers({"X-Service-Name": "async-svc"})
        captured = {}

        async def fn():
            captured.update(RequestContext.current().get_headers())

        asyncio.run(
            GraftConfig.invoke_with_headers_async(fn, {"X-Tenant-Id": "acme"})
        )
        assert captured["x-service-name"] == "async-svc"
        assert captured["x-tenant-id"] == "acme"
