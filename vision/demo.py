"""
vision/demo.py
~~~~~~~~~~~~~~

Local runner -- exercises all 8 RequestContextDemo methods without Docker.

Usage:
    PYTHONPATH=src python vision/demo.py

All 8 cases are called in sequence and their results printed as JSON.
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from request_context_demo import RequestContextDemo  # noqa: E402

SEP = "=" * 62
demo = RequestContextDemo()

CASES = [
    ("Case 1 -- Health Check + Global Headers",        demo.health_check),
    ("Case 2 -- Auth Demo (success)",                  lambda: demo.auth_demo()),
    ("Case 3 -- Auth Demo (missing token / 401)",      demo.auth_demo_missing_token),
    ("Case 4 -- Correlation ID (auto-generated)",      lambda: demo.correlation_demo()),
    ("Case 4b -- Correlation ID (provided)",           lambda: demo.correlation_demo("req-5f3a-2026")),
    ("Case 5 -- Tenant ID missing (400)",              demo.tenant_demo_missing_id),
    ("Case 6 -- All Headers",                          demo.all_headers),
    ("Case 7 -- Global Headers Demo",                  demo.global_headers_demo),
    ("Case 8 -- Async Isolation Demo",                 demo.async_isolation_demo),
]

print(SEP)
print("  Graftcode Context Demo -- Local Runner")
print(SEP)

for label, fn in CASES:
    print(f"\n[{label}]")
    result = fn()
    print(json.dumps(result, indent=2, default=str))

print()
print(SEP)
print("  All 8 cases completed successfully.")
print("  Run with Docker for Graftcode Vision UI:")
print("    docker-compose -f docker-compose.vision.yml up --build")
print("  Then open: http://localhost:81/GV")
print(SEP)
