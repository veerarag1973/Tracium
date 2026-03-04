"""Tests for all namespace payload dataclasses (Phase 5).

Coverage targets
----------------
* Construction with required fields only.
* Construction with all optional fields.
* ``to_dict()`` round-trip.
* ``from_dict()`` round-trip.
* Validation errors for bad/missing required fields.
* Validation errors for out-of-range optional fields.
* Immutability: frozen dataclasses cannot be mutated.
* Default field values.
* Cross-field constraints (e.g. from_version != to_version).
"""

from __future__ import annotations

import pytest

# ============================================================
# trace
# ============================================================
from llm_toolkit_schema.namespaces.trace import (
    ModelInfo,
    SpanCompletedPayload,
    TokenUsage,
    ToolCall,
)

# ============================================================
# diff
# ============================================================
from llm_toolkit_schema.namespaces.diff import DiffComparisonPayload, DiffReportPayload

# ============================================================
# prompt
# ============================================================
from llm_toolkit_schema.namespaces.prompt import (
    PromptApprovedPayload,
    PromptPromotedPayload,
    PromptRejectedPayload,
    PromptRenderedPayload,
    PromptRolledBackPayload,
    PromptSavedPayload,
)

# ============================================================
# inspect
# ============================================================
from llm_toolkit_schema.namespaces.inspect import (
    InspectIssueSummary,
    InspectReportPayload,
)

# ============================================================
# cost
# ============================================================
from llm_toolkit_schema.namespaces.cost import BudgetThresholdPayload, CostRecordedPayload

# ============================================================
# eval_
# ============================================================
from llm_toolkit_schema.namespaces.eval_ import EvalRegressionPayload, EvalScenarioPayload

# ============================================================
# guard
# ============================================================
from llm_toolkit_schema.namespaces.guard import GuardBlockedPayload, GuardFlaggedPayload

# ============================================================
# redact (namespace submodule)
# ============================================================
from llm_toolkit_schema.namespaces.redact import (
    PIIDetectedPayload,
    PIIRedactedPayload,
    ScanCompletedPayload,
)

# ============================================================
# cache
# ============================================================
from llm_toolkit_schema.namespaces.cache import CacheEvictedPayload, CacheHitPayload, CacheMissPayload

# ============================================================
# template
# ============================================================
from llm_toolkit_schema.namespaces.template import (
    TemplateRenderedPayload,
    TemplateValidationFailedPayload,
    VariableMissingPayload,
)

# ============================================================
# fence
# ============================================================
from llm_toolkit_schema.namespaces.fence import (
    FenceValidationFailedPayload,
    RetryTriggeredPayload,
    ValidationPassedPayload,
)

# ============================================================
# Also verify top-level namespace re-exports work
# ============================================================
import llm_toolkit_schema.namespaces as ns_pkg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _round_trip(cls, obj):
    """Serialise and deserialise an object via to_dict / from_dict."""
    return cls.from_dict(obj.to_dict())


# ===========================================================================
# TokenUsage
# ===========================================================================


class TestTokenUsage:
    def test_basic(self):
        tu = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        assert tu.prompt_tokens == 10
        assert tu.completion_tokens == 5
        assert tu.total_tokens == 15

    def test_to_dict(self):
        tu = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        d = tu.to_dict()
        assert d == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    def test_round_trip(self):
        tu = TokenUsage(prompt_tokens=100, completion_tokens=200, total_tokens=300)
        assert _round_trip(TokenUsage, tu) == tu

    def test_negative_prompt_tokens_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            TokenUsage(prompt_tokens=-1, completion_tokens=5, total_tokens=4)

    def test_total_less_than_sum_raises(self):
        with pytest.raises(ValueError, match="total_tokens"):
            TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=5)

    def test_non_int_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            TokenUsage(prompt_tokens=1.5, completion_tokens=1, total_tokens=2)  # type: ignore

    def test_frozen(self):
        tu = TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
        with pytest.raises((AttributeError, TypeError)):
            tu.prompt_tokens = 99  # type: ignore

    def test_total_equal_sum_ok(self):
        # total == prompt + completion is valid
        TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10)

    def test_total_greater_than_sum_ok(self):
        # Provider may include extra tokens; total > sum is allowed
        TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=15)


# ===========================================================================
# ModelInfo
# ===========================================================================


class TestModelInfo:
    def test_required_only(self):
        mi = ModelInfo(name="gpt-4o", provider="openai")
        assert mi.version is None

    def test_with_version(self):
        mi = ModelInfo(name="claude-3", provider="anthropic", version="20240229")
        assert mi.version == "20240229"

    def test_to_dict_no_version(self):
        mi = ModelInfo(name="gpt-4o", provider="openai")
        assert mi.to_dict() == {"name": "gpt-4o", "provider": "openai"}

    def test_to_dict_with_version(self):
        mi = ModelInfo(name="gpt-4o", provider="openai", version="2024")
        d = mi.to_dict()
        assert d["version"] == "2024"

    def test_round_trip(self):
        mi = ModelInfo(name="gpt-4o", provider="openai", version="v1")
        assert _round_trip(ModelInfo, mi) == mi

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="name"):
            ModelInfo(name="", provider="openai")

    def test_empty_provider_raises(self):
        with pytest.raises(ValueError, match="provider"):
            ModelInfo(name="gpt-4o", provider="")

    def test_non_string_version_raises(self):
        with pytest.raises(ValueError, match="version"):
            ModelInfo(name="gpt-4o", provider="openai", version=123)  # type: ignore

    def test_frozen(self):
        mi = ModelInfo(name="gpt-4o", provider="openai")
        with pytest.raises((AttributeError, TypeError)):
            mi.name = "other"  # type: ignore


# ===========================================================================
# ToolCall
# ===========================================================================


