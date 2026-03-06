"""RFC-0001 export backends for AGENTOBS SDK events.

All exporters are **opt-in** — importing this package does not open any network
connections or file handles.  Instantiate an exporter explicitly to activate it.

Core exporters (RFC-0001 §14)
------------------------------
* :class:`~agentobs.export.otlp.OTLPExporter` — OTLP/JSON HTTP exporter
  (zero dependencies; builds OTLP wire format from stdlib).
* :class:`~agentobs.export.otel_bridge.OTelBridgeExporter` — OTel SDK bridge
  that emits real OTel spans via a configured ``TracerProvider``.
  Requires ``pip install "agentobs[otel]"``.
* :class:`~agentobs.export.webhook.WebhookExporter` — HTTP webhook with
  HMAC-SHA256 request signing.
* :class:`~agentobs.export.jsonl.JSONLExporter` — NDJSON for local development
  and audit trail persistence.
"""

from __future__ import annotations

from agentobs.export.datadog import DatadogExporter, DatadogResourceAttributes
from agentobs.export.grafana import GrafanaLokiExporter
from agentobs.export.jsonl import JSONLExporter
from agentobs.export.otlp import OTLPExporter, ResourceAttributes
from agentobs.export.webhook import WebhookExporter

__all__ = [
    "DatadogExporter",
    "DatadogResourceAttributes",
    "GrafanaLokiExporter",
    "JSONLExporter",
    "OTLPExporter",
    "ResourceAttributes",
    "WebhookExporter",
]
