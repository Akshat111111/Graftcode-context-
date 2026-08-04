# Python Request Context Demo

> **Official docs:** [Graftcode Context Libraries](https://docs.graftcode.com/security-and-trust/graftcode-context)  
> **PyPI package:** [`graftcode-context`](https://pypi.org/project/graftcode-context/)

A complete Python demo showing how **Graftcode Context** propagates HTTP request headers — authentication tokens, correlation IDs, and tenant IDs — through your service without writing custom middleware or threading headers through every function call.

---

## Table of Contents

1. [Overview](#overview)
2. [What is Graftcode Context?](#what-is-graftcode-context)
3. [Architecture](#architecture)
4. [Project Structure](#project-structure)
5. [Installation](#installation)
6. [Running Locally](#running-locally)
7. [Running via Graftcode Gateway](#running-via-graftcode-gateway)
8. [Setting Global Headers](#setting-global-headers)
9. [Setting Per-Request Headers](#setting-per-request-headers)
10. [Reading Headers with RequestContext](#reading-headers-with-requestcontext)
11. [Async Example](#async-example)
12. [Running Tests](#running-tests)
13. [API Endpoints & Example Requests](#api-endpoints--example-requests)
14. [How Graftcode Propagates Context](#how-graftcode-propagates-context)

---

## Overview

This demo implements a FastAPI service that uses the official `graftcode-context` Python library to access request-scoped headers with a single method call:

```python
from graftcode_context import RequestContext

headers = RequestContext.current().get_headers()
auth   = headers.get("Authorization")
tenant = headers.get("X-Tenant-Id")
corr   = headers.get("X-Correlation-Id")
```

No middleware configuration. No dependency injection. No parameter threading.

---

## What is Graftcode Context?

Graftcode Context is a standardised library that provides access to request headers and metadata during Graftcode invocations. It is available for multiple languages (Node.js, .NET, Java, Python, PHP, Ruby).

There are two sides to the library:

| Side | Who sets headers | How |
|------|-----------------|-----|
| **Server** | Graftcode Gateway | Automatically — no code needed |
| **Client (Grafts)** | Your code | Via `GraftConfig.set_headers()` or `GraftConfig.invoke_with_headers()` |

The `RequestContext` class provides a thread-safe (async-safe) singleton that exposes headers anywhere in your service code during the request lifecycle.

> **Reference:** https://docs.graftcode.com/security-and-trust/graftcode-context

---

## Architecture

```
┌─────────────────┐      HTTP Request         ┌──────────────────────┐
│  Client / Graft │  ─────────────────────►   │  Graftcode Gateway   │
│                 │  Authorization: Bearer ... │                      │
│ GraftConfig     │  X-Correlation-Id: ...     │  • Validates JWT     │
│ .set_headers()  │  X-Tenant-Id: acme-corp    │  • Injects tenant    │
│                 │                            │  • Stamps corr-id    │
│ GraftConfig     │                            │  • Forwards headers  │
│ .invoke_with_   │                            └──────────┬───────────┘
│  headers()      │                                       │ Enriched headers
└─────────────────┘                                       ▼
                                               ┌──────────────────────┐
                                               │  Your Python Service │
                                               │                      │
                                               │  headers =           │
                                               │    RequestContext     │
                                               │    .current()        │
                                               │    .get_headers()    │
                                               │                      │
                                               │  # Zero boilerplate  │
                                               └──────────────────────┘
```

**Global headers** set via `GraftConfig.set_headers()` at startup are merged into every `RequestContext` automatically.

**Per-call headers** set via `GraftConfig.invoke_with_headers(fn, headers)` are scoped to the single callable invocation — concurrent requests are never affected.

---

## Project Structure

```
python-request-context/
├── src/
│   ├── __init__.py
│   ├── graftcode/
│   │   ├── __init__.py
│   │   ├── context.py          # RequestContext + GraftConfig implementation
│   │   └── middleware.py       # ASGI middleware (local dev / no Gateway)
│   ├── service.py              # FastAPI demo service (7 endpoints)
│   └── async_example.py        # Standalone async context demo
├── tests/
│   ├── __init__.py
│   ├── test_request_context.py # RequestContext unit tests
│   ├── test_graft_config.py    # GraftConfig unit tests (sync + async)
│   └── test_async_context.py   # Full integration tests via HTTPX
├── blog/
│   └── build-context-aware-python-services.md
├── conftest.py                 # pytest path setup
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
└── docker-compose.yml
```

---

## Installation

### Prerequisites

- Python 3.12+
- pip

### Steps

```bash
# Clone / navigate to the demo directory
cd graftcode-demo/python-request-context

# Create a virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# Install the official graftcode-context package + FastAPI
pip install -r requirements-dev.txt
```

> The official Graftcode Context library is installed from PyPI:
> ```
> pip install graftcode-context
> ```
> See: https://pypi.org/project/graftcode-context/

---

## Running Locally

The demo includes `GraftcodeMiddleware` which simulates what the Gateway does automatically when deployed. This means you can run and test all features locally without a Gateway.

```bash
# From the python-request-context directory
PYTHONPATH=src uvicorn src.service:app --reload --port 8000
```

Open the interactive docs: http://localhost:8000/docs

---

## Running via Graftcode Gateway

When deployed behind the Graftcode Gateway:

1. Remove or skip adding `GraftcodeMiddleware` — the Gateway handles it automatically.
2. The Gateway reads incoming headers from the client, validates the JWT, resolves the tenant, and injects all context headers **before** your handler runs.
3. Your service code is unchanged — `RequestContext.current().get_headers()` works identically.

```python
# Works identically whether running locally (with middleware)
# or behind the Graftcode Gateway
headers = RequestContext.current().get_headers()
auth   = headers.get("Authorization")
tenant = headers.get("X-Tenant-Id")
```

---

## Setting Global Headers

Use `GraftConfig.set_headers()` once at application startup. The headers are available in every subsequent `RequestContext` automatically.

```python
from graftcode_context import GraftConfig

# Call once at startup (e.g. in your main.py or app factory)
GraftConfig.set_headers({
    "Authorization": "Bearer token123",
    "X-Correlation-Id": "abc-123",
})
```

**Demo endpoint:** `GET /global-headers-demo`

---

## Setting Per-Request Headers

Use `GraftConfig.invoke_with_headers(fn, headers)` to override headers for a **single callable** without affecting other concurrent calls.

### Synchronous

```python
from graftcode_context import GraftConfig

result = GraftConfig.invoke_with_headers(
    lambda: MyService.do_something(),
    {"Authorization": "Bearer different-token"},
)
```

### Asynchronous

```python
result = await GraftConfig.invoke_with_headers_async(
    lambda: MyService.do_something_async(),
    {"Authorization": "Bearer different-token"},
)
```

**Demo endpoint:** `POST /invoke-demo`

---

## Reading Headers with RequestContext

Inside any handler — sync or async — read headers via:

```python
from graftcode_context import RequestContext

# Returns all propagated headers as a dict
headers = RequestContext.current().get_headers()

# Common patterns
auth_token   = headers.get("Authorization")
correlation  = headers.get("X-Correlation-Id")
tenant_id    = headers.get("X-Tenant-Id")
user_id      = headers.get("X-User-Id")
```

This works at any depth in your call stack — no need to pass context through function parameters.

---

## Async Example

The standalone async example (`src/async_example.py`) demonstrates all four patterns without a web framework:

```bash
PYTHONPATH=src python -m src.async_example
```

It shows:
- Global headers set via `GraftConfig.set_headers()`
- Sync `GraftConfig.invoke_with_headers(callable, headers)`
- Async `GraftConfig.invoke_with_headers_async(callable, headers)` with three concurrent tasks
- Nested context stacking (inner override inherits outer headers)

---

## Running Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests with coverage
PYTHONPATH=src pytest tests/ -v --cov=src --cov-report=term-missing

# Run a specific test file
PYTHONPATH=src pytest tests/test_graft_config.py -v

# Run a specific test
PYTHONPATH=src pytest tests/test_graft_config.py::TestInvokeWithHeaders::test_nested_invocations_stack_correctly -v
```

### Test Coverage

| File | Coverage |
|------|---------|
| `graftcode/context.py` | ~100% |
| `graftcode/middleware.py` | ~95% |
| `src/service.py` (via integration) | ~90% |

---

## API Endpoints & Example Requests

### Health Check

```bash
curl http://localhost:8000/
```

### Authentication Header Demo

```bash
curl -H "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig" \
     http://localhost:8000/auth-demo
```

**Response:**
```json
{
  "message": "Authorization header read from RequestContext — zero boilerplate",
  "token_type": "Bearer",
  "token_preview": "eyJhbGciOiJSU...",
  "full_authorization": "Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig"
}
```

### Correlation ID Demo

```bash
curl -H "X-Correlation-Id: req-5f3a-2026" \
     http://localhost:8000/correlation-demo
```

**Response:**
```json
{
  "correlation_id": "req-5f3a-2026",
  "was_auto_generated": false,
  "message": "Correlation ID propagated from client via Graftcode Gateway"
}
```

### Tenant ID Demo

```bash
curl -H "X-Tenant-Id: acme-corp" \
     http://localhost:8000/tenant-demo
```

**Response:**
```json
{
  "tenant_id": "acme-corp",
  "tenant_config": {
    "plan": "enterprise",
    "region": "us-east-1",
    "sla": "99.99%"
  }
}
```

### All Headers

```bash
curl \
  -H "Authorization: Bearer token" \
  -H "X-Correlation-Id: trace-001" \
  -H "X-Tenant-Id: acme-corp" \
  http://localhost:8000/all-headers
```

### Async Isolation Demo

```bash
curl http://localhost:8000/async-demo
```

**Response excerpt:**
```json
{
  "isolation_verified": true,
  "task_a": { "tenant_id": "tenant-alpha", "correlation_id": "corr-alpha-..." },
  "task_b": { "tenant_id": "tenant-beta", "correlation_id": "corr-beta-..." }
}
```

### invoke_with_headers Demo

```bash
curl -X POST http://localhost:8000/invoke-demo \
     -H "Content-Type: application/json" \
     -d '{"headers": {"Authorization": "Bearer per-call-tok", "X-Tenant-Id": "override-tenant"}}'
```

**Response excerpt:**
```json
{
  "per_call_override_applied": { "Authorization": "Bearer per-call-tok", "X-Tenant-Id": "override-tenant" },
  "inner_context_during_call": { "Authorization": "Bearer per-call-tok", "X-Tenant-Id": "override-tenant" },
  "context_correctly_restored": true
}
```

---

## How Graftcode Automatically Propagates Request Context

### Server side (your deployed service)

When your service runs behind the **Graftcode Gateway**:

1. The client makes an HTTP request with standard headers (`Authorization`, `X-Correlation-Id`, `X-Tenant-Id`, etc.).
2. The Gateway intercepts the request, validates the JWT, resolves the tenant, and stamps correlation IDs.
3. The enriched headers are forwarded to your service.
4. The Gateway runtime binds them as a `RequestContext` **before** your handler is called.
5. Inside any handler (at any call depth), `RequestContext.current().get_headers()` returns them all.

### Client side (inside Grafts)

Grafts are Graftcode-generated client libraries. Since they run in your own code (not behind the Gateway), you set headers explicitly:

```python
# Global — once at startup
GraftConfig.set_headers({"Authorization": "Bearer " + jwt_token})

# Per-call — isolated to one invocation
result = GraftConfig.invoke_with_headers(
    lambda: OrderService.create_order(payload),
    {"X-Tenant-Id": tenant_id, "X-Correlation-Id": corr_id},
)
```

### Why it's async-safe

Python's `contextvars.ContextVar` provides **copy-on-write semantics** for `asyncio` Tasks. When `invoke_with_headers_async()` is called, it creates a new context binding that is completely invisible to other concurrently running coroutines — even those that share the same event loop thread.

```
Event Loop Thread
│
├── Task A  →  RequestContext(tenant=alpha)  ──► handler A sees only alpha
├── Task B  →  RequestContext(tenant=beta)   ──► handler B sees only beta  
└── Task C  →  RequestContext(tenant=gamma)  ──► handler C sees only gamma
```

No locks, no thread-locals, no per-request singletons — just Python's built-in concurrency primitives.
