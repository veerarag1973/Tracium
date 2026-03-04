"""RFC-0001 export backends for AGENTOBS SDK events.

All exporters are **opt-in** — importing this package does not open any network
connections or file handles.  Instantiate an exporter explicitly to activate it.

Core exporters (RFC-0001 §14)
------------------------------
* :class:`~tracium.export.otlp.OTLPExporter` — OTLP/JSON HTTP exporter
  (zero dependencies; builds OTLP wire format from stdlib).
* :class:`~tracium.export.otel_bridge.OTelBridgeExporter` — OTel SDK bridge
  that emits real OTel spans via a configured ``TracerProvider``.
  Requires ``pip install "agentobs[otel]"``.
* :class:`~tracium.export.webhook.WebhookExporter` — HTTP webhook with
  HMAC-SHA256 request signing.
* :class:`~tracium.export.jsonl.JSONLExporter` — NDJSON for local development
  and audit trail persistence.
"""

from __future__ import annotations

from tracium.export.datadog import DatadogExporter, DatadogResourceAttributes
from tracium.export.grafana import GrafanaLokiExporter
from tracium.export.jsonl import JSONLExporter
from tracium.export.otlp import OTLPExporter, ResourceAttributes
from tracium.export.webhook import WebhookExporter

__all__ = [
    "DatadogExporter",
    "DatadogResourceAttributes",
    "GrafanaLokiExporter",
    "JSONLExporter",
    "OTLPExporter",
    "ResourceAttributes",
    "WebhookExporter",
]