class TestToolCall:
    def test_required_only(self):
        tc = ToolCall(tool_name="search", tool_input={"q": "hi"})
        assert tc.status == "completed"
        assert tc.tool_output is None
        assert tc.duration_ms is None

    def test_full(self):
        tc = ToolCall(
            tool_name="search",
            tool_input={"q": "hi"},
            tool_output={"result": "ok"},
            duration_ms=12.5,
            status="completed",
        )
        d = tc.to_dict()
        assert d["tool_output"] == {"result": "ok"}
        assert d["duration_ms"] == 12.5

    def test_to_dict_minimal(self):
        tc = ToolCall(tool_name="search", tool_input={"q": "hi"})
        d = tc.to_dict()
        assert "tool_output" not in d
        assert "duration_ms" not in d

    def test_round_trip(self):
        tc = ToolCall(
            tool_name="search",
            tool_input={"q": "hi"},
            tool_output={"r": "ok"},
            duration_ms=5.0,
            status="error",
        )
        assert _round_trip(ToolCall, tc) == tc

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="status"):
            ToolCall(tool_name="t", tool_input={}, status="unknown")

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="tool_name"):
            ToolCall(tool_name="", tool_input={})

    def test_non_dict_input_raises(self):
        with pytest.raises(ValueError, match="tool_input"):
            ToolCall(tool_name="t", tool_input="bad")  # type: ignore

    def test_negative_duration_raises(self):
        with pytest.raises(ValueError, match="duration_ms"):
            ToolCall(tool_name="t", tool_input={}, duration_ms=-1)

    def test_non_dict_output_raises(self):
        with pytest.raises(ValueError, match="tool_output"):
            ToolCall(tool_name="t", tool_input={}, tool_output="bad")  # type: ignore

    def test_all_statuses(self):
        for status in ("completed", "error", "timeout"):
            tc = ToolCall(tool_name="t", tool_input={}, status=status)
            assert tc.status == status

    def test_frozen(self):
        tc = ToolCall(tool_name="t", tool_input={})
        with pytest.raises((AttributeError, TypeError)):
            tc.tool_name = "x"  # type: ignore


# ===========================================================================
# SpanCompletedPayload
# ===========================================================================


class TestSpanCompletedPayload:
    def _minimal(self):
        return SpanCompletedPayload(span_name="run", status="ok", duration_ms=10.0)

    def test_required_only(self):
        sp = self._minimal()
        assert sp.model is None
        assert sp.token_usage is None
        assert sp.tool_calls is None
        assert sp.error is None
        assert sp.cost_usd is None

    def test_to_dict_minimal(self):
        sp = self._minimal()
        d = sp.to_dict()
        assert d == {"span_name": "run", "status": "ok", "duration_ms": 10.0}

    def test_full(self):
        model = ModelInfo(name="gpt-4o", provider="openai")
        tu = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        tc = ToolCall(tool_name="t", tool_input={})
        sp = SpanCompletedPayload(
            span_name="run",
            status="ok",
            duration_ms=100.0,
            model=model,
            token_usage=tu,
            tool_calls=[tc],
            cost_usd=0.002,
        )
        d = sp.to_dict()
        assert "model" in d
        assert "token_usage" in d
        assert len(d["tool_calls"]) == 1
        assert d["cost_usd"] == 0.002

    def test_round_trip_minimal(self):
        sp = self._minimal()
        assert _round_trip(SpanCompletedPayload, sp) == sp

    def test_round_trip_full(self):
        model = ModelInfo(name="gpt-4o", provider="openai", version="v1")
        tu = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        tc = ToolCall(tool_name="t", tool_input={"q": "x"}, status="error")
        sp = SpanCompletedPayload(
            span_name="run",
            status="error",
            duration_ms=50.0,
            model=model,
            token_usage=tu,
            tool_calls=[tc],
            error="timeout",
            cost_usd=0.001,
        )
        assert _round_trip(SpanCompletedPayload, sp) == sp

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="status"):
            SpanCompletedPayload(span_name="run", status="bad", duration_ms=1.0)

    def test_negative_duration_raises(self):
        with pytest.raises(ValueError, match="duration_ms"):
            SpanCompletedPayload(span_name="run", status="ok", duration_ms=-1.0)

    def test_empty_span_name_raises(self):
        with pytest.raises(ValueError, match="span_name"):
            SpanCompletedPayload(span_name="", status="ok", duration_ms=1.0)

    def test_invalid_model_type_raises(self):
        with pytest.raises(TypeError, match="ModelInfo"):
            SpanCompletedPayload(span_name="r", status="ok", duration_ms=1.0, model={"bad": True})  # type: ignore

    def test_invalid_token_usage_type_raises(self):
        with pytest.raises(TypeError, match="TokenUsage"):
            SpanCompletedPayload(span_name="r", status="ok", duration_ms=1.0, token_usage={"bad": 1})  # type: ignore

    def test_invalid_tool_calls_type_raises(self):
        with pytest.raises(TypeError, match="list"):
            SpanCompletedPayload(span_name="r", status="ok", duration_ms=1.0, tool_calls="bad")  # type: ignore

    def test_invalid_tool_calls_item_raises(self):
        with pytest.raises(TypeError, match="ToolCall"):
            SpanCompletedPayload(span_name="r", status="ok", duration_ms=1.0, tool_calls=[{}])

    def test_negative_cost_raises(self):
        with pytest.raises(ValueError, match="cost_usd"):
            SpanCompletedPayload(span_name="r", status="ok", duration_ms=1.0, cost_usd=-0.1)

    def test_frozen(self):
        sp = self._minimal()
        with pytest.raises((AttributeError, TypeError)):
            sp.span_name = "x"  # type: ignore


# ===========================================================================
# DiffComparisonPayload
# ===========================================================================


