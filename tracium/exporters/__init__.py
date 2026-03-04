"""tracium.exporters — Synchronous export backends for the Tracium SDK.

This package provides the sync exporter implementations used by the internal
:mod:`tracium._stream` module.  All exporters expose the same minimal
interface::

    class SomeExporter:
        def export(self, event: Event) -> None: ...
        def flush(self) -> None: ...
        def close(self) -> None: ...

Available exporters
-------------------
* :class:`~tracium.exporters.jsonl.SyncJSONLExporter` — append events as
  newline-delimited JSON to a file.
* :class:`~tracium.exporters.console.SyncConsoleExporter` — pretty-print
  events to stdout during development.

Additional backends (OTLP, Webhook, Datadog, Grafana Loki) are implemented in
later phases; they live in :mod:`tracium.export` (the async-based backends) until
synchronous wrappers are added here.
"""

from __future__ import annotations

from tracium.exporters.console import SyncConsoleExporter
from tracium.exporters.jsonl import SyncJSONLExporter

__all__ = ["SyncConsoleExporter", "SyncJSONLExporter"]
