# llm.redact — Redaction Audit Record

> **Note:** This namespace records *metadata about a redaction operation* —
> for example, which PII categories were detected and which fields were
> affected. It is distinct from the runtime `tracium.redact` module that
> performs the actual field-level redaction.

> **Auto-documented module:** `tracium.namespaces.redact`

The `llm.redact.*` namespace provides payload dataclasses for PII and PHI
detection events and redaction audit records (RFC-0001 §2).

## Payload classes

| Class | Event type | Description |
|-------|-----------|-------------|
| `RedactPiiDetectedPayload` | `llm.redact.pii.detected` | PII was detected in event fields |
| `RedactPhiDetectedPayload` | `llm.redact.phi.detected` | PHI was detected in event fields |
| `RedactAppliedPayload` | `llm.redact.applied` | A redaction policy was applied |

---

## `RedactPiiDetectedPayload` — key fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `detected_categories` | `list[str]` | ✓ | PII category strings detected (e.g. `["email", "phone"]`). Minimum 1. |
| `field_names` | `list[str]` | ✓ | Payload field paths where PII was found. Minimum 1. |
| `sensitivity_level` | `str` | ✓ | Highest level encountered: `"LOW"`, `"MEDIUM"`, `"HIGH"`, `"PII"`, or `"PHI"` |
| `detection_count` | `int \| None` | — | Total number of individual PII instances found |
| `detector` | `str \| None` | — | Detector identifier (e.g. `"presidio-v2"`) |
| `subject_event_id` | `str \| None` | — | ULID of the event containing PII |

---

## Example

```python
from tracium import Event, EventType
from tracium.namespaces.redact import RedactPiiDetectedPayload

payload = RedactPiiDetectedPayload(
    detected_categories=["email", "phone"],
    field_names=["payload.prompt", "payload.completion"],
    sensitivity_level="PII",
    detection_count=3,
    detector="presidio-v2",
)

event = Event(
    event_type=EventType.REDACT_PII_DETECTED,
    source="redactor@1.0.0",
    org_id="org_01HX",
    payload=payload.to_dict(),
)
```