class TestDiffComparisonPayload:
    def test_required_only(self):
        p = DiffComparisonPayload(source_id="a", target_id="b", diff_type="text")
        assert p.similarity_score is None

    def test_full(self):
        p = DiffComparisonPayload(
            source_id="a",
            target_id="b",
            diff_type="semantic",
            similarity_score=0.9,
            source_text="hello",
            target_text="world",
            diff_result={"diff": "x"},
        )
        d = p.to_dict()
        assert d["similarity_score"] == 0.9
        assert d["diff_result"] == {"diff": "x"}

    def test_round_trip(self):
        p = DiffComparisonPayload(
            source_id="a", target_id="b", diff_type="text", similarity_score=0.5
        )
        assert _round_trip(DiffComparisonPayload, p) == p

    def test_similarity_out_of_range_raises(self):
        with pytest.raises(ValueError, match="similarity_score"):
            DiffComparisonPayload(source_id="a", target_id="b", diff_type="text", similarity_score=1.5)

    def test_empty_source_raises(self):
        with pytest.raises(ValueError, match="source_id"):
            DiffComparisonPayload(source_id="", target_id="b", diff_type="text")

    def test_frozen(self):
        p = DiffComparisonPayload(source_id="a", target_id="b", diff_type="text")
        with pytest.raises((AttributeError, TypeError)):
            p.source_id = "x"  # type: ignore


class TestDiffReportPayload:
    def test_required_only(self):
        p = DiffReportPayload(report_id="r1", comparison_event_id="evt", format="html")
        assert p.export_path is None
        assert p.export_url is None

    def test_full(self):
        p = DiffReportPayload(
            report_id="r1",
            comparison_event_id="evt",
            format="markdown",
            export_path="/tmp/report.md",
            export_url="https://example.com/r1",
        )
        d = p.to_dict()
        assert d["export_path"] == "/tmp/report.md"

    def test_round_trip(self):
        p = DiffReportPayload(report_id="r1", comparison_event_id="evt", format="json")
        assert _round_trip(DiffReportPayload, p) == p

    def test_empty_report_id_raises(self):
        with pytest.raises(ValueError, match="report_id"):
            DiffReportPayload(report_id="", comparison_event_id="evt", format="html")


# ===========================================================================
# PromptSavedPayload
# ===========================================================================


class TestPromptSavedPayload:
    def test_required_only(self):
        p = PromptSavedPayload(
            prompt_id="p1",
            version="1.0.0",
            environment="production",
            template_hash="abc",
        )
        assert p.author is None
        assert p.tags is None

    def test_with_tags(self):
        p = PromptSavedPayload(
            prompt_id="p1",
            version="1.0.0",
            environment="staging",
            template_hash="abc",
            author="alice",
            tags=["summarise", "v2"],
        )
        d = p.to_dict()
        assert d["tags"] == ["summarise", "v2"]

    def test_round_trip(self):
        p = PromptSavedPayload(
            prompt_id="p1",
            version="1.0.0",
            environment="dev",
            template_hash="abc",
            tags=["a"],
        )
        assert _round_trip(PromptSavedPayload, p) == p

    def test_invalid_tag_type_raises(self):
        with pytest.raises(TypeError, match="tag"):
            PromptSavedPayload(
                prompt_id="p1",
                version="1.0.0",
                environment="dev",
                template_hash="abc",
                tags=[123],  # type: ignore
            )

    def test_non_list_tags_raises(self):
        with pytest.raises(TypeError, match="tags"):
            PromptSavedPayload(
                prompt_id="p1",
                version="1.0.0",
                environment="dev",
                template_hash="abc",
                tags="not-a-list",  # type: ignore
            )


class TestPromptPromotedPayload:
    def test_basic(self):
        p = PromptPromotedPayload(
            prompt_id="p1",
            version="1.0.0",
            from_environment="staging",
            to_environment="production",
        )
        assert p.promoted_by is None

    def test_same_env_raises(self):
        with pytest.raises(ValueError, match="differ"):
            PromptPromotedPayload(
                prompt_id="p1",
                version="1.0.0",
                from_environment="staging",
                to_environment="staging",
            )

    def test_round_trip(self):
        p = PromptPromotedPayload(
            prompt_id="p1",
            version="1.0",
            from_environment="staging",
            to_environment="production",
            promoted_by="bot",
        )
        assert _round_trip(PromptPromotedPayload, p) == p


class TestPromptApprovedPayload:
    def test_basic(self):
        p = PromptApprovedPayload(prompt_id="p1", version="1.0", approved_by="alice")
        assert p.approval_note is None

    def test_with_note(self):
        p = PromptApprovedPayload(
            prompt_id="p1", version="1.0", approved_by="alice", approval_note="LGTM"
        )
        d = p.to_dict()
        assert d["approval_note"] == "LGTM"

    def test_round_trip(self):
        p = PromptApprovedPayload(
            prompt_id="p1", version="1.0", approved_by="alice", approval_note="ok"
        )
        assert _round_trip(PromptApprovedPayload, p) == p

    def test_empty_approved_by_raises(self):
        with pytest.raises(ValueError, match="approved_by"):
            PromptApprovedPayload(prompt_id="p1", version="1.0", approved_by="")


class TestPromptRolledBackPayload:
    def test_basic(self):
        p = PromptRolledBackPayload(prompt_id="p1", from_version="2.0", to_version="1.0")
        assert p.reason is None

    def test_same_version_raises(self):
        with pytest.raises(ValueError, match="differ"):
            PromptRolledBackPayload(prompt_id="p1", from_version="1.0", to_version="1.0")

    def test_round_trip(self):
        p = PromptRolledBackPayload(
            prompt_id="p1", from_version="2.0", to_version="1.0", reason="bug"
        )
        assert _round_trip(PromptRolledBackPayload, p) == p


# ===========================================================================
# CostRecordedPayload
# ===========================================================================


