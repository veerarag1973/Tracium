# tracium.consumer

Consumer registry for tracking which tools and services depend on which schema
namespaces, and enforcing schema-version compatibility at startup.

See the [Governance & Consumer Registry](../user_guide/governance.md) user guide
for usage patterns.

---

## `ConsumerRecord`

```python
@dataclass(frozen=True)
class ConsumerRecord:
    tool_name: str
    namespaces: Tuple[str, ...]
    schema_version: str
    contact: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)
```

An immutable record representing one registered consumer of the schema.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `tool_name` | `str` | The name of the tool or service consuming events. |
| `namespaces` | `Tuple[str, ...]` | Namespaces this consumer reads (e.g. `("llm.trace.*", "llm.cost.*")`). |
| `schema_version` | `str` | The minimum schema version this consumer requires (e.g. `"1.0"`). |
| `contact` | `str` | Optional owner / on-call info. |
| `metadata` | `Dict[str, str]` | Arbitrary extra metadata. |

---

## `ConsumerRegistry`

```python
class ConsumerRegistry
```

Thread-safe registry that tracks all registered `ConsumerRecord` objects.

**Example:**

```python
from tracium.consumer import ConsumerRegistry, ConsumerRecord

registry = ConsumerRegistry()
registry.register(ConsumerRecord(
    tool_name="my-analytics-agent",
    namespaces=("llm.trace.*", "llm.cost.*"),
    schema_version="1.0",
    contact="analytics-team@example.com",
))
```

### Methods

#### `register(record: ConsumerRecord) -> None`

Add a consumer record to the registry.

**Args:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `record` | `ConsumerRecord` | The consumer to register. |

---

#### `all() -> List[ConsumerRecord]`

Return a snapshot of all registered consumers.

**Returns:** `List[ConsumerRecord]`

---

#### `by_namespace(namespace: str) -> List[ConsumerRecord]`

Return all consumers that list `namespace` in their `namespaces` tuple.
Supports exact matches and wildcard patterns (e.g. `"llm.trace.*"`).

**Args:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `namespace` | `str` | Namespace string to look up. |

**Returns:** `List[ConsumerRecord]`

---

#### `by_tool(tool_name: str) -> List[ConsumerRecord]`

Return all records registered under the given `tool_name`.

**Args:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `tool_name` | `str` | Exact tool name string. |

**Returns:** `List[ConsumerRecord]`

---

#### `check_compatible(installed_version: str) -> List[Tuple[str, str]]`

Check every registered consumer against `installed_version`.

A consumer is **compatible** if:
- its major version equals the installed major version, and
- its minor version is ≤ the installed minor version.

**Args:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `installed_version` | `str` | The currently installed schema version (e.g. `"1.1"`). |

**Returns:** `List[Tuple[str, str]]` — list of `(tool_name, schema_version)` tuples for **incompatible** consumers. An empty list means all consumers are satisfied.

---

#### `assert_compatible(installed_version: str) -> None`

Like `check_compatible`, but raises if any consumer is incompatible.

**Args:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `installed_version` | `str` | The currently installed schema version. |

**Raises:** `IncompatibleSchemaError` — if one or more consumers require a version the installation cannot satisfy.

---

#### `clear() -> None`

Remove all registered consumers. Useful in tests.

---

## `IncompatibleSchemaError`

```python
class IncompatibleSchemaError(LLMSchemaError):
    incompatible: List[Tuple[str, str]]
```

Raised by `ConsumerRegistry.assert_compatible()` when one or more registered
consumers require a schema version the installation cannot satisfy.

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `incompatible` | `List[Tuple[str, str]]` | List of `(tool_name, required_version)` pairs that are incompatible. |

---

## Module-level helpers

The module exposes a **global registry** singleton and convenience wrappers
so most callers never need to instantiate `ConsumerRegistry` directly.

### `get_registry() -> ConsumerRegistry`

Return the global `ConsumerRegistry` singleton.

---

### `register_consumer(record: ConsumerRecord) -> None`

Register a consumer in the global registry.

**Args:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `record` | `ConsumerRecord` | Consumer to register. |

---

### `assert_compatible(installed_version: str = tracium.__version__) -> None`

Assert all globally registered consumers are compatible with `installed_version`.

Defaults to the currently installed package version.

**Raises:** `IncompatibleSchemaError` — if any registered consumer is incompatible.

**Example:**

```python
import tracium
from tracium.consumer import register_consumer, assert_compatible, ConsumerRecord

register_consumer(ConsumerRecord(
    tool_name="billing-agent",
    namespaces=("llm.cost.*",),
    schema_version="1.0",
))

# Call at startup — raises IncompatibleSchemaError if your tool requires
# a higher schema version than installed.
assert_compatible()
```
