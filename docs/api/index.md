# API Reference

The tracium API surface is organised by module. All public symbols are
exported at the top-level package under `tracium`.

## Modules

- [event](event.md)
- [types](types.md)
- [signing](signing.md)
- [redact](redact.md)
- [compliance](compliance.md)
- [export](export.md)
- [stream](stream.md)
- [validate](validate.md)
- [migrate](migrate.md)
- [consumer](consumer.md)
- [governance](governance.md)
- [deprecations](deprecations.md)
- [integrations](integrations.md)
- [ulid](ulid.md)
- [exceptions](exceptions.md)
- [models](models.md)

## Module summary

| Module | Responsibility |
|--------|---------------|
| `tracium.event` | `Event` envelope and serialisation |
| `tracium.types` | `EventType` enum, custom type validation |
| `tracium.signing` | HMAC signing, `AuditStream`, chain verification |
| `tracium.redact` | `Redactable`, `RedactionPolicy`, PII helpers |
| `tracium.compliance` | Compatibility checks, isolation, chain integrity, scope verification |
| `tracium.export` | OTLP, Webhook, JSONL, Datadog, and Grafana Loki export backends |
| `tracium.stream` | `EventStream` multiplexer with Kafka support |
| `tracium.validate` | JSON Schema validation helpers |
| `tracium.migrate` | `MigrationResult`, `SunsetPolicy`, `DeprecationRecord`, `v2_migration_roadmap()` |
| `tracium.consumer` | `ConsumerRegistry`, `ConsumerRecord`, `IncompatibleSchemaError` |
| `tracium.governance` | `EventGovernancePolicy`, `GovernanceViolationError`, `GovernanceWarning` |
| `tracium.deprecations` | `DeprecationRegistry`, `DeprecationNotice`, `warn_if_deprecated()` |
| `tracium.integrations` | `LLMSchemaCallbackHandler` (LangChain), `LLMSchemaEventHandler` (LlamaIndex) |
| `tracium.ulid` | ULID generation and helpers |
| `tracium.exceptions` | Package-level exception hierarchy |
| `tracium.models` | Shared Pydantic base models |