class TestCostRecordedPayload:
    def _make(self, **kw):
        defaults = dict(
            span_event_id="evt1",
            model_name="gpt-4o",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.003,
        )
        defaults.update(kw)
        return CostRecordedPayload(**defaults)

    def test_required_only(self):
        p = self._make()
        assert p.currency == "USD"
        assert p.budget_id is None

    def test_custom_currency(self):
        p = self._make(currency="EUR")
        assert p.currency == "EUR"

    def test_to_dict(self):
        p = self._make()
        d = p.to_dict()
        assert d["currency"] == "USD"
        assert "budget_id" not in d

    def test_round_trip(self):
        p = self._make(budget_id="bgt-1")
        assert _round_trip(CostRecordedPayload, p) == p

    def test_negative_tokens_raise(self):
        with pytest.raises(ValueError, match="non-negative"):
            self._make(prompt_tokens=-1)

    def test_negative_cost_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            self._make(cost_usd=-0.01)


class TestBudgetThresholdPayload:
    def _make(self, **kw):
        defaults = dict(
            budget_id="bgt-1",
            threshold_type="warning",
            threshold_usd=100.0,
            current_spend_usd=85.0,
            percentage_used=85.0,
        )
        defaults.update(kw)
        return BudgetThresholdPayload(**defaults)

    def test_required_only(self):
        p = self._make()
        assert p.org_id is None

    def test_invalid_threshold_type_raises(self):
        with pytest.raises(ValueError, match="threshold_type"):
            self._make(threshold_type="unknown")

    def test_negative_threshold_raises(self):
        with pytest.raises(ValueError, match="threshold_usd"):
            self._make(threshold_usd=-1.0)

    def test_round_trip(self):
        p = self._make(org_id="org-1")
        assert _round_trip(BudgetThresholdPayload, p) == p

    def test_all_threshold_types(self):
        for t in ("warning", "critical", "hard_limit"):
            BudgetThresholdPayload(
                budget_id="b", threshold_type=t, threshold_usd=1.0,
                current_spend_usd=0.5, percentage_used=50.0
            )


# ===========================================================================
# EvalScenarioPayload
# ===========================================================================


class TestEvalScenarioPayload:
    def test_required_only(self):
        p = EvalScenarioPayload(scenario_id="s1", scenario_name="test", status="passed")
        assert p.score is None
        assert p.metrics is None

    def test_full(self):
        p = EvalScenarioPayload(
            scenario_id="s1",
            scenario_name="test",
            status="failed",
            score=0.75,
            metrics={"rouge": 0.75},
            baseline_score=0.8,
            duration_ms=200.0,
        )
        d = p.to_dict()
        assert d["metrics"] == {"rouge": 0.75}

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="status"):
            EvalScenarioPayload(scenario_id="s1", scenario_name="t", status="running")

    def test_invalid_metrics_raises(self):
        with pytest.raises(TypeError, match="metrics"):
            EvalScenarioPayload(
                scenario_id="s1",
                scenario_name="t",
                status="passed",
                metrics="bad",  # type: ignore
            )

    def test_metrics_wrong_value_type_raises(self):
        with pytest.raises(TypeError, match="metrics"):
            EvalScenarioPayload(
                scenario_id="s1",
                scenario_name="t",
                status="passed",
                metrics={"x": "bad"},  # type: ignore
            )

    def test_round_trip(self):
        p = EvalScenarioPayload(
            scenario_id="s1",
            scenario_name="test",
            status="skipped",
            metrics={"bleu": 0.5},
        )
        assert _round_trip(EvalScenarioPayload, p) == p


class TestEvalRegressionPayload:
    def _make(self, **kw):
        defaults = dict(
            scenario_id="s1",
            scenario_name="test",
            current_score=0.7,
            baseline_score=0.8,
            regression_delta=-0.1,
            threshold=-0.05,
        )
        defaults.update(kw)
        return EvalRegressionPayload(**defaults)

    def test_basic(self):
        p = self._make()
        assert p.metrics is None

    def test_round_trip(self):
        p = self._make(metrics={"rouge": 0.7})
        assert _round_trip(EvalRegressionPayload, p) == p

    def test_empty_scenario_id_raises(self):
        with pytest.raises(ValueError, match="scenario_id"):
            self._make(scenario_id="")


# ===========================================================================
# GuardBlockedPayload
# ===========================================================================


class TestGuardBlockedPayload:
    def test_required_only(self):
        p = GuardBlockedPayload(
            policy_id="pol-1",
            policy_name="jailbreak",
            input_hash="abc123",
            violation_types=["prompt_injection"],
        )
        assert p.action == "blocked"
        assert p.severity == "high"

    def test_invalid_severity_raises(self):
        with pytest.raises(ValueError, match="severity"):
            GuardBlockedPayload(
                policy_id="p",
                policy_name="n",
                input_hash="h",
                violation_types=["x"],
                severity="extreme",
            )

    def test_empty_violation_types_raises(self):
        with pytest.raises(ValueError, match="violation_types"):
            GuardBlockedPayload(
                policy_id="p", policy_name="n", input_hash="h", violation_types=[]
            )

    def test_round_trip(self):
        p = GuardBlockedPayload(
            policy_id="p",
            policy_name="n",
            input_hash="h",
            violation_types=["jailbreak"],
            severity="critical",
        )
        assert _round_trip(GuardBlockedPayload, p) == p

    def test_all_severities(self):
        for sev in ("low", "medium", "high", "critical"):
            GuardBlockedPayload(
                policy_id="p",
                policy_name="n",
                input_hash="h",
                violation_types=["x"],
                severity=sev,
            )


class TestGuardFlaggedPayload:
    def test_required_only(self):
        p = GuardFlaggedPayload(
            policy_id="pol-1",
            policy_name="pii_detection",
            output_hash="xyz",
            flag_types=["email_leak"],
        )
        assert p.action == "flagged"
        assert p.severity == "medium"

    def test_round_trip(self):
        p = GuardFlaggedPayload(
            policy_id="p",
            policy_name="n",
            output_hash="h",
            flag_types=["x", "y"],
        )
        assert _round_trip(GuardFlaggedPayload, p) == p

    def test_empty_flag_types_raises(self):
        with pytest.raises(ValueError, match="flag_types"):
            GuardFlaggedPayload(
                policy_id="p", policy_name="n", output_hash="h", flag_types=[]
            )


