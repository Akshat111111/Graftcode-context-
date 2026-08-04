"""
graftcode.context
~~~~~~~~~~~~~~~~~

Python implementation of the Graftcode Context Library.

This mirrors the official `graftcode-context` PyPI package
(https://pypi.org/project/graftcode-context/) which is automatically
used by services running behind the Graftcode Gateway.

Key APIs
--------
- RequestContext.current()           — returns the active request context
- RequestContext.current().get_headers()  — returns all propagated headers
- GraftConfig.set_headers(dict)      — set global headers for all calls
- GraftConfig.invoke_with_headers(fn, headers)        — per-call override (sync)
- GraftConfig.invoke_with_headers_async(coro_fn, headers)  — per-call override (async)

Reference
---------
https://docs.graftcode.com/security-and-trust/graftcode-context
"""

import contextvars
import threading
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Internal storage
# ---------------------------------------------------------------------------

#: Holds the active RequestContext scoped to the current coroutine / thread.
_request_context_var: contextvars.ContextVar[Optional["RequestContext"]] = (
    contextvars.ContextVar("_graftcode_request_context", default=None)
)

#: Process-wide global headers (set via GraftConfig.set_headers).
_global_headers: Dict[str, str] = {}
_global_headers_lock = threading.RLock()


# ---------------------------------------------------------------------------
# RequestContext
# ---------------------------------------------------------------------------


