# API Reference

The agentobs API surface is organised by module. All public symbols are
exported at the top-level package under `agentobs`.

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
| `agentobs.event` | `Event` envelope and serialisation |
| `agentobs.types` | `EventType` enum, custom type validation |
| `agentobs.signing` | HMAC signing, `AuditStream`, chain verification |
| `agentobs.redact` | `Redactable`, `RedactionPolicy`, PII helpers |
| `agentobs.compliance` | Compatibility checks, isolation, chain integrity, scope verification |
| `agentobs.export` | OTLP, Webhook, JSONL, Datadog, and Grafana Loki export backends |
| `agentobs.stream` | `EventStream` multiplexer with Kafka support |
| `agentobs.validate` | JSON Schema validation helpers |
| `agentobs.migrate` | `MigrationResult`, `SunsetPolicy`, `DeprecationRecord`, `v2_migration_roadmap()` |
| `agentobs.consumer` | `ConsumerRegistry`, `ConsumerRecord`, `IncompatibleSchemaError` |
| `agentobs.governance` | `EventGovernancePolicy`, `GovernanceViolationError`, `GovernanceWarning` |
| `agentobs.deprecations` | `DeprecationRegistry`, `DeprecationNotice`, `warn_if_deprecated()` |
| `agentobs.integrations` | `LLMSchemaCallbackHandler` (LangChain), `LLMSchemaEventHandler` (LlamaIndex) |
| `agentobs.ulid` | ULID generation and helpers |
| `agentobs.exceptions` | Package-level exception hierarchy |
| `agentobs.models` | Shared Pydantic base models |