# ===========================================================================
# PIIDetectedPayload
# ===========================================================================


class TestPIIDetectedPayload:
    def test_required_only(self):
        p = PIIDetectedPayload(
            field_path="payload.author",
            pii_types=["email"],
            confidence=0.95,
        )
        assert p.redacted is False

    def test_confidence_out_of_range_raises(self):
        with pytest.raises(ValueError, match="confidence"):
            PIIDetectedPayload(field_path="f", pii_types=["email"], confidence=1.5)

    def test_empty_pii_types_raises(self):
        with pytest.raises(ValueError, match="pii_types"):
            PIIDetectedPayload(field_path="f", pii_types=[], confidence=0.9)

    def test_non_bool_redacted_raises(self):
        with pytest.raises(TypeError, match="redacted"):
            PIIDetectedPayload(field_path="f", pii_types=["x"], confidence=0.9, redacted="yes")  # type: ignore

    def test_round_trip(self):
        p = PIIDetectedPayload(field_path="f", pii_types=["email", "phone"], confidence=0.8, redacted=True)
        assert _round_trip(PIIDetectedPayload, p) == p


class TestPIIRedactedPayload:
    def test_required_only(self):
        p = PIIRedactedPayload(field_path="f", pii_types=["email"], method="mask")
        assert p.redacted_by is None

    def test_round_trip(self):
        p = PIIRedactedPayload(
            field_path="f", pii_types=["email"], method="hash", redacted_by="policy:corp"
        )
        assert _round_trip(PIIRedactedPayload, p) == p

    def test_empty_method_raises(self):
        with pytest.raises(ValueError, match="method"):
            PIIRedactedPayload(field_path="f", pii_types=["x"], method="")


class TestScanCompletedPayload:
    def test_required_only(self):
        p = ScanCompletedPayload(scanned_fields=10, pii_detected_count=3, pii_redacted_count=3)
        assert p.duration_ms is None
        assert p.policy_id is None

    def test_redacted_exceeds_detected_raises(self):
        with pytest.raises(ValueError, match="pii_redacted_count"):
            ScanCompletedPayload(scanned_fields=10, pii_detected_count=2, pii_redacted_count=5)

    def test_detected_exceeds_scanned_raises(self):
        with pytest.raises(ValueError, match="pii_detected_count"):
            ScanCompletedPayload(scanned_fields=3, pii_detected_count=5, pii_redacted_count=2)

    def test_round_trip(self):
        p = ScanCompletedPayload(
            scanned_fields=20, pii_detected_count=4, pii_redacted_count=4,
            duration_ms=10.0, policy_id="pol-1"
        )
        assert _round_trip(ScanCompletedPayload, p) == p

    def test_negative_scanned_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            ScanCompletedPayload(scanned_fields=-1, pii_detected_count=0, pii_redacted_count=0)


# ===========================================================================
# CacheHitPayload
# ===========================================================================


class TestCacheHitPayload:
    def test_required_only(self):
        p = CacheHitPayload(cache_key_hash="abc", cache_store="redis")
        assert p.similarity_score is None
        assert p.cached_event_id is None
        assert p.ttl_seconds is None

    def test_full(self):
        p = CacheHitPayload(
            cache_key_hash="abc",
            cache_store="redis",
            similarity_score=0.97,
            cached_event_id="EVT123",
            ttl_seconds=300,
        )
        d = p.to_dict()
        assert d["ttl_seconds"] == 300

    def test_similarity_out_of_range_raises(self):
        with pytest.raises(ValueError, match="similarity_score"):
            CacheHitPayload(cache_key_hash="a", cache_store="r", similarity_score=-0.1)

    def test_negative_ttl_raises(self):
        with pytest.raises(ValueError, match="ttl_seconds"):
            CacheHitPayload(cache_key_hash="a", cache_store="r", ttl_seconds=-1)

    def test_round_trip(self):
        p = CacheHitPayload(
            cache_key_hash="abc", cache_store="redis", similarity_score=1.0, ttl_seconds=60
        )
        assert _round_trip(CacheHitPayload, p) == p


class TestCacheMissPayload:
    def test_required_only(self):
        p = CacheMissPayload(cache_key_hash="abc", cache_store="redis")
        assert p.reason is None

    def test_with_reason(self):
        p = CacheMissPayload(cache_key_hash="abc", cache_store="redis", reason="expired")
        d = p.to_dict()
        assert d["reason"] == "expired"

    def test_round_trip(self):
        p = CacheMissPayload(cache_key_hash="abc", cache_store="redis", reason="key_not_found")
        assert _round_trip(CacheMissPayload, p) == p

    def test_empty_key_raises(self):
        with pytest.raises(ValueError, match="cache_key_hash"):
            CacheMissPayload(cache_key_hash="", cache_store="redis")


class TestCacheEvictedPayload:
    def test_required_only(self):
        p = CacheEvictedPayload(cache_key_hash="abc", cache_store="redis", reason="ttl_expired")
        assert p.evicted_count == 1

    def test_multiple_evictions(self):
        p = CacheEvictedPayload(
            cache_key_hash="abc", cache_store="redis", reason="capacity", evicted_count=50
        )
        d = p.to_dict()
        assert d["evicted_count"] == 50

    def test_zero_evicted_raises(self):
        with pytest.raises(ValueError, match="evicted_count"):
            CacheEvictedPayload(cache_key_hash="a", cache_store="r", reason="x", evicted_count=0)

    def test_round_trip(self):
        p = CacheEvictedPayload(
            cache_key_hash="abc", cache_store="redis", reason="lru", evicted_count=5
        )
        assert _round_trip(CacheEvictedPayload, p) == p

    def test_empty_reason_raises(self):
        with pytest.raises(ValueError, match="reason"):
            CacheEvictedPayload(cache_key_hash="a", cache_store="r", reason="")


# ===========================================================================
# TemplateRenderedPayload
# ===========================================================================