class RequestContext:
    """
    Thread-safe (and async-safe) singleton that exposes request headers
    injected by the Graftcode Gateway.

    On the **server side**, headers are set automatically by the Gateway
    before your handler is invoked — you never instantiate this class
    directly.

    On the **client side** (inside Grafts), headers are set via
    :class:`GraftConfig` before making a remote call.

    Usage (server-side handler)::

        from graftcode_context import RequestContext

        def my_handler():
            headers = RequestContext.current().get_headers()
            auth   = headers.get("Authorization")
            corr   = headers.get("X-Correlation-Id")
            tenant = headers.get("X-Tenant-Id")
            ...

    Reference: https://docs.graftcode.com/security-and-trust/graftcode-context
    """

    def __init__(self, headers: Optional[Dict[str, str]] = None) -> None:
        # Normalise keys to lowercase for consistent case-insensitive lookup
        self._headers: Dict[str, str] = (
            {k.lower(): v for k, v in headers.items()} if headers else {}
        )

    # ------------------------------------------------------------------
    # Class-level accessor — the primary public API
    # ------------------------------------------------------------------

    @classmethod
    def current(cls) -> "RequestContext":
        """
        Return the :class:`RequestContext` bound to the current execution scope.

        When called inside a Graftcode Gateway-hosted handler, the context
        is already populated with all forwarded request headers.

        When called outside a request (e.g. during startup or in tests), an
        empty context is returned — never raises.

        Returns
        -------
        RequestContext
            The active context for the current coroutine or thread.
        """
        ctx = _request_context_var.get()
        if ctx is None:
            # Fall back to global headers so set_headers() is always visible
            with _global_headers_lock:
                return cls(dict(_global_headers))
        return ctx

    # ------------------------------------------------------------------
    # Internal helpers used by GraftConfig and the Gateway middleware
    # ------------------------------------------------------------------

    @classmethod
    def _bind(cls, ctx: "RequestContext") -> contextvars.Token:
        """Bind *ctx* to the current scope; returns a token to undo later."""
        return _request_context_var.set(ctx)

    @classmethod
    def _unbind(cls, token: contextvars.Token) -> None:
        """Restore the previous context using *token*."""
        _request_context_var.reset(token)

    # ------------------------------------------------------------------
    # Public header accessors
    # ------------------------------------------------------------------

    def get_headers(self) -> Dict[str, str]:
        """Return a copy of all propagated headers."""
        return dict(self._headers)

    def get_header(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Return a single header value by name (case-insensitive lookup).

        Parameters
        ----------
        name:
            Header name, e.g. ``"Authorization"`` or ``"X-Correlation-Id"``.
        default:
            Returned when the header is absent.  Defaults to ``None``.
        """
        # All keys are stored lowercase — normalise lookup key
        return self._headers.get(name.lower(), default)

    def __repr__(self) -> str:  # pragma: no cover
        keys = list(self._headers.keys())
        return f"RequestContext(headers={keys})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RequestContext):
            return NotImplemented
        return self._headers == other._headers


# ---------------------------------------------------------------------------
# GraftConfig
# ---------------------------------------------------------------------------


class GraftConfig:
    """
    Client-side configuration class for setting Graftcode request headers.

    This class is used **inside Grafts** (Graftcode client libraries) to
    attach headers to outgoing service calls.  On the server side, the
    Graftcode Gateway sets headers automatically — you don't need to use
    GraftConfig there.

    The class provides two complementary APIs:

    Global headers (``set_headers``)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Set once at application startup; applied to every subsequent Graft call::

        GraftConfig.set_headers({
            "Authorization": "Bearer token123",
            "X-Correlation-Id": "abc-123",
        })

    Per-call headers (``invoke_with_headers`` / ``invoke_with_headers_async``)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Override headers for a single function call.  Other concurrent calls
    are not affected::

        # Synchronous
        result = GraftConfig.invoke_with_headers(
            lambda: MyService.do_something(),
            {"Authorization": "Bearer different-token"},
        )

        # Asynchronous
        result = await GraftConfig.invoke_with_headers_async(
            lambda: MyService.do_something_async(),
            {"Authorization": "Bearer different-token"},
        )

    Header precedence: per-call headers **override** global headers.

    Reference: https://docs.graftcode.com/security-and-trust/graftcode-context
    """

    # ------------------------------------------------------------------
    # Global headers
    # ------------------------------------------------------------------

    @classmethod
    def set_headers(cls, headers: Dict[str, str]) -> None:
        """
        Set process-wide default headers for all Graft invocations.

        Call this once at startup (e.g. after reading a JWT from the
        environment) and the headers will be sent with every outgoing
        Graftcode call for the lifetime of the process.

        Parameters
        ----------
        headers:
            Mapping of header name → value, e.g.::

                {
                    "Authorization": "Bearer <token>",
                    "X-Correlation-Id": "req-abc-123",
                }

        Example
        -------
        ::

            from graftcode_context import GraftConfig

            GraftConfig.set_headers({
                "Authorization": "Bearer token123",
                "X-Correlation-Id": "abc-123",
            })
        """
        with _global_headers_lock:
            _global_headers.update(headers)

    @classmethod
    def get_global_headers(cls) -> Dict[str, str]:
        """Return a snapshot of all currently configured global headers."""
        with _global_headers_lock:
            return dict(_global_headers)

    @classmethod
    def clear_global_headers(cls) -> None:
        """Remove all global headers.  Useful in test teardown."""
        with _global_headers_lock:
            _global_headers.clear()

    # ------------------------------------------------------------------
    # Per-call header override — synchronous
    # ------------------------------------------------------------------

    @classmethod
    def invoke_with_headers(
        cls,
        fn: Callable[[], T],
        headers: Dict[str, str],
    ) -> T:
        """
        Invoke *fn* with the given *headers* merged into the request context.

        The headers are **scoped to this single call** and do not affect other
        concurrent or subsequent invocations.  Per-call headers override any
        global headers set via :meth:`set_headers`.

        Parameters
        ----------
        fn:
            A zero-argument callable (e.g. ``lambda: MyService.do_something()``).
        headers:
            Headers to apply for this call only.

        Returns
        -------
        T
            Whatever *fn* returns.

        Example
        -------
        ::

            result = GraftConfig.invoke_with_headers(
                lambda: MyService.do_something(),
                {"Authorization": "Bearer different-token"},
            )
        """
        merged = cls._merge(headers)
        ctx = RequestContext(merged)
        token = RequestContext._bind(ctx)
        try:
            return fn()
        finally:
            RequestContext._unbind(token)

    # ------------------------------------------------------------------
    # Per-call header override — asynchronous
    # ------------------------------------------------------------------

    @classmethod
    async def invoke_with_headers_async(
        cls,
        fn: Callable[[], Awaitable[T]],
        headers: Dict[str, str],
    ) -> T:
        """
        Async version of :meth:`invoke_with_headers`.

        Invoke the awaitable returned by *fn* with the given *headers* merged
        into the request context.  Safe to use concurrently — each call gets
        its own isolated context via Python's ``contextvars`` mechanism.

        Parameters
        ----------
        fn:
            A zero-argument callable that returns an awaitable
            (e.g. ``lambda: MyService.do_something_async()``).
        headers:
            Headers to apply for this call only.

        Returns
        -------
        T
            Whatever the awaitable resolves to.

        Example
        -------
        ::

            result = await GraftConfig.invoke_with_headers_async(
                lambda: MyService.do_something_async(),
                {"Authorization": "Bearer different-token"},
            )
        """
        merged = cls._merge(headers)
        ctx = RequestContext(merged)
        token = RequestContext._bind(ctx)
        try:
            return await fn()
        finally:
            RequestContext._unbind(token)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @classmethod
    def _merge(cls, override: Dict[str, str]) -> Dict[str, str]:
        """
        Build the effective header dict: global defaults ← current ctx ← override.
        """
        with _global_headers_lock:
            merged = dict(_global_headers)

        # Layer in any existing context headers (supports nested calls)
        current = _request_context_var.get()
        if current is not None:
            merged.update(current.get_headers())

        # Per-call override wins
        merged.update(override)
        return merged
