"""agentobs.compliance — RFC-0001 compliance utilities.

Provides three compliance modules:

* :mod:`~agentobs.compliance._compat`        — RFC-0001 schema compatibility checks.
* :mod:`~agentobs.compliance.test_chain`     — HMAC audit-chain integrity verification.
* :mod:`~agentobs.compliance.test_isolation` — Tenant isolation verification.

All public symbols from each submodule are re-exported from this package so
callers can do::

    from agentobs.compliance import (
        test_compatibility,
        verify_chain_integrity,
        verify_tenant_isolation,
        verify_events_scoped,
    )
"""

from __future__ import annotations

from agentobs.compliance._compat import (
    CompatibilityResult,
    CompatibilityViolation,
    test_compatibility,
)
from agentobs.compliance.test_chain import (
    ChainIntegrityResult,
    ChainIntegrityViolation,
    verify_chain_integrity,
)
from agentobs.compliance.test_isolation import (
    IsolationResult,
    IsolationViolation,
    verify_events_scoped,
    verify_tenant_isolation,
)

__all__: list[str] = [
    # test_chain
    "ChainIntegrityResult",
    "ChainIntegrityViolation",
    # _compat
    "CompatibilityResult",
    "CompatibilityViolation",
    # test_isolation
    "IsolationResult",
    "IsolationViolation",
    "test_compatibility",
    "verify_chain_integrity",
    "verify_events_scoped",
    "verify_tenant_isolation",
]
