# Migration Guide

`agentobs.migrate` provides helpers for upgrading stored event payloads
to use new namespace payload schemas, plus the Phase 9 v2 migration roadmap
so you can prepare for breaking changes before v2.0 ships.

## MigrationResult

Every migration function returns a `MigrationResult` dataclass carrying
per-event outcome metadata:

```python
from agentobs.migrate import MigrationResult

result: MigrationResult   # returned by v1_to_v2()
result.source_version     # "1.0"
result.target_version     # "2.0"
result.event_id           # event ULID
result.success            # True / False
result.transformed_fields # tuple of modified field names
result.warnings           # tuple of non-fatal messages
```

## Migrating v1.0 → v2.0 (scaffold)

`v1_to_v2()` is a **scaffold** that raises `NotImplementedError` until the
v2.0 schema is finalised. Write the call-site now to receive the working
implementation in v2.0 with zero code changes:

```python
from agentobs.migrate import v1_to_v2

try:
    new_event, result = v1_to_v2(event)
except NotImplementedError:
    pass  # expected until v2.0 ships
```

## v2 Migration Roadmap

Phase 9 ships a structured roadmap of every event type that will change
in v2.0. Use `v2_migration_roadmap()` to audit your codebase:

```python
from agentobs.migrate import v2_migration_roadmap

for record in v2_migration_roadmap():
    print(record.summary())
```

Example output:

```
llm.cache.evicted → llm.cache.entry_evicted (since 1.1.0, sunset 2.0.0, NEXT_MAJOR)
llm.cost.estimate → llm.cost.estimated (since 1.1.0, sunset 2.0.0, NEXT_MAJOR)
llm.eval.regression → llm.eval.regression_failed (since 1.1.0, sunset 2.0.0, NEXT_MAJOR)
...
```

Each `DeprecationRecord` provides:

| Field | Description |
|-------|-------------|
| `event_type` | The deprecated event type string |
| `since` | Version deprecated (`"1.1.0"`) |
| `sunset` | Planned removal version (`"2.0.0"`) |
| `sunset_policy` | `SunsetPolicy.NEXT_MAJOR` for all roadmap entries |
| `replacement` | Recommended new event type |
| `migration_notes` | Guidance text |
| `field_renames` | `{old_field: new_field}` dict for payload field renames |

### CLI roadmap view

```bash
# Human-readable table
agentobs migration-roadmap

# JSON for tooling
agentobs migration-roadmap --json
```

## Sunset policy

| Policy | Meaning |
|--------|---------|
| `NEXT_MAJOR` | Removed in v2.0.0 |
| `NEXT_MINOR` | Removed in the next minor release |
| `LONG_TERM` | Removed in v3.0.0 or later |
| `UNSCHEDULED` | Advisory deprecation; no removal planned |

All Phase 9 roadmap entries use `NEXT_MAJOR` — they will be removed when v2.0
ships.

## Deprecation warnings

At import time, `agentobs.deprecations` auto-populates the global
`DeprecationRegistry` with every entry from `v2_migration_roadmap()`. Callers
can surface these warnings at runtime:

```python
from agentobs.deprecations import warn_if_deprecated

# Inside event processing loops, or at schema validation time:
warn_if_deprecated(event.event_type)
# → emits DeprecationWarning if this type is on the roadmap
```

### CLI deprecation list

```bash
agentobs list-deprecated
```

## Preparing for v2.0

1. Run `agentobs migration-roadmap` to see the full list.
2. Search your code for deprecated event type strings.
3. Replace with the recommended `replacement` type from each record.
4. Apply any `field_renames` to affected payload construction sites.
5. Update consumer registry entries with `schema_version="2.0"` once v2.0 ships.


## MigrationResult

Every migration function returns a `MigrationResult` dataclass:

```python
@dataclass
class MigrationResult:
    migrated: list[Event]   # successfully transformed events
    skipped:  list[Event]   # events that needed no change
    errors:   list[dict]       # {"event_id": str, "error": str}

@property
def success(self) -> bool:
    return len(self.errors) == 0
```

## Migrating v1 → v2 (scaffold)

The `v1_to_v2` scaffold converts events recorded with the `llm.trace.*`
payload from the frozen v1.0 schema to any updated v2 layout that ships in
Phase 9:

```python
from agentobs.migrate import v1_to_v2

result = v1_to_v2(events)

if result.success:
    save(result.migrated)
else:
    for err in result.errors:
        print(f"{err['event_id']}: {err['error']}")
```

The function is idempotent — events whose `schema_version` is already
`"2.0"` are placed in `result.skipped` unchanged.

## Batch migration from JSONL

Read a JSONL archive, migrate, and write the output:

```python
import json
from agentobs.event import Event
from agentobs.migrate import v1_to_v2

events = [Event(**json.loads(line)) for line in open("archive.jsonl")]
result = v1_to_v2(events)

with open("archive_v2.jsonl", "w") as f:
    for event in result.migrated + result.skipped:
        f.write(json.dumps(event.to_dict()) + "\n")

print(f"Migrated: {len(result.migrated)}")
print(f"Skipped:  {len(result.skipped)}")
print(f"Errors:   {len(result.errors)}")
```

## Phase 9 roadmap

Phase 9 will ship breaking-change namespace payload schemas alongside a
`migrate` sub-command for the CLI:

```bash
agentobs migrate --from v1 --to v2 archive.jsonl --out archive_v2.jsonl
```

Until Phase 9 ships, the `v1_to_v2` Python API is the primary migration path.
The function signature and `MigrationResult` dataclass fields are considered
**stable** and will not change in Phase 9.