class TestTemplateRenderedPayload:
    def test_required_only(self):
        p = TemplateRenderedPayload(
            template_id="t1", template_version="1.0", variable_count=3
        )
        assert p.render_duration_ms is None
        assert p.output_length is None

    def test_full(self):
        p = TemplateRenderedPayload(
            template_id="t1",
            template_version="1.0",
            variable_count=3,
            render_duration_ms=5.5,
            output_length=200,
        )
        d = p.to_dict()
        assert d["render_duration_ms"] == 5.5
        assert d["output_length"] == 200

    def test_negative_variable_count_raises(self):
        with pytest.raises(ValueError, match="variable_count"):
            TemplateRenderedPayload(template_id="t1", template_version="1.0", variable_count=-1)

    def test_round_trip(self):
        p = TemplateRenderedPayload(
            template_id="t1", template_version="2.0", variable_count=0,
            render_duration_ms=1.0, output_length=50,
        )
        assert _round_trip(TemplateRenderedPayload, p) == p


class TestVariableMissingPayload:
    def test_basic(self):
        p = VariableMissingPayload(
            template_id="t1",
            missing_variables=["user_name"],
            required_variables=["user_name", "greeting"],
        )
        d = p.to_dict()
        assert d["missing_variables"] == ["user_name"]

    def test_extra_missing_raises(self):
        with pytest.raises(ValueError, match="missing_variables"):
            VariableMissingPayload(
                template_id="t1",
                missing_variables=["unknown_var"],
                required_variables=["greeting"],
            )

    def test_empty_missing_raises(self):
        with pytest.raises(ValueError, match="missing_variables"):
            VariableMissingPayload(
                template_id="t1",
                missing_variables=[],
                required_variables=["x"],
            )

    def test_round_trip(self):
        p = VariableMissingPayload(
            template_id="t1",
            missing_variables=["a"],
            required_variables=["a", "b"],
        )
        assert _round_trip(VariableMissingPayload, p) == p

    def test_non_string_variable_raises(self):
        with pytest.raises(TypeError, match="string"):
            VariableMissingPayload(
                template_id="t1",
                missing_variables=[123],  # type: ignore
                required_variables=["a"],
            )


class TestTemplateValidationFailedPayload:
    def test_basic(self):
        p = TemplateValidationFailedPayload(
            template_id="t1",
            validation_errors=["undefined variable: %name%"],
        )
        assert p.validator is None

    def test_with_validator(self):
        p = TemplateValidationFailedPayload(
            template_id="t1",
            validation_errors=["err"],
            validator="jinja2-strict",
        )
        d = p.to_dict()
        assert d["validator"] == "jinja2-strict"

    def test_empty_errors_raises(self):
        with pytest.raises(ValueError, match="validation_errors"):
            TemplateValidationFailedPayload(template_id="t1", validation_errors=[])

    def test_round_trip(self):
        p = TemplateValidationFailedPayload(
            template_id="t1",
            validation_errors=["err1", "err2"],
            validator="v1",
        )
        assert _round_trip(TemplateValidationFailedPayload, p) == p


# ===========================================================================
# ValidationPassedPayload
# ===========================================================================


class TestValidationPassedPayload:
    def test_required_only(self):
        p = ValidationPassedPayload(validator_id="v1", format_type="json")
        assert p.attempt == 1
        assert p.duration_ms is None

    def test_full(self):
        p = ValidationPassedPayload(
            validator_id="v1", format_type="json", attempt=2, duration_ms=3.5
        )
        d = p.to_dict()
        assert d["attempt"] == 2
        assert d["duration_ms"] == 3.5

    def test_zero_attempt_raises(self):
        with pytest.raises(ValueError, match="attempt"):
            ValidationPassedPayload(validator_id="v1", format_type="json", attempt=0)

    def test_round_trip(self):
        p = ValidationPassedPayload(
            validator_id="v1", format_type="yaml", attempt=3, duration_ms=1.0
        )
        assert _round_trip(ValidationPassedPayload, p) == p


class TestFenceValidationFailedPayload:
    def test_required_only(self):
        p = FenceValidationFailedPayload(
            validator_id="v1", format_type="json", errors=["missing key"]
        )
        assert p.attempt == 1
        assert p.retryable is True

    def test_not_retryable(self):
        p = FenceValidationFailedPayload(
            validator_id="v1", format_type="json", errors=["e"], retryable=False
        )
        d = p.to_dict()
        assert d["retryable"] is False

    def test_empty_errors_raises(self):
        with pytest.raises(ValueError, match="errors"):
            FenceValidationFailedPayload(validator_id="v1", format_type="json", errors=[])

    def test_round_trip(self):
        p = FenceValidationFailedPayload(
            validator_id="v1",
            format_type="json",
            errors=["err1", "err2"],
            attempt=2,
            retryable=False,
        )
        assert _round_trip(FenceValidationFailedPayload, p) == p


class TestRetryTriggeredPayload:
    def test_required_only(self):
        p = RetryTriggeredPayload(validator_id="v1", attempt=2, max_attempts=3)
        assert p.strategy == "regenerate"
        assert p.previous_error is None

    def test_attempt_exceeds_max_raises(self):
        with pytest.raises(ValueError, match="max_attempts"):
            RetryTriggeredPayload(validator_id="v1", attempt=5, max_attempts=3)

    def test_invalid_strategy_raises(self):
        with pytest.raises(ValueError, match="strategy"):
            RetryTriggeredPayload(validator_id="v1", attempt=2, max_attempts=3, strategy="unknown")

    def test_all_strategies(self):
        for s in ("regenerate", "repair", "fallback"):
            RetryTriggeredPayload(validator_id="v1", attempt=1, max_attempts=3, strategy=s)

    def test_round_trip(self):
        p = RetryTriggeredPayload(
            validator_id="v1",
            attempt=2,
            max_attempts=3,
            previous_error="invalid json",
            strategy="repair",
        )
        assert _round_trip(RetryTriggeredPayload, p) == p

    def test_zero_attempt_raises(self):
        with pytest.raises(ValueError, match="attempt"):
            RetryTriggeredPayload(validator_id="v1", attempt=0, max_attempts=3)


