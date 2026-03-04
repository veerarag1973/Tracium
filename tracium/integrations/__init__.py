"""tracium.integrations — Third-party provider and framework integrations.

Each sub-module is an optional extra that sits on top of the zero-dependency
core SDK.  Install the relevant extra before importing:

    pip install "tracium[openai]"      # OpenAI auto-instrumentation
    pip install "tracium[langchain]"   # LangChain callback handler
    pip install "tracium[llamaindex]"  # LlamaIndex event handler

Available integrations
----------------------
* :mod:`tracium.integrations.openai`    — OpenAI chat completions (Phase 6)
* :mod:`tracium.integrations.anthropic` — Anthropic Claude (Phase 7)
* :mod:`tracium.integrations.ollama`    — Ollama local models (Phase 7)
* :mod:`tracium.integrations.groq`      — Groq API (Phase 7)
* :mod:`tracium.integrations.together`  — Together AI (Phase 7)
"""

from __future__ import annotations

__all__: list[str] = [
    "openai",
]
