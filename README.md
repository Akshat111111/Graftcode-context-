# Python Request Context Demo

> **PyPI package:** [`graftcode-context`](https://pypi.org/project/graftcode-context/)

A focused Python demo showing how **Graftcode Context** propagates HTTP request
headers — authentication tokens, correlation IDs, and tenant IDs — through your
service without writing custom middleware or threading headers through every
function call.

The demo cases are exposed via **Graftcode Vision**: the built-in browser UI
that ships with every `gg` (Graftcode Gateway) deployment. No HTTP framework,
no REST routes, no controllers — just a plain Python class.


---

## Table of Contents

1. [What is Graftcode Context?](#what-is-graftcode-context)
2. [What is Graftcode Vision?](#what-is-graftcode-vision)
3. [The API](#the-api)
4. [Project Structure](#project-structure)
5. [Running via Graftcode Vision (Docker)](#running-via-graftcode-vision-docker)
6. [The Demo Cases](#the-demo-cases)
7. [Running Locally (without Docker)](#running-locally-without-docker)
8. [Running Tests](#running-tests)
9. [How Graftcode Propagates Context](#how-graftcode-propagates-context)

---

## What is Graftcode Context?

Graftcode Context is a standardised library that gives your service access to
request headers and metadata during Graftcode invocations. It is available for
multiple languages (Node.js, .NET, Java, Python, PHP, Ruby).

Install it from PyPI:

```bash
pip install graftcode-context
```

| Side | Who sets headers | How |
|------|-----------------|-----|
| **Server** | Graftcode Gateway | Automatically — calls `RequestContext.current().set_headers()` before your handler |
| **Client (Grafts)** | Your code | Call `set_headers()` before invoking a downstream service |

Reading headers in a handler is always the same one-liner:

```python
from graftcode import RequestContext

ctx = RequestContext.current()
headers = ctx.get_headers()
auth   = headers.get("Authorization")
tenant = headers.get("X-Tenant-Id")
corr   = headers.get("X-Correlation-Id")
```

No middleware configuration. No dependency injection. No parameter threading.

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

> **Quick Start:** https://pypi.org/project/graftcode-context/

---

## The API

`graftcode-context 1.0.0` exports exactly three methods on `RequestContext`:

```python
from graftcode import RequestContext

# Get (or create) the context for the current execution scope
ctx = RequestContext.current()

# Set headers — the Gateway calls this before your handler runs
ctx.set_headers({"Authorization": "Bearer ...", "X-Tenant-Id": "acme"})

# Read headers — your handler calls this
headers = ctx.get_headers()  # → dict[str, str | None]
```

That's the entire public surface. No `GraftConfig`, no `invoke_with_headers` — 
the Gateway handles context injection transparently.

---

## Project Structure

```
python-request-context/
├── vision/
│   ├── __init__.py
│   ├── request_context_demo.py   # 7-method demo class — the Vision module
│   ├── pyproject.toml            # Required by gg for module discovery
│   └── demo.py                   # Local runner (no Docker needed)
├── tests/
│   ├── __init__.py
│   ├── test_request_context.py   # RequestContext unit tests
│   └── test_request_context_demo.py  # Integration tests against demo methods
├── blog/
│   ├── build-context-aware-python-services.md
│   └── assets/                   # Screenshots used in the blog post
├── conftest.py                   # pytest path setup
├── context.md                    # Setup cheat sheet and expected outputs
├── pytest.ini
├── requirements.txt              # graftcode-context>=1.0.0
├── requirements-dev.txt
├── Dockerfile.vision             # gg + Python image (official docs pattern)
└── docker-compose.vision.yml     # One-command local run
```

---

## Running via Graftcode Vision (Docker)

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) installed and running

### Step 1 — Build and start the container

```bash
# From the python-request-context directory
docker-compose -f docker-compose.vision.yml up --build
```

The Dockerfile installs `graftcode-context` from PyPI — the same package your
users install. No local library copies.

### Step 2 — Open Vision in your browser

Navigate to: **http://localhost:81/GV**

You will see `RequestContextDemo` listed with all public methods auto-discovered.

### Step 3 — Try each case

Click any method in the sidebar → **"Try it out"** → fill in the form → **"Run"**.

### Gateway Connection Override

Override host and ports when auto-detect from the browser does not match your local gateway:
- **Host**: `localhost`
- **HTTP port**: `81`
- **WebSocket port**: `80`
- **MCP port**: `80`

*(Note: We use this split-port configuration (Vision UI on 81, Gateway execution on 80) in this Docker setup to cleanly separate the browser UI traffic from the WebSocket/MCP execution traffic.)*

---

## The Demo Cases

> **All outputs are dynamically generated** from live `RequestContext` state —
> not templates or mocks. Change an input and the output changes accordingly.

| # | Method | Inputs | What it demonstrates |
|---|--------|--------|----------------------|
| 1 | `health_check()` | none | Gateway-injected WebSocket handshake headers visible via `get_headers()` — proves the Gateway does the injection automatically |
| 2 | `auth_demo(authorization)` | `authorization` string | Gateway pattern: `set_headers({"Authorization": ...})` → `get_headers()` |
| 3 | `auth_demo_missing_token()` | none | Handler detecting absent `Authorization` → 401-style error response |
| 4 | `correlation_demo(x_correlation_id)` | optional ID string | Propagate a supplied ID; auto-generate a UUID when the field is blank |
| 5 | `tenant_demo_missing_id()` | none | Handler detecting absent `X-Tenant-Id` → 400-style error response |
| 6 | `all_headers(authorization, x_correlation_id, x_tenant_id)` | all 3 headers | All per-request headers visible in one `get_headers()` call |
| 7 | `context_replace_demo(first_tenant, second_tenant)` | two tenant IDs | `set_headers()` replaces the full context — shows Gateway per-request reset behaviour |

### How Vision executes each case

```
You click "Run" on a method in Vision
        ↓
Vision sends any form inputs over WebSocket (ws://localhost:80/ws) to gg
        ↓
gg calls the method with your inputs as Python arguments
        ↓
  • Case 1: the Gateway already injected real WebSocket handshake headers before
    calling the handler — health_check() calls get_headers() directly, no set_headers()
  • Cases 2–7: the method calls set_headers({...}) with headers built from your form input,
    then reads them back via get_headers()
        ↓
A real RequestContext is populated with those headers in memory
        ↓
get_headers() reads them back — live, from the ContextVar
        ↓
Result is serialised to JSON and returned to Vision — displayed in the UI
```

**Proof the output is live:**

| Observation | Why it proves dynamic execution |
|---|---|
| Case 4 (blank input) returns `"correlation_id": "auto-<uuid>"` | UUID is newly generated on every run — impossible to hardcode |
| Case 2 — change the `authorization` field → output reflects your exact value | Directly reads from the `RequestContext` you created |
| Cases 3 & 5 show `null` for missing headers | The context truly has no `Authorization`/`X-Tenant-Id` — not a preset |

---

## Running Locally (without Docker)

First install the dev dependencies (includes `graftcode-context` from PyPI):

```bash
pip install -r requirements-dev.txt
```

Then run the local demo script — exercises all cases and prints JSON output:

**bash / zsh:**
```bash
python vision/demo.py
```

**PowerShell:**
```powershell
python vision/demo.py
```

---

## Running Tests

The unit tests exercise `RequestContext` (from the real installed package) directly.
No Gateway or Docker container required.

**bash / zsh:**
```bash
pytest tests/ -v
```

**PowerShell:**
```powershell
pytest tests/ -v
```

Run a specific test file:

**bash / zsh:**
```bash
pytest tests/test_request_context.py -v
```

**PowerShell:**
```powershell
pytest tests/test_request_context.py -v
```

---

## How Graftcode Propagates Context

### Vision demo vs. real Gateway — same mechanism, different trigger

| | Graftcode Vision (this demo) | Real Graftcode Gateway (production) |
|---|---|---|
| **Who sets headers?** | Case 1: the Gateway injects real WebSocket handshake headers automatically. Cases 2–7: each method calls `set_headers()` explicitly with form input values | The Gateway calls it automatically — your handler never sees this code |
| **What gets bound?** | Case 1: real live connection headers. Cases 2–7: the values you type into the Vision form | The HTTP headers from the inbound client request (JWT, tenant ID, correlation ID, etc.) |
| **How you read headers** | `RequestContext.current().get_headers()` | Identical — same one-liner |
| **Output** | Live JSON reflecting the real `RequestContext` state | Same — your service reads real validated headers |

Case 1 is the purest demonstration: `health_check()` never calls `set_headers()` — the Gateway does it transparently. Cases 2–7 make the injection step visible so you can see the exact mechanism.

### Server side (your deployed service)

When your service runs behind the **Graftcode Gateway**:

1. The client makes an HTTP request with standard headers (`Authorization`,
   `X-Correlation-Id`, `X-Tenant-Id`, etc.).
2. The Gateway intercepts the request, validates the JWT, resolves the tenant,
   and stamps correlation IDs.
3. The enriched headers are forwarded to your service.
4. The Gateway runtime calls `RequestContext.current().set_headers()` **before** your handler.
5. Inside any handler (at any call depth), `RequestContext.current().get_headers()`
   returns them all.
