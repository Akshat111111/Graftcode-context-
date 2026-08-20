# Python Request Context Demo

> **Official docs:** [Graftcode Context Libraries](https://docs.graftcode.com/security-and-trust/graftcode-context)
> **PyPI package:** [`graftcode-context`](https://pypi.org/project/graftcode-context/)

A complete Python demo showing how **Graftcode Context** propagates HTTP request
headers — authentication tokens, correlation IDs, and tenant IDs — through your
service without writing custom middleware or threading headers through every
function call.

The 8 demo cases are exposed via **Graftcode Vision**: the built-in browser UI
that ships with every `gg` (Graftcode Gateway) deployment. No HTTP framework,
no REST routes, no controllers — just a plain Python class.

---

## Table of Contents

1. [What is Graftcode Context?](#what-is-graftcode-context)
2. [What is Graftcode Vision?](#what-is-graftcode-vision)
3. [Architecture](#architecture)
4. [Project Structure](#project-structure)
5. [Running via Graftcode Vision](#running-via-graftcode-vision)
6. [The 8 Demo Cases](#the-8-demo-cases)
7. [Running Locally (without Docker)](#running-locally-without-docker)
8. [Running Tests](#running-tests)
9. [How Graftcode Propagates Context](#how-graftcode-propagates-context)

---

## What is Graftcode Context?

Graftcode Context is a standardised library that provides access to request
headers and metadata during Graftcode invocations. It is available for multiple
languages (Node.js, .NET, Java, Python, PHP, Ruby).

| Side | Who sets headers | How |
|------|-----------------|-----|
| **Server** | Graftcode Gateway | Automatically — no code needed |
| **Client (Grafts)** | Your code | Via `GraftConfig.set_headers()` or `GraftConfig.invoke_with_headers()` |

```python
from graftcode import RequestContext

headers = RequestContext.current().get_headers()
auth   = headers.get("Authorization")
tenant = headers.get("X-Tenant-Id")
corr   = headers.get("X-Correlation-Id")
```

No middleware configuration. No dependency injection. No parameter threading.

> **Reference:** https://docs.graftcode.com/security-and-trust/graftcode-context

---

## What is Graftcode Vision?

Graftcode Vision is the built-in browser-based UI that ships with every `gg`
(Graftcode Gateway) deployment. It **auto-discovers** all public methods of your
Python class by reading type annotations at startup — no manual registration,
no Swagger/OpenAPI config needed.

For every public method it renders:
- The method name, parameter names, and types
- An interactive **"Try it out"** form
- Live output when you click **Run**

> **Quick Start:** https://docs.graftcode.com/quick-start/expose-backend/python

---

## Architecture

```
┌───────────────────────┐
│   Graftcode Vision    │  ← http://localhost:81/GV
│   (browser UI)        │    Auto-discovered from Python type hints
└──────────┬────────────┘
           │ calls
┌──────────▼────────────┐
│   gg (Gateway binary) │  Port 80 = Graft API
│                       │  Port 81 = Vision UI
└──────────┬────────────┘
           │ introspects & invokes
┌──────────▼────────────┐
│  RequestContextDemo   │  ← vision/request_context_demo.py
│  (plain Python class) │    8 public methods, zero HTTP imports
│                       │
│  uses:                │
│  GraftConfig          │  ← src/graftcode/context.py  (local lib)
│  RequestContext       │
└───────────────────────┘
```

**How the demo works:** Graftcode Vision calls methods directly (not via HTTP),
so each method uses `GraftConfig.invoke_with_headers()` to explicitly bind a
`RequestContext` — which is exactly what the Graftcode Gateway does
automatically in production. The binding code is visible so you can see the
mechanism; behind the Gateway it happens transparently.

> **The output is 100% live — not hardcoded.** When you type a value into the
> Vision form and click **Run**, that value is passed through a real
> `RequestContext` and the method reads it back from `RequestContext.current()`.
> There is no mock, stub, or preset response.

---

## Project Structure

```
python-request-context/
├── src/
│   ├── __init__.py
│   └── graftcode/
│       ├── __init__.py
│       └── context.py          # RequestContext + GraftConfig implementation
├── vision/
│   ├── __init__.py
│   ├── request_context_demo.py # 8-method class — the Graftcode Vision module
│   ├── pyproject.toml          # Required by gg for module discovery
│   └── demo.py                 # Local runner (no Docker needed)
├── tests/
│   ├── __init__.py
│   ├── test_request_context.py # RequestContext unit tests
│   ├── test_graft_config.py    # GraftConfig unit tests (sync + async)
│   └── test_async_context.py   # Integration tests
├── conftest.py                 # pytest path setup
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile.vision           # gg + Python image (official docs pattern)
└── docker-compose.vision.yml   # One-command local run
```

---

## Running via Graftcode Vision

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) installed and running

### Step 1 — Build and start the container

```bash
# From the python-request-context directory
docker-compose -f docker-compose.vision.yml up --build
```

Expected output:
```
✔ Container request-context-vision  Started
```

### Step 2 — Open Vision in your browser

Navigate to: **http://localhost:81/GV**

You will see `RequestContextDemo` listed with all 8 public methods
auto-discovered from their Python type annotations.

### Step 3 — Try each case

Click any method in the sidebar → **"Try it out"** → fill in the form → **"Run"**.

### Gateway Connection Override

Override host and ports when auto-detect from the browser does not match your local gateway:
- **Host**: `localhost`
- **HTTP port**: `81`
- **WebSocket port**: `80`
- **MCP port**: `80`

*(Note: We use this split-port configuration (Vision UI on 81, Gateway execution on 80) in this Docker setup to cleanly separate the browser UI traffic from the WebSocket/MCP execution traffic, demonstrating how the Gateway can operate with isolated ports for security and routing purposes.)*

---

## The 8 Demo Cases

> **All outputs are dynamically generated** from live `RequestContext` state —
> not templates or mocks. Change an input and the output changes accordingly.

| # | Method | Inputs | What it demonstrates |
|---|--------|--------|----------------------|
| 1 | `health_check()` | none | `GraftConfig.set_headers()` global headers present in every context automatically |
| 2 | `auth_demo(authorization)` | `authorization` string | Gateway pattern: bind `Authorization` header → read it back via `RequestContext` |
| 3 | `auth_demo_missing_token()` | none | What a handler sees when no `Authorization` is present → 401-style error response |
| 4 | `correlation_demo(x_correlation_id)` | optional ID string | Propagate a supplied ID; auto-generate a UUID when the field is blank |
| 5 | `tenant_demo_missing_id()` | none | What a handler sees when no `X-Tenant-Id` is present → 400-style error response |
| 6 | `all_headers(authorization, x_correlation_id, x_tenant_id)` | all 3 headers | All per-request headers merged with global headers in one `RequestContext` — 6 total |
| 7 | `global_headers_demo()` | none | Same 3 startup headers appear in `global_headers_set_at_startup` and `visible_in_current_context` |
| 8 | `async_isolation_demo()` | none | Two concurrent async tasks with separate contexts — `isolation_verified: true` |

### How Vision Executes Each Case

```
You type a value in the Vision form (e.g. "Bearer my-token")
        ↓
Vision sends it over WebSocket (ws://localhost:80/ws) to gg
        ↓
gg calls the method with your input as a Python argument
        ↓
The method calls GraftConfig.invoke_with_headers(_handler, {"Authorization": your_value})
        ↓
A real RequestContext is created in memory with that header bound
        ↓
_handler() reads RequestContext.current().get_headers() — live, from memory
        ↓
Result is serialised to JSON and returned to Vision — displayed in the UI
```

**Proof the output is live:**

| Observation | Why it proves dynamic execution |
|---|---|
| Case 4 (blank input) returns `"correlation_id": "auto-<uuid>"` | UUID is newly generated on every run — impossible to hardcode |
| Case 8 returns `corr-alpha-<hex>`, `corr-beta-<hex>` | Hex suffix changes on every run |
| Case 2 — change the `authorization` field → output reflects your exact value | Directly reads from the `RequestContext` you created |
| Cases 3 & 5 show `null` for missing headers | The context truly has no `Authorization`/`X-Tenant-Id` — not a preset |

---

## Running Locally (without Docker)

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run the local demo script — exercises all 8 cases, prints JSON output
PYTHONPATH=src python vision/demo.py
```

---

## Running Tests

The unit tests exercise the library (`src/graftcode/`) directly — no Gateway
or Docker container required.

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests with coverage
PYTHONPATH=src pytest tests/ -v --cov=src --cov-report=term-missing

# Run a specific test file
PYTHONPATH=src pytest tests/test_graft_config.py -v
```

---

## How Graftcode Propagates Context

### Vision demo vs. real Gateway — same mechanism, different trigger

| | Graftcode Vision (this demo) | Real Graftcode Gateway (production) |
|---|---|---|
| **Who binds headers?** | Each demo method calls `GraftConfig.invoke_with_headers()` explicitly | The Gateway calls it automatically — your handler never sees this code |
| **What gets bound?** | The values you type into the Vision form | The HTTP headers from the inbound client request (JWT, tenant ID, correlation ID, etc.) |
| **How you read headers** | `RequestContext.current().get_headers()` | Identical — same one-liner |
| **Output** | Live JSON reflecting the real `RequestContext` state | Same — your service reads real validated headers |

The binding code is shown in the demo so you can **see** the mechanism. In production it is invisible.

### Server side (your deployed service)

When your service runs behind the **Graftcode Gateway**:

1. The client makes an HTTP request with standard headers (`Authorization`,
   `X-Correlation-Id`, `X-Tenant-Id`, etc.).
2. The Gateway intercepts the request, validates the JWT, resolves the tenant,
   and stamps correlation IDs.
3. The enriched headers are forwarded to your service.
4. The Gateway runtime binds them as a `RequestContext` **before** your handler
   is called.
5. Inside any handler (at any call depth), `RequestContext.current().get_headers()`
   returns them all.

### Client side (inside Grafts)

Grafts are Graftcode-generated client libraries. Since they run in your own
code (not behind the Gateway), you set headers explicitly:

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

Python's `contextvars.ContextVar` provides **copy-on-write semantics** for
`asyncio` Tasks. When `invoke_with_headers_async()` is called, it creates a
new context binding completely invisible to other concurrently running
coroutines — even those that share the same event loop thread.

```
Event Loop Thread
│
├── Task A  →  RequestContext(tenant=alpha)  ──► handler A sees only alpha
├── Task B  →  RequestContext(tenant=beta)   ──► handler B sees only beta
└── Task C  →  RequestContext(tenant=gamma)  ──► handler C sees only gamma
```

No locks, no thread-locals, no per-request singletons — just Python's
built-in concurrency primitives. Case 8 (`async_isolation_demo`) demonstrates
this live: two concurrent tasks run with different tenant IDs and correlation
IDs, and `isolation_verified: true` confirms neither task leaked headers to
the other.
