# tracium.compliance

Programmatic compliance testing: v1.0 compatibility checks, audit chain
integrity verification, and multi-tenant isolation testing.

All compliance functions can be called directly without pytest.

See the [Compliance User Guide](../user_guide/compliance.md) for usage examples.

---

## Compatibility checker

### `CompatibilityViolation`

```python
@dataclass(frozen=True)
class CompatibilityViolation:
    check_id: str
    rule: str
    detail: str
    event_id: str
```

A single compliance non-conformance found during a check.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `check_id` | `str` | Numeric code, e.g. `"CHK-1"`. |
| `rule` | `str` | Short description of the rule violated. |
| `detail` | `str` | Human-readable description of the specific problem. |
| `event_id` | `str` | The `event_id` of the offending event. |

---

### `CompatibilityResult`

```python
@dataclass
class CompatibilityResult:
    passed: bool
    events_checked: int
    violations: List[CompatibilityViolation]
```

Result of a compatibility compliance check across a batch of events.

Evaluates as `True` in a boolean context only when `passed=True`.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `passed` | `bool` | `True` only when zero violations are found. |
| `events_checked` | `int` | Number of events that were inspected. |
| `violations` | `List[CompatibilityViolation]` | Full list of violations. |

---

### `test_compatibility(events: Sequence[Event]) -> CompatibilityResult`

Apply the tracium v1.0 compatibility checklist to `events`.

**Checks performed:**

| Check ID | Rule |
|----------|------|
| CHK-1 | Required fields (`schema_version`, `source`, `payload`) are present and non-empty. |
| CHK-2 | `event_type` uses a registered namespace or valid `x.*` custom prefix. |
| CHK-3 | `source` matches the `<service>@<semver>` pattern. |
| CHK-5 | `event_id` is a valid 26-character ULID. |

**Args:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `events` | `Sequence[Event]` | One or more `Event` instances to inspect. |

**Returns:** `CompatibilityResult`

**Example:**

```python
from tracium.compliance import test_compatibility

result = test_compatibility(my_events)
if not result:
    for v in result.violations:
        print(f"[{v.check_id}] {v.rule}: {v.detail}")
```

---

## Audit chain integrity

### `ChainIntegrityViolation`

A single chain integrity violation (broken `prev_id` link, tampered signature,
or non-monotonic timestamp).

### `ChainIntegrityResult`

Result of `verify_chain_integrity()`. Evaluates as `True` only when no
violations were found.

**Attributes:** `valid`, `events_checked`, `violations`.

---

### `verify_chain_integrity(events: Sequence[Event]) -> ChainIntegrityResult`

Verify the structural integrity of an ordered event chain.

Checks:
- Each event's `prev_id` points to the preceding event's `event_id`.
- Timestamps are monotonically non-decreasing.
- No gaps in the chain.

**Args:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `events` | `Sequence[Event]` | Ordered list of events (oldest first). |

**Returns:** `ChainIntegrityResult`

---

## Multi-tenant isolation

### `IsolationViolation`

A single isolation violation found during tenant boundary checking.

### `IsolationResult`

Result of `verify_tenant_isolation()` or `verify_events_scoped()`. Evaluates
as `True` only when no violations were found.

**Attributes:** `valid`, `events_checked`, `violations`.

---

### `verify_tenant_isolation(tenant_events: Dict[str, Sequence[Event]]) -> IsolationResult`

Verify that events from different tenants do not share `org_id` values.

**Args:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `tenant_events` | `Dict[str, Sequence[Event]]` | Mapping of tenant name → events for that tenant. |

**Returns:** `IsolationResult`

---

### `verify_events_scoped(events: Sequence[Event], *, org_id: str) -> IsolationResult`

Verify that all events in `events` have the expected `org_id`.

Useful for asserting that a batch of events belongs to a single organisation.

**Args:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `events` | `Sequence[Event]` | Events to check. |
| `org_id` | `str` | Expected organisation ID. |

**Returns:** `IsolationResult`
