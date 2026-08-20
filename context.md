# Graftcode Vision — Setup & Demo Cheat Sheet

---

## 1. Gateway Connection

Override host and ports when auto-detect from the browser does not match your local gateway.

| Setting        | Value | Why |
|----------------|-------|-----|
| Host           | `localhost` | |
| HTTP port      | `81`  | Vision serves library data on port 81 |
| WebSocket port | `80`  | Gateway execution WebSocket runs on port 80 |
| MCP port       | `80`  | Gateway API runs on port 80 |

> **Note:** Port `81` = Vision UI + HTTP library fetch. Port `80` = gateway execution (WebSocket/MCP). They are different.

To apply: open Graftcode Vision at `http://localhost:81/GV`, click the **gear icon** (⚙) in the top bar, enter the values above, and click **Save**.

---

## 2. Running the 8 Demo Cases

Navigate to `http://localhost:81/GV` → expand **RequestContextDemo** in the left sidebar → click a method → click **"Try it out"** → fill inputs → click **"Run"**.

---

### Case 1 — `health_check`

**Inputs:** _(none)_

**Expected output:**
```json
{
  "service": "Graftcode Request Context Demo (Python)",
  "version": "1.0.0",
  "status": "healthy",
  "docs": "https://docs.graftcode.com/security-and-trust/graftcode-context",
  "global_headers_always_present": {
    "X-Service-Name": "graftcode-python-demo",
    "X-Api-Version": "v1",
    "X-Environment": "local-dev"
  },
  "explanation": "GraftConfig.set_headers() was called once at startup. RequestContext.current() returns them in every context -- no per-request code required."
}
```

---

### Case 2 — `auth_demo`

**Inputs:**

| Field           | Value                                          |
|-----------------|------------------------------------------------|
| `authorization` | `Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig`     |

**Expected output:**
```json
{
  "message": "Authorization header read from RequestContext -- zero boilerplate",
  "token_type": "Bearer",
  "token_preview": "eyJhbGciOiJSUzI1...",
  "full_authorization": "Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig",
  "user_id": null,
  "all_headers_in_context": {
    "X-Service-Name": "graftcode-python-demo",
    "X-Api-Version": "v1",
    "X-Environment": "local-dev",
    "Authorization": "Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig"
  },
  "how_gateway_does_it": "The Graftcode Gateway intercepts the client request, validates the JWT, and calls invoke_with_headers() before your handler runs. Your handler just calls RequestContext.current() -- that is it."
}
```

---

### Case 3 — `auth_demo_missing_token`

**Inputs:** _(none)_

**Expected output:**
```json
{
  "http_status_equivalent": 401,
  "error": "No Authorization header in context",
  "authorization_value": null,
  "available_headers": [
    "X-Service-Name",
    "X-Api-Version",
    "X-Environment"
  ],
  "hint": "In production the Graftcode Gateway rejects unauthenticated requests before they reach your service. This case shows what your handler sees when no Authorization header is present."
}
```

---

### Case 4 — `correlation_demo`

**Inputs:**

| Field              | Value                                      |
|--------------------|--------------------------------------------|
| `x_correlation_id` | _(leave blank for auto-generation)_ **or** type e.g. `req-5f3a-2026` to supply one |

**Expected output (blank input — auto-generated):**
```json
{
  "correlation_id": "auto-<uuid>",
  "was_auto_generated": true,
  "message": "No X-Correlation-Id supplied -- auto-generated for this response",
  "distributed_tracing_tip": "In production every service reads the same X-Correlation-Id from RequestContext and includes it in logs -- end-to-end tracing without manual propagation.",
  "all_headers_in_context": {
    "X-Service-Name": "graftcode-python-demo",
    "X-Api-Version": "v1",
    "X-Environment": "local-dev"
  }
}
```

**Expected output (with `req-5f3a-2026`):**
```json
{
  "correlation_id": "req-5f3a-2026",
  "was_auto_generated": false,
  "message": "Correlation ID propagated from client via Graftcode Gateway",
  ...
}
```

---

### Case 5 — `tenant_demo_missing_id`

**Inputs:** _(none)_

