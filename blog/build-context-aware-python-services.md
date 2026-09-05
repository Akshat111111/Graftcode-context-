# Build Context-Aware Python Services Without Custom Middleware Using Graftcode

> **PyPI package:** [`graftcode-context`](https://pypi.org/project/graftcode-context/)

---

## Introduction

Every non-trivial Python service eventually hits the same wall: you need to know *who* is making a request, *which tenant* they belong to, and *where* to trace the call when something goes wrong. The data is right there in the HTTP headers — but threading it through your entire application without creating a mess is harder than it sounds.

This article explores that problem, shows why traditional approaches with Flask and FastAPI middleware create coupling and boilerplate, and demonstrates how **Graftcode Context** eliminates all of it with a single method call anywhere in your code.

---

## Why Request Context Matters in Distributed Systems

In a monolith, request context is annoying but manageable. You might store it in a thread-local, pass it as a function parameter, or smuggle it through a global variable.

In a distributed system, the stakes are higher:

**Authentication** — A JWT must be validated once at the gateway and then *trusted* by downstream services. Re-validating in every service wastes CPU and creates surface area for bugs.

**Correlation IDs** — A user sees a 500 error. Without a correlation ID flowing through every log line authentication service, order service, inventory service, payment service — finding the root cause means searching through millions of unrelated events.

**Multi-tenancy** — SaaS products must ensure that tenant A never accidentally reads tenant B's data. The safest design routes every database query through a tenant filter that is *automatically* derived from the request, not passed manually.

**Audit logging** — Compliance regulations demand a complete record of who did what. If user ID falls out of the call stack at any layer, your audit log is incomplete.

The common thread: request-scoped data must flow *implicitly* through the entire call graph, not be threaded manually through every function signature.

---

## Traditional Approaches: The Flask/FastAPI Middleware Trap

### Flask: Thread-locals and g

Flask's `g` object provides per-request storage backed by thread-local state:

```python
# Flask approach
from flask import g, request

@app.before_request
def extract_context():
    g.auth_token = request.headers.get("Authorization")
    g.correlation_id = request.headers.get("X-Correlation-Id")
    g.tenant_id = request.headers.get("X-Tenant-Id")
```

This seems elegant until you need the tenant ID five layers deep in your service layer:

```python
# You must thread it through every function, or use g globally
def create_order(user_id: int, items: list):
    tenant_id = g.tenant_id  # Tight coupling to Flask's g
    return db.query(Order).filter_by(tenant_id=tenant_id).all()
```

The problems multiply quickly:
- **Framework lock-in:** `g` only works inside a Flask request context. Unit tests must mock it.
- **Async incompatibility:** Thread-locals break with async frameworks.
- **Hidden coupling:** Your domain logic silently depends on Flask internals.

### FastAPI: Dependency Injection Boilerplate

FastAPI's canonical solution is dependency injection:

```python
# FastAPI approach — dependency injection
from fastapi import Depends, Request

async def get_auth_token(request: Request) -> str:
    return request.headers.get("Authorization", "")

async def get_tenant_id(request: Request) -> str:
    return request.headers.get("X-Tenant-Id", "")

async def get_correlation_id(request: Request) -> str:
    return request.headers.get("X-Correlation-Id", "")

# Every endpoint that needs context must declare dependencies
@app.get("/orders")
async def list_orders(
    auth: str = Depends(get_auth_token),
    tenant: str = Depends(get_tenant_id),
    corr_id: str = Depends(get_correlation_id),
):
    # Now you must pass these to every service function
    return await order_service.list_orders(tenant, auth, corr_id)
```

And the service layer:

```python
# You're now threading context through every function
class OrderService:
    async def list_orders(self, tenant_id: str, auth: str, corr_id: str):
        await self.db.query_with_tenant(tenant_id)
        await self.audit.log(user=auth, corr=corr_id)
        # ...and every sub-call needs these parameters too
```

This is verbose, repetitive, and creates a function signature explosion as the number of context fields grows. It also ties your domain logic to your HTTP layer — making unit testing harder and service reuse nearly impossible.

### Custom Middleware with contextvars

The clever Python developer eventually discovers `contextvars` and rolls a custom solution:

```python
# Custom contextvars approach — you build and maintain this
import contextvars
from starlette.middleware.base import BaseHTTPMiddleware

_auth_var = contextvars.ContextVar("auth")
_tenant_var = contextvars.ContextVar("tenant")
_corr_var = contextvars.ContextVar("correlation")

class ContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        token_a = _auth_var.set(request.headers.get("Authorization", ""))
        token_t = _tenant_var.set(request.headers.get("X-Tenant-Id", ""))
        token_c = _corr_var.set(request.headers.get("X-Correlation-Id", ""))
        try:
            return await call_next(request)
        finally:
            _auth_var.reset(token_a)
            _tenant_var.reset(token_t)
            _corr_var.reset(token_c)

def get_tenant():
    return _tenant_var.get("")
```

Better! But now you're maintaining your own context library. You need to add new headers, handle defaults, ensure proper reset on exceptions, support nested overrides, document it, and test it — for every service, every team, every language.

---

## How Graftcode Context Simplifies Everything

Graftcode Context is the standardised solution that works on both sides of the equation:

- **Server side:** The Graftcode Gateway automatically populates `RequestContext` before your handler runs. Zero configuration.
- **Client side:** You can easily set headers on the context from any code that invokes Graftcode services using `RequestContext.current().set_headers()`.


Install from PyPI:

```bash
pip install graftcode-context
```

> Package: https://pypi.org/project/graftcode-context/

---

## Understanding RequestContext

`RequestContext` is a thread-safe (async-safe) construct that holds all request headers for the current execution scope. It uses Python's `contextvars.ContextVar` internally.

```python
from graftcode import RequestContext

# Works anywhere in your call stack — handler, service, repository
headers = RequestContext.current().get_headers()

auth_token   = headers.get("Authorization")
correlation  = headers.get("X-Correlation-Id")
tenant_id    = headers.get("X-Tenant-Id")
user_id      = headers.get("X-User-Id")
```

The API is intentionally minimal. There is one method to remember: `RequestContext.current().get_headers()`.

### Server-side usage (no framework required)

Graftcode Context works with **any** Python HTTP server — or no framework at all.  When your service runs behind the Graftcode Gateway, the Gateway populates `RequestContext` before your handler is called.  For local development the same effect is achieved with a tiny helper that mirrors what the Gateway does:

```python
from http.server import BaseHTTPRequestHandler, HTTPServer
from graftcode import RequestContext

class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Inject context — in production the Gateway does this for you
        ctx = RequestContext.current()
        ctx.set_headers(dict(self.headers))
        
        handle_orders(self)

def handle_orders(h):
    # Zero boilerplate — identical whether hosted on http.server,
    # Flask, FastAPI, or behind the Graftcode Gateway directly
    headers = RequestContext.current().get_headers()
    tenant  = headers.get("X-Tenant-Id")
    user    = headers.get("X-User-Id")
    # ... serve the response
```

The critical point: the application code (`RequestContext.current().get_headers()`) is **identical** regardless of the host.  Swapping from local `http.server` to the Graftcode Gateway in production requires zero changes to your handlers.

The real benefit becomes clear in the service layer underneath, which has **zero coupling to any HTTP framework**:

```python
# Service layer — no framework imports whatsoever
class OrderService:
    async def list_for_tenant(self, tenant_id: str, user_id: str):
        # RequestContext works here too — no parameters needed
        headers = RequestContext.current().get_headers()
        await self.audit.log(
            action="list_orders",
            tenant=tenant_id,
            user=headers.get("X-User-Id"),
            correlation=headers.get("X-Correlation-Id"),
        )
        return await self.db.query(Order, tenant=tenant_id)
```

---

## Example: Authentication & Correlation IDs

Let's build a realistic service that handles JWT authentication and distributed tracing without any boilerplate.  This example uses the standard-library `http.server` — no framework required:

```python
from http.server import BaseHTTPRequestHandler, HTTPServer
from graftcode import RequestContext

def handle_get_order(h: BaseHTTPRequestHandler, order_id: str) -> None:
    headers = RequestContext.current().get_headers()

    # Authentication — read directly from context, no parameter needed
    auth = headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        h._json_response(401, {"detail": "Missing auth token"})
        return

    # Distributed tracing — already available, no threading required
    correlation_id = headers.get("X-Correlation-Id")
    tenant_id      = headers.get("X-Tenant-Id")

    logger.info(
        "Fetching order",
        extra={"order_id": order_id, "tenant": tenant_id, "correlation": correlation_id},
    )

    # Fetch order — tenant isolation is automatic
    order = order_repo.get(order_id, tenant_id=tenant_id)
    h._json_response(200, order)
```

Compare this to the FastAPI Depends() version: **3 fewer parameters, no framework imports, no coupling to HTTP concerns in your business logic** — and it runs on plain Python.

---

## Running Locally and with Docker / Graftcode Gateway

### Local development

No framework, no extra tooling — just Python. You can run our interactive demo script:

**bash / zsh:**
```bash
pip install -r requirements-dev.txt
python vision/demo.py
```

**PowerShell:**
```powershell
pip install -r requirements-dev.txt
python vision/demo.py
```

The script exercises all 7 demo cases directly and prints the live JSON output
to your terminal. Cases 2–7 inject context explicitly via `set_headers()`,
mirroring exactly what the Gateway does. **Case 1** (`health_check`) never calls
`set_headers()`, so locally `headers_in_context` is `{}` — the output explains
this and points you to Vision to see the real Gateway injection in action.

### Docker

To see the interactive **Graftcode Vision** browser UI:

```bash
docker-compose -f docker-compose.vision.yml up --build
```

Service available at http://localhost:81/GV.

**Gateway Connection Override**

Override host and ports when auto-detect from the browser does not match your local gateway:
- **Host**: `localhost`
- **HTTP port**: `81`
- **WebSocket port**: `80`
- **MCP port**: `80`

*(Note: We use this split-port configuration (Vision UI on 81, Gateway execution on 80) in this Docker setup to cleanly separate the browser UI traffic from the WebSocket/MCP execution traffic, demonstrating how the Gateway can operate with isolated ports for security and routing purposes.)*

![Gateway Connection Settings](assets/Demo%20Dashboard.png)

### Graftcode Gateway integration

When deployed behind the Gateway, the Gateway takes over context injection entirely — the manual `set_headers()` call in your server is not needed.  Your handler code (`RequestContext.current()` calls) is **completely unchanged**.  The transition from local to production is zero-code.

---

## Real-World Use Cases

> **Note:** The following snippets are conceptual examples demonstrating how you might use `RequestContext` in various layers of your application (like middlewares, repositories, or loggers). They are intended to illustrate the pattern, not to be copy-pasted as runnable code.

### JWT Authentication

The Gateway validates the JWT signature and expiry. Your service trusts the forwarded `Authorization` header:

```python
def get_current_user():
    """Extract user claims from the pre-validated token."""
    headers = RequestContext.current().get_headers()
    auth = headers.get("Authorization", "")
    # Token is already validated by Gateway — just decode claims
    token = auth.removeprefix("Bearer ")
    return jwt.decode(token, options={"verify_signature": False})["sub"]
```

No signature validation in your service. No repeated secret management. Security responsibility stays at the edge.

---

### Multi-Tenancy

```python
class TenantRepository:
    async def get_all(self, model_class):
        """All queries are automatically scoped to the current tenant."""
        headers = RequestContext.current().get_headers()
        tenant_id = headers.get("X-Tenant-Id")
        if not tenant_id:
            raise RuntimeError("X-Tenant-Id missing from context")
        return await db.query(model_class).filter_by(tenant_id=tenant_id).all()
```

No `tenant_id` parameter anywhere. The `TenantRepository` reads it directly from `RequestContext` — making it impossible to accidentally query across tenants.

---

### Distributed Tracing

```python
class StructuredLogger:
    def info(self, message: str, **extra):
        headers = RequestContext.current().get_headers()
        log_entry = {
            "level": "INFO",
            "message": message,
            # Automatically included in every log line
            "correlation_id": headers.get("X-Correlation-Id"),
            "tenant_id": headers.get("X-Tenant-Id"),
            "user_id": headers.get("X-User-Id"),
            **extra,
        }
        print(json.dumps(log_entry))
```

Every log line in every service in the call chain carries the same `X-Correlation-Id`. When an error occurs, a single grep surfaces the entire request path across all services.

---

### Audit Logging

```python
class AuditService:
    async def record(self, action: str, resource_id: str):
        headers = RequestContext.current().get_headers()
        await db.insert(AuditLog(
            action=action,
            resource_id=resource_id,
            user_id=headers.get("X-User-Id"),
            tenant_id=headers.get("X-Tenant-Id"),
            correlation_id=headers.get("X-Correlation-Id"),
            timestamp=datetime.utcnow(),
        ))
```

Compliance-grade audit logs with zero parameter threading. Call `AuditService.record()` from anywhere in your code and all required metadata is available automatically.

---

### Request Tracking

```python
class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        headers = RequestContext.current().get_headers()
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start
        
        metrics.histogram(
            "request_duration_seconds",
            duration,
            labels={
                "tenant": headers.get("X-Tenant-Id", "unknown"),
                "correlation": headers.get("X-Correlation-Id", ""),
                "service": headers.get("X-Service-Name", ""),
            },
        )
        return response
```

---

## Benefits for AI Agents and MCP

Graftcode Context becomes even more powerful in agentic architectures.

AI agents that orchestrate multiple tool calls or service invocations often need to:
- Forward the originating user's identity to downstream services
- Propagate a single correlation ID across a multi-step reasoning chain
- Route tool calls to the correct tenant's data namespace

With Graftcode Context, an agent runtime can set headers once at the start of an agent execution:

```python
# Agent runtime: set context at the start of an agent run
ctx = RequestContext.current()
ctx.set_headers({
    "Authorization": f"Bearer {user_jwt}",
    "X-Tenant-Id": tenant_id,
    "X-Correlation-Id": f"agent-run-{run_id}",
    "X-Agent-Id": agent_id,
})

# Every tool call the agent makes automatically carries this context
result = await tool_registry.invoke("search_orders", query="latest")
# The search_orders tool reads X-Tenant-Id from RequestContext — 
# no need for the agent to pass it explicitly
```

For **Model Context Protocol (MCP)** servers built on Graftcode, request context flows transparently from the MCP client through the Gateway into the MCP server — enabling secure, tenant-aware, traceable AI tool invocations without any additional plumbing.

---

## Live API Demonstration

To prove these concepts in action, we expose all 7 demo cases through **Graftcode Vision**, the auto-generated browser UI that ships with every Graftcode Gateway. Here are the results demonstrating how Graftcode Context behaves:

> **All outputs are dynamically generated** from live `RequestContext` state —
> not templates or mocks. Change an input and the output changes accordingly.

| # | Method | Inputs | What it demonstrates |
|---|--------|--------|----------------------|
| 1 | `health_check()` | none | Gateway-injected WebSocket handshake headers visible via `get_headers()` — proves the Gateway does the injection automatically |
| 2 | `auth_demo(authorization)` | `authorization` string | Gateway pattern: bind `Authorization` header → read it back via `RequestContext` |
| 3 | `auth_demo_missing_token()` | none | What a handler sees when no `Authorization` is present → 401-style error response |
| 4 | `correlation_demo(x_correlation_id)` | optional ID string | Propagate a supplied ID; auto-generate a UUID when the field is blank |
| 5 | `tenant_demo_missing_id()` | none | What a handler sees when no `X-Tenant-Id` is present → 400-style error response |
| 6 | `all_headers(authorization, x_correlation_id, x_tenant_id)` | all 3 headers | All per-request headers set in one `RequestContext` |
| 7 | `context_replace_demo(first_tenant, second_tenant)` | two tenant IDs | `set_headers()` replaces the full context — shows Gateway per-request reset behaviour |

### How Vision Executes Each Case

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
The handler code reads RequestContext.current().get_headers() — live, from memory
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

### Case 1: Health Check
![Case 1: Health Check part 1](assets/case%201%20a.png)
![Case 1: Health Check part 2](assets/case%201%20b.png)
**Explanation:** The root endpoint shows our service is healthy. Notice that the context isn't empty — the Graftcode Gateway automatically captured the real HTTP headers that initiated the WebSocket connection (like `user-agent` and `host`) and injected them into the `RequestContext` before invoking our method.

### Case 2: Auth Demo (With Bearer Token)
![Case 2: Auth Demo with Token](assets/case%202.png)
**Explanation:** When a valid token is provided, `RequestContext` reads the `Authorization` header effortlessly. No dependency injection or manual extraction needed.

### Case 3: Auth Demo (Missing Token)
![Case 3: Auth Demo without Token](assets/case%203.png)
**Explanation:** If the token is missing, the handler identifies the absence from the context and rightfully returns a 401 Unauthorized error equivalent.

### Case 4: Correlation ID Propagation
![Case 4: Correlation ID](assets/case%204.png)
**Explanation:** The `X-Correlation-Id` flows smoothly into the response. If left blank, it auto-generates a UUID to ensure tracing is never broken.

### Case 5: Tenant Isolation
![Case 5: Tenant Demo](assets/case%205.png)
**Explanation:** Demonstrates strict isolation; failing to provide an `X-Tenant-Id` safely returns a 400 error, preventing cross-tenant data leakage.

### Case 6: Request Context Aggregation
![Case 6: All Headers part 1](assets/case%206%20a.png)
![Case 6: All Headers part 2](assets/case%206%20b.png)
**Explanation:** A comprehensive view of all headers currently active in the request context, showing that all headers can be accessed with a single call.

### Case 7: Context Replacement Enforcement
![Case 7: Context Replace Demo](assets/case%207.png)
**Explanation:** Calling `set_headers()` replaces the existing context, which mimics exactly how the Graftcode Gateway sets a clean, new context per-request.

---

## Conclusion

Request context propagation is one of those problems that seems small at first and silently grows into a significant source of bugs, security issues, and maintenance burden.

Traditional solutions — Flask's `g`, FastAPI's dependency injection, hand-rolled `contextvars` middleware — all require repeating the same boilerplate in every service, every team, and every language.

**Graftcode Context** replaces all of that with two primitives:

| Scenario | API |
|----------|-----|
| Setting headers into context | `RequestContext.current().set_headers(headers)` |
| Reading headers in a handler | `RequestContext.current().get_headers()` |

The result is service code that is:

- **Decoupled** from the HTTP framework — domain logic carries no framework imports
- **Automatically async-safe** — Python's `contextvars` provides the guarantee internally
- **Trivially testable** — call `RequestContext.current().set_headers()` in test setup, done
- **Production-ready** — the Graftcode Gateway handles propagation; zero code changes when you deploy

If you're building distributed Python services — or AI agents that call services — Graftcode Context is the right abstraction for propagating request-scoped data across your entire call graph.

---

**Try the demo:**

```bash
git clone <repo>
cd graftcode-demo/python-request-context
docker-compose -f docker-compose.vision.yml up --build
# Open http://localhost:81/GV
```

**Official resources:**
- PyPI: https://pypi.org/project/graftcode-context/