# ===========================================================================
# namespace package re-exports
# ===========================================================================


class TestNamespacePackageReexports:
    """Ensure all 29 payload classes are accessible from llm_toolkit_schema.namespaces."""

    _CLASSES = [
        "CacheHitPayload",
        "CacheMissPayload",
        "CacheEvictedPayload",
        "CostRecordedPayload",
        "BudgetThresholdPayload",
        "DiffComparisonPayload",
        "DiffReportPayload",
        "EvalScenarioPayload",
        "EvalRegressionPayload",
        "ValidationPassedPayload",
        "FenceValidationFailedPayload",
        "RetryTriggeredPayload",
        "GuardBlockedPayload",
        "GuardFlaggedPayload",
        "PromptSavedPayload",
        "PromptPromotedPayload",
        "PromptApprovedPayload",
        "PromptRolledBackPayload",
        "PromptRejectedPayload",
        "PromptRenderedPayload",
        "InspectIssueSummary",
        "InspectReportPayload",
        "PIIDetectedPayload",
        "PIIRedactedPayload",
        "ScanCompletedPayload",
        "TemplateRenderedPayload",
        "VariableMissingPayload",
        "TemplateValidationFailedPayload",
        "TokenUsage",
        "ModelInfo",
        "ToolCall",
        "SpanCompletedPayload",
    ]

    def test_all_classes_accessible(self):
        for name in self._CLASSES:
            assert hasattr(ns_pkg, name), f"llm_toolkit_schema.namespaces is missing {name}"

    def test_all_in_all(self):
        for name in self._CLASSES:
            assert name in ns_pkg.__all__, f"{name} not in llm_toolkit_schema.namespaces.__all__"


# ===========================================================================
# PromptRejectedPayload
# ===========================================================================


class TestPromptRejectedPayload:
    def test_basic(self):
        p = PromptRejectedPayload(
            prompt_id="p1",
            version="2.0",
            rejected_by="bob",
            rejection_reason="Output quality degraded by 40% vs baseline.",
        )
        assert p.prompt_id == "p1"
        assert p.rejection_reason == "Output quality degraded by 40% vs baseline."

    def test_to_dict(self):
        p = PromptRejectedPayload(
            prompt_id="p1", version="2.0", rejected_by="bob", rejection_reason="Too verbose."
        )
        d = p.to_dict()
        assert d == {
            "prompt_id": "p1",
            "version": "2.0",
            "rejected_by": "bob",
            "rejection_reason": "Too verbose.",
        }

    def test_round_trip(self):
        p = PromptRejectedPayload(
            prompt_id="p1", version="2.0", rejected_by="bob", rejection_reason="Quality drop."
        )
        assert _round_trip(PromptRejectedPayload, p) == p

    def test_empty_rejection_reason_raises(self):
        with pytest.raises(ValueError, match="rejection_reason"):
            PromptRejectedPayload(
                prompt_id="p1", version="2.0", rejected_by="bob", rejection_reason=""
            )

    def test_empty_rejected_by_raises(self):
        with pytest.raises(ValueError, match="rejected_by"):
            PromptRejectedPayload(
                prompt_id="p1", version="2.0", rejected_by="", rejection_reason="Bad output."
            )

    def test_frozen(self):
        p = PromptRejectedPayload(
            prompt_id="p1", version="2.0", rejected_by="bob", rejection_reason="Bad."
        )
        with pytest.raises((AttributeError, TypeError)):
            p.rejected_by = "alice"  # type: ignore


# ===========================================================================
# PromptRenderedPayload
# ===========================================================================


class TestPromptRenderedPayload:
    def test_required_only(self):
        p = PromptRenderedPayload(
            prompt_id="p1", version="1.0", environment="production", variable_count=3
        )
        assert p.render_duration_ms is None
        assert p.output_hash is None

    def test_with_all_optional(self):
        p = PromptRenderedPayload(
            prompt_id="p1",
            version="1.0",
            environment="staging",
            variable_count=2,
            render_duration_ms=12.5,
            output_hash="abc123",
        )
        d = p.to_dict()
        assert d["render_duration_ms"] == 12.5
        assert d["output_hash"] == "abc123"

    def test_round_trip(self):
        p = PromptRenderedPayload(
            prompt_id="p1",
            version="1.0",
            environment="production",
            variable_count=5,
            render_duration_ms=8.0,
            output_hash="sha256:deadbeef",
        )
        assert _round_trip(PromptRenderedPayload, p) == p

    def test_optional_fields_absent_from_dict(self):
        p = PromptRenderedPayload(
            prompt_id="p1", version="1.0", environment="development", variable_count=0
        )
        d = p.to_dict()
        assert "render_duration_ms" not in d
        assert "output_hash" not in d

    def test_negative_variable_count_raises(self):
        with pytest.raises(ValueError, match="variable_count"):
            PromptRenderedPayload(
                prompt_id="p1", version="1.0", environment="dev", variable_count=-1
            )

    def test_negative_render_duration_raises(self):
        with pytest.raises(ValueError, match="render_duration_ms"):
            PromptRenderedPayload(
                prompt_id="p1",
                version="1.0",
                environment="dev",
                variable_count=0,
                render_duration_ms=-5.0,
            )

    def test_non_string_output_hash_raises(self):
        with pytest.raises(TypeError, match="output_hash"):
            PromptRenderedPayload(
                prompt_id="p1",
                version="1.0",
                environment="dev",
                variable_count=0,
                output_hash=123,  # type: ignore
            )

    def test_frozen(self):
        p = PromptRenderedPayload(
            prompt_id="p1", version="1.0", environment="dev", variable_count=0
        )
        with pytest.raises((AttributeError, TypeError)):
            p.variable_count = 99  # type: ignore