**Expected output:**
```json
{
  "http_status_equivalent": 400,
  "error": "X-Tenant-Id header not found in context",
  "tenant_id_value": null,
  "available_headers": [
    "X-Service-Name",
    "X-Api-Version",
    "X-Environment"
  ],
  "hint": "In production the Graftcode Gateway resolves the tenant from the JWT and injects X-Tenant-Id automatically. This case shows the error path when it is absent."
}
```

---

### Case 6 — `all_headers`

**Inputs:**

| Field              | Value        |
|--------------------|--------------|
| `authorization`    | `Bearer tok` |
| `x_correlation_id` | `trace-001`  |
| `x_tenant_id`      | `acme-corp`  |

**Expected output:**
```json
{
  "total_headers": 6,
  "graftcode_x_headers": {
    "X-Service-Name": "graftcode-python-demo",
    "X-Api-Version": "v1",
    "X-Environment": "local-dev",
    "X-Correlation-Id": "trace-001",
    "X-Tenant-Id": "acme-corp"
  },
  "authentication": {
    "Authorization": "Bearer tok"
  },
  "other": {},
  "raw": {
    "X-Service-Name": "graftcode-python-demo",
    "X-Api-Version": "v1",
    "X-Environment": "local-dev",
    "Authorization": "Bearer tok",
    "X-Correlation-Id": "trace-001",
    "X-Tenant-Id": "acme-corp"
  },
  "note": "X-Service-Name, X-Api-Version, and X-Environment are injected globally via GraftConfig.set_headers() at startup and appear in every context alongside the per-request headers."
}
```

---

### Case 7 — `global_headers_demo`

**Inputs:** _(none)_

**Expected output:**
```json
{
  "global_headers_set_at_startup": {
    "X-Service-Name": "graftcode-python-demo",
    "X-Api-Version": "v1",
    "X-Environment": "local-dev"
  },
  "visible_in_current_context": {
    "X-Service-Name": "graftcode-python-demo",
    "X-Api-Version": "v1",
    "X-Environment": "local-dev"
  },
  "code_snippet": "GraftConfig.set_headers({\n    \"X-Service-Name\": \"graftcode-python-demo\",\n    \"X-Api-Version\": \"v1\",\n    \"X-Environment\": \"local-dev\",\n})",
  "explanation": "Call GraftConfig.set_headers() once at startup. Every subsequent RequestContext will automatically contain these headers -- no manual injection into each handler or function call required."
}
```

---

### Case 8 — `async_isolation_demo`

**Inputs:** _(none)_

> ⏱ May take 1–2 seconds — two concurrent async tasks are running.

**Expected output:**
```json
{
  "message": "Two concurrent async calls with fully isolated RequestContexts",
  "task_a": {
    "task": "Task-A",
    "tenant_id": "tenant-alpha",
    "correlation_id": "corr-alpha-<hex>",
    "authorization": "Bearer alpha-token",
    "all_headers_seen": {
      "X-Service-Name": "graftcode-python-demo",
      "X-Api-Version": "v1",
      "X-Environment": "local-dev",
      "X-Tenant-Id": "tenant-alpha",
      "X-Correlation-Id": "corr-alpha-<hex>",
      "Authorization": "Bearer alpha-token"
    }
  },
  "task_b": {
    "task": "Task-B",
    "tenant_id": "tenant-beta",
    "correlation_id": "corr-beta-<hex>",
    "authorization": "Bearer beta-token",
    "all_headers_seen": {
      "X-Service-Name": "graftcode-python-demo",
      "X-Api-Version": "v1",
      "X-Environment": "local-dev",
      "X-Tenant-Id": "tenant-beta",
      "X-Correlation-Id": "corr-beta-<hex>",
      "Authorization": "Bearer beta-token"
    }
  },
  "outer_context_tenant_id": null,
  "outer_context_unchanged": true,
  "isolation_verified": true,
  "how_it_works": "Python's contextvars.ContextVar provides copy-on-write semantics for asyncio Tasks. invoke_with_headers_async() binds a new context for each call so concurrent requests never share or overwrite each other's headers."
}
```

