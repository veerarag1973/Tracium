"""RFC-0001 export backends for AGENTOBS SDK events.

All exporters are **opt-in** — importing this package does not open any network
connections or file handles.  Instantiate an exporter explicitly to activate it.

Core exporters (RFC-0001 §14)
------------------------------
* :class:`~llm_toolkit_schema.export.otlp.OTLPExporter` — OTLP/JSON HTTP exporter
  (zero dependencies; builds OTLP wire format from stdlib).
* :class:`~llm_toolkit_schema.export.otel_bridge.OTelBridgeExporter` — OTel SDK bridge
  that emits real OTel spans via a configured ``TracerProvider``.
  Requires ``pip install "llm-toolkit-schema[otel]"``.
* :class:`~llm_toolkit_schema.export.webhook.WebhookExporter` — HTTP webhook with
  HMAC-SHA256 request signing.
* :class:`~llm_toolkit_schema.export.jsonl.JSONLExporter` — NDJSON for local development
  and audit trail persistence.
"""

from __future__ import annotations

from llm_toolkit_schema.export.jsonl import JSONLExporter
from llm_toolkit_schema.export.otlp import OTLPExporter, ResourceAttributes
from llm_toolkit_schema.export.webhook import WebhookExporter

__all__ = [
    "OTLPExporter",
    "ResourceAttributes",
    "WebhookExporter",
    "JSONLExporter",
]