# ===========================================================================
# InspectIssueSummary
# ===========================================================================


class TestInspectIssueSummary:
    def test_basic(self):
        issue = InspectIssueSummary(
            issue_type="hallucination", severity="high", description="Model cited a fake source."
        )
        assert issue.issue_type == "hallucination"
        assert issue.severity == "high"

    def test_to_dict(self):
        issue = InspectIssueSummary(
            issue_type="off_topic", severity="low", description="Response drifted from task."
        )
        d = issue.to_dict()
        assert d == {
            "issue_type": "off_topic",
            "severity": "low",
            "description": "Response drifted from task.",
        }

    def test_round_trip(self):
        issue = InspectIssueSummary(
            issue_type="policy_violation",
            severity="critical",
            description="Contains PII.",
        )
        assert _round_trip(InspectIssueSummary, issue) == issue

    def test_invalid_severity_raises(self):
        with pytest.raises(ValueError, match="severity"):
            InspectIssueSummary(issue_type="x", severity="extreme", description="desc")

    def test_empty_issue_type_raises(self):
        with pytest.raises(ValueError, match="issue_type"):
            InspectIssueSummary(issue_type="", severity="low", description="desc")

    def test_all_valid_severities(self):
        for sev in ("low", "medium", "high", "critical"):
            InspectIssueSummary(issue_type="x", severity=sev, description="d")

    def test_frozen(self):
        issue = InspectIssueSummary(issue_type="x", severity="low", description="d")
        with pytest.raises((AttributeError, TypeError)):
            issue.severity = "high"  # type: ignore


# ===========================================================================
# InspectReportPayload
# ===========================================================================


class TestInspectReportPayload:
    def _make_issue(self, sev: str = "medium") -> InspectIssueSummary:
        return InspectIssueSummary(issue_type="hallucination", severity=sev, description="Fake.")

    def test_clean_report(self):
        p = InspectReportPayload(
            report_id="r1",
            span_id="s1",
            model="gpt-4o",
            issues=[],
            overall_severity="none",
        )
        assert p.score is None
        assert p.inspector_version is None
        assert p.issues == []

    def test_with_issues(self):
        p = InspectReportPayload(
            report_id="r1",
            span_id="s1",
            model="gpt-4o",
            issues=[self._make_issue("high"), self._make_issue("low")],
            overall_severity="high",
            score=0.4,
            inspector_version="0.9.1",
        )
        assert len(p.issues) == 2
        assert p.score == 0.4

    def test_to_dict_no_optionals(self):
        p = InspectReportPayload(
            report_id="r1",
            span_id="s1",
            model="gpt-4o",
            issues=[],
            overall_severity="none",
        )
        d = p.to_dict()
        assert "score" not in d
        assert "inspector_version" not in d
        assert d["issues"] == []

    def test_to_dict_with_issues(self):
        issue = self._make_issue("medium")
        p = InspectReportPayload(
            report_id="r1",
            span_id="s1",
            model="gpt-4o",
            issues=[issue],
            overall_severity="medium",
            score=0.7,
        )
        d = p.to_dict()
        assert len(d["issues"]) == 1
        assert d["issues"][0]["issue_type"] == "hallucination"
        assert d["score"] == 0.7

    def test_round_trip(self):
        p = InspectReportPayload(
            report_id="r1",
            span_id="s1",
            model="claude-3-opus",
            issues=[self._make_issue()],
            overall_severity="medium",
            score=0.6,
            inspector_version="1.0.0",
        )
        assert _round_trip(InspectReportPayload, p) == p

    def test_invalid_overall_severity_raises(self):
        with pytest.raises(ValueError, match="overall_severity"):
            InspectReportPayload(
                report_id="r1",
                span_id="s1",
                model="gpt-4o",
                issues=[],
                overall_severity="extreme",
            )

    def test_score_out_of_range_raises(self):
        with pytest.raises(ValueError, match="score"):
            InspectReportPayload(
                report_id="r1",
                span_id="s1",
                model="gpt-4o",
                issues=[],
                overall_severity="none",
                score=1.5,
            )

    def test_score_zero_ok(self):
        InspectReportPayload(
            report_id="r1",
            span_id="s1",
            model="gpt-4o",
            issues=[],
            overall_severity="none",
            score=0.0,
        )

    def test_score_one_ok(self):
        InspectReportPayload(
            report_id="r1",
            span_id="s1",
            model="gpt-4o",
            issues=[],
            overall_severity="none",
            score=1.0,
        )

    def test_non_list_issues_raises(self):
        with pytest.raises(TypeError, match="issues"):
            InspectReportPayload(
                report_id="r1",
                span_id="s1",
                model="gpt-4o",
                issues="not-a-list",  # type: ignore
                overall_severity="none",
            )

    def test_wrong_issue_type_raises(self):
        with pytest.raises(TypeError, match="InspectIssueSummary"):
            InspectReportPayload(
                report_id="r1",
                span_id="s1",
                model="gpt-4o",
                issues=["not-an-issue"],  # type: ignore
                overall_severity="low",
            )

    def test_frozen(self):
        p = InspectReportPayload(
            report_id="r1", span_id="s1", model="gpt-4o", issues=[], overall_severity="none"
        )
        with pytest.raises((AttributeError, TypeError)):
            p.model = "other"  # type: ignore


# ===========================================================================
# Top-level __init__ re-exports for Phase 5
# ===========================================================================


class TestTopLevelReexports:
    """Spot-check that Phase 5 classes appear at the package root."""

    def test_span_completed_accessible(self):
        import llm_toolkit_schema
        assert hasattr(llm_toolkit_schema, "SpanCompletedPayload")

    def test_validate_event_accessible(self):
        import llm_toolkit_schema
        assert hasattr(llm_toolkit_schema, "validate_event")

    def test_version(self):
        import llm_toolkit_schema
        assert llm_toolkit_schema.__version__ == "1.1.2"
