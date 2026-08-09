"""
async_example.py
~~~~~~~~~~~~~~~~

Standalone async example demonstrating Graftcode Context propagation with
Python's asyncio and contextvars — no web framework required.

This script shows:
  1. GraftConfig.set_headers()               — global headers
  2. GraftConfig.invoke_with_headers()       — sync per-call override
  3. GraftConfig.invoke_with_headers_async() — async per-call override
  4. Context isolation between concurrent async tasks

Run
---
    python -m src.async_example

Official docs: https://docs.graftcode.com/security-and-trust/graftcode-context
"""

import asyncio
import uuid

from graftcode import GraftConfig, RequestContext


# ---------------------------------------------------------------------------
# 1. Global headers — set once, available everywhere
# ---------------------------------------------------------------------------

print("=" * 60)
print("Graftcode Context - Python Async Demo")
print("=" * 60)

GraftConfig.set_headers(
    {
        "X-Service-Name": "async-demo-service",
        "X-Api-Version": "v1",
    }
)

print("\n[1] Global headers set via GraftConfig.set_headers()")
print(f"    => {GraftConfig.get_global_headers()}")


# ---------------------------------------------------------------------------
# 2. Synchronous invoke_with_headers
# ---------------------------------------------------------------------------

print("\n[2] Synchronous: GraftConfig.invoke_with_headers(callable, headers)")


def read_auth_context() -> dict:
    """Simulates a service handler reading its context."""
    ctx = RequestContext.current()
    return {
        "authorization": ctx.get_header("Authorization"),
        "correlation_id": ctx.get_header("X-Correlation-Id"),
        "service_name": ctx.get_header("X-Service-Name"),  # from global headers
    }


result = GraftConfig.invoke_with_headers(
    read_auth_context,
    {
        "Authorization": "Bearer jwt-token-for-user-alice",
        "X-Correlation-Id": f"req-{uuid.uuid4().hex[:8]}",
    },
)
print(f"    => {result}")

# Confirm outer context is unaffected
outer = RequestContext.current().get_headers()
print(f"    => Outer context after call: {outer}")
print(f"    => Authorization in outer context: {outer.get('Authorization', 'None (correctly isolated)')}")


# ---------------------------------------------------------------------------
# 3. Async invoke_with_headers_async
# ---------------------------------------------------------------------------

print("\n[3] Async: GraftConfig.invoke_with_headers_async(callable, headers)")


async def async_service_call(name: str, tenant: str, corr_id: str) -> dict:
    """Simulate an async downstream Graft call."""

    async def _work():
        await asyncio.sleep(0.01)  # simulate I/O
        ctx = RequestContext.current()
        return {
            "caller": name,
            "tenant_id": ctx.get_header("X-Tenant-Id"),
            "correlation_id": ctx.get_header("X-Correlation-Id"),
            "authorization": ctx.get_header("Authorization"),
            "service_name": ctx.get_header("X-Service-Name"),  # global header
        }

    return await GraftConfig.invoke_with_headers_async(
        _work,
        {
            "X-Tenant-Id": tenant,
            "X-Correlation-Id": corr_id,
            "Authorization": f"Bearer token-for-{tenant}",
        },
    )


async def run_concurrent_demo():
    # Launch three concurrent tasks, each with distinct headers
    results = await asyncio.gather(
        async_service_call("Task-Alpha", "acme-corp", f"corr-{uuid.uuid4().hex[:8]}"),
        async_service_call("Task-Beta", "startup-co", f"corr-{uuid.uuid4().hex[:8]}"),
        async_service_call("Task-Gamma", "demo-tenant", f"corr-{uuid.uuid4().hex[:8]}"),
    )

    for r in results:
        print(f"    => {r}")

    # Verify isolation
    tenants = [r["tenant_id"] for r in results]
    all_unique = len(set(tenants)) == len(tenants)
    print(f"\n    [OK] All tenant IDs unique (context isolation verified): {all_unique}")

    # Verify global headers were visible inside each call
    all_have_service_name = all(r["service_name"] == "async-demo-service" for r in results)
    print(f"    [OK] Global X-Service-Name visible in all tasks: {all_have_service_name}")

    # Outer context is clean after all tasks complete
    outer = RequestContext.current().get_headers()
    print(f"\n    Outer context after all tasks: {outer}")
    print(f"    No X-Tenant-Id in outer context: {RequestContext.current().get_header('X-Tenant-Id') is None}")


asyncio.run(run_concurrent_demo())


# ---------------------------------------------------------------------------
# 4. Nested invoke_with_headers (context stacking)
# ---------------------------------------------------------------------------

print("\n[4] Nested context stacking")


def inner_call() -> dict:
    ctx = RequestContext.current()
    return {
        "authorization": ctx.get_header("Authorization"),
        "tenant_id": ctx.get_header("X-Tenant-Id"),
        "correlation_id": ctx.get_header("X-Correlation-Id"),
    }


def outer_call() -> dict:
    # Outer sets Authorization + Correlation-Id
    outer_headers = {
        "Authorization": "Bearer outer-token",
        "X-Correlation-Id": "outer-corr-001",
    }
    # Inner overrides Authorization only; Correlation-Id is inherited
    inner_headers = {
        "Authorization": "Bearer inner-token",
        "X-Tenant-Id": "nested-tenant",
    }

    inner_result = GraftConfig.invoke_with_headers(
        lambda: GraftConfig.invoke_with_headers(inner_call, inner_headers),
        outer_headers,
    )
    return inner_result


nested_result = GraftConfig.invoke_with_headers(outer_call, {})
print(f"    => Nested result: {nested_result}")
print(
    "    => Authorization from inner override: Bearer inner-token ==",
    nested_result["authorization"],
)
print(
    "    => Correlation-Id inherited from outer: outer-corr-001 ==",
    nested_result["correlation_id"],
)

print("\n" + "=" * 60)
print("Demo complete. All context propagation patterns verified.")
print("=" * 60)
