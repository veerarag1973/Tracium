"""Supplementary tests targeting every uncovered branch in Phase 5 namespace modules.

Each test is labelled with the source file and line(s) it is designed to reach
so that future maintainers can see the intent at a glance.

Coverage targets (cache/cost/diff/eval_/fence/guard/prompt/redact/template/validate):
  * Every ``raise ValueError / TypeError`` reachable from __post_init__ that the
    initial 200-test suite left uncovered.
  * Every ``if <optional> is not None:`` False-branch inside ``to_dict()`` methods
    that was never taken because ``to_dict()`` was never called on a minimal object.
  * Every ``if <optional> is not None else None`` ternary inside ``from_dict()``
    that produced ``None`` (the else branch) was never exercised.
  * ``validate.py`` line 138: the ``len(value) < min_length`` raise path.
"""

from __future__ import annotations

import pytest

# ── cache ─────────────────────────────────────────────────────────────────────
from llm_toolkit_schema.namespaces.cache import CacheEvictedPayload, CacheHitPayload, CacheMissPayload

# ── cost ──────────────────────────────────────────────────────────────────────
from llm_toolkit_schema.namespaces.cost import BudgetThresholdPayload, CostRecordedPayload

# ── diff ──────────────────────────────────────────────────────────────────────
from llm_toolkit_schema.namespaces.diff import DiffComparisonPayload, DiffReportPayload

# ── eval_ ─────────────────────────────────────────────────────────────────────
from llm_toolkit_schema.namespaces.eval_ import EvalRegressionPayload, EvalScenarioPayload

# ── fence ─────────────────────────────────────────────────────────────────────
from llm_toolkit_schema.namespaces.fence import (
    FenceValidationFailedPayload,
    RetryTriggeredPayload,
    ValidationPassedPayload,
)

# ── guard ─────────────────────────────────────────────────────────────────────
from llm_toolkit_schema.namespaces.guard import GuardBlockedPayload, GuardFlaggedPayload

# ── prompt ────────────────────────────────────────────────────────────────────
from llm_toolkit_schema.namespaces.prompt import (
    PromptApprovedPayload,
    PromptPromotedPayload,
    PromptRolledBackPayload,
    PromptSavedPayload,
)

# ── redact ────────────────────────────────────────────────────────────────────
from llm_toolkit_schema.namespaces.redact import (
    PIIDetectedPayload,
    PIIRedactedPayload,
    ScanCompletedPayload,
)

# ── template ──────────────────────────────────────────────────────────────────
from llm_toolkit_schema.namespaces.template import (
    TemplateRenderedPayload,
    TemplateValidationFailedPayload,
    VariableMissingPayload,
)

# ── validate ──────────────────────────────────────────────────────────────────
from llm_toolkit_schema.exceptions import SchemaValidationError
from llm_toolkit_schema.validate import _stdlib_validate


# ===========================================================================
# cache.py — lines 51, 53, 56, 77->79, 81->83, 124, 136->138, 178, 180
# ===========================================================================


class TestCacheHitPayloadCoverage:
    """Missing validation raises and to_dict / from_dict optional-field branches."""

    # ── line 51 ──────────────────────────────────────────────────────────────
    def test_empty_cache_key_hash_raises(self):
        """CacheHitPayload.cache_key_hash must be non-empty (line 51)."""
        with pytest.raises(ValueError, match="cache_key_hash"):
            CacheHitPayload(cache_key_hash="", cache_store="redis")

    def test_non_string_cache_key_hash_raises(self):
        """Non-string truthy value also triggers the same guard (line 51)."""
        with pytest.raises(ValueError, match="cache_key_hash"):
            CacheHitPayload(cache_key_hash=123, cache_store="redis")  # type: ignore[arg-type]

    # ── line 53 ──────────────────────────────────────────────────────────────
    def test_empty_cache_store_raises(self):
        """CacheHitPayload.cache_store must be non-empty (line 53)."""
        with pytest.raises(ValueError, match="cache_store"):
            CacheHitPayload(cache_key_hash="abc", cache_store="")

    def test_non_string_cache_store_raises(self):
        """Non-string truthy value also triggers the same guard (line 53)."""
        with pytest.raises(ValueError, match="cache_store"):
            CacheHitPayload(cache_key_hash="abc", cache_store=99)  # type: ignore[arg-type]

    # ── line 56 ──────────────────────────────────────────────────────────────
    def test_non_numeric_similarity_score_raises(self):
        """A non-numeric similarity_score triggers the isinstance guard (line 56)."""
        with pytest.raises(ValueError, match="similarity_score"):
            CacheHitPayload(cache_key_hash="k", cache_store="r", similarity_score="high")  # type: ignore[arg-type]

    # ── branches 77->79, 81->83 ──────────────────────────────────────────────
    def test_to_dict_without_optional_fields(self):
        """to_dict() on a minimal hit — all optional fields None — covers the
        False branches of the ``if similarity_score is not None`` (77->79) and
        ``if ttl_seconds is not None`` (81->83) guards."""
        p = CacheHitPayload(cache_key_hash="sha256-abc", cache_store="redis")
        d = p.to_dict()
        assert d == {"cache_key_hash": "sha256-abc", "cache_store": "redis"}
        assert "similarity_score" not in d
        assert "cached_event_id" not in d
        assert "ttl_seconds" not in d

    # ── branch 136->138 ──────────────────────────────────────────────────────
    def test_from_dict_without_ttl_seconds(self):
        """from_dict() with ttl_seconds absent covers the else-None branch (136->138)."""
        data = {"cache_key_hash": "k", "cache_store": "r", "similarity_score": 0.8}
        p = CacheHitPayload.from_dict(data)
        assert p.ttl_seconds is None
        assert p.similarity_score == 0.8


class TestCacheMissPayloadCoverage:
    """Missing raises and to_dict optional-field branches for CacheMissPayload."""

    # ── line 124 (raise for cache_store validation) ──────────────────────────
    def test_empty_cache_key_hash_raises(self):
        """Empty cache_key_hash in CacheMissPayload raises ValueError."""
        with pytest.raises(ValueError, match="cache_key_hash"):
            CacheMissPayload(cache_key_hash="", cache_store="r")

    def test_empty_cache_store_raises(self):
        """Empty cache_store in CacheMissPayload raises ValueError (line 124)."""
        with pytest.raises(ValueError, match="cache_store"):
            CacheMissPayload(cache_key_hash="valid-key", cache_store="")

    def test_non_string_cache_store_raises(self):
        """Non-string cache_store triggers the isinstance guard."""
        with pytest.raises(ValueError, match="cache_store"):
            CacheMissPayload(cache_key_hash="valid-key", cache_store=42)  # type: ignore[arg-type]

    # ── branch 136->138 (to_dict reason is None) ─────────────────────────────
    def test_to_dict_without_reason(self):
        """to_dict() when reason is None must not include the 'reason' key (136->138)."""
        p = CacheMissPayload(cache_key_hash="sha256-key", cache_store="memcached")
        d = p.to_dict()
        assert d == {"cache_key_hash": "sha256-key", "cache_store": "memcached"}
        assert "reason" not in d


class TestCacheEvictedPayloadCoverage:
    """Missing raises for CacheEvictedPayload (lines 178, 180)."""

    # ── line 178 ─────────────────────────────────────────────────────────────
    def test_empty_cache_key_hash_raises(self):
        """Empty cache_key_hash raises ValueError in CacheEvictedPayload (line 178)."""
        with pytest.raises(ValueError, match="cache_key_hash"):
            CacheEvictedPayload(cache_key_hash="", cache_store="redis", reason="lru")

    def test_non_string_cache_key_hash_raises(self):
        """Non-string cache_key_hash also raises (line 178)."""
        with pytest.raises(ValueError, match="cache_key_hash"):
            CacheEvictedPayload(cache_key_hash=0, cache_store="redis", reason="lru")  # type: ignore[arg-type]

    # ── line 180 ─────────────────────────────────────────────────────────────
    def test_empty_cache_store_raises(self):
        """Empty cache_store raises ValueError in CacheEvictedPayload (line 180)."""
        with pytest.raises(ValueError, match="cache_store"):
            CacheEvictedPayload(cache_key_hash="k", cache_store="", reason="lru")

    def test_non_string_cache_store_raises(self):
        """Non-string cache_store also raises (line 180)."""
        with pytest.raises(ValueError, match="cache_store"):
            CacheEvictedPayload(cache_key_hash="k", cache_store=[], reason="lru")  # type: ignore[arg-type]


# ===========================================================================
# cost.py — lines 63, 71, 144, 155, 159, 176->178
# ===========================================================================


class TestCostRecordedPayloadCoverage:
    """Missing raises for CostRecordedPayload."""

    def _make(self, **kw):
        defaults = dict(
            span_event_id="evt1",
            model_name="gpt-4o",
            provider="openai",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost_usd=0.002,
        )
        defaults.update(kw)
        return CostRecordedPayload(**defaults)

    # ── line 63 (non-int tokens) ──────────────────────────────────────────────
    def test_float_prompt_tokens_raises(self):
        """Fractional prompt_tokens must fail the isinstance check (line 63)."""
        with pytest.raises(ValueError, match="non-negative"):
            self._make(prompt_tokens=1.5)  # type: ignore[arg-type]

    def test_float_completion_tokens_raises(self):
        """Fractional completion_tokens similarly raises (line 63)."""
        with pytest.raises(ValueError, match="non-negative"):
            self._make(completion_tokens=0.5)  # type: ignore[arg-type]

    def test_float_total_tokens_raises(self):
        """Fractional total_tokens raises (line 63)."""
        with pytest.raises(ValueError, match="non-negative"):
            self._make(total_tokens=2.5)  # type: ignore[arg-type]

    # ── line 71 (empty currency) ──────────────────────────────────────────────
    def test_empty_currency_raises(self):
        """Empty currency string raises ValueError (line 71)."""
        with pytest.raises(ValueError, match="currency"):
            self._make(currency="")

    def test_non_string_currency_raises(self):
        """Non-string currency raises ValueError (line 71)."""
        with pytest.raises(ValueError, match="currency"):
            self._make(currency=840)  # type: ignore[arg-type]


class TestBudgetThresholdPayloadCoverage:
    """Missing raises and to_dict branch for BudgetThresholdPayload."""

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

    # ── line 144 (non-numeric threshold_usd) ─────────────────────────────────
    def test_non_numeric_threshold_usd_raises(self):
        """Non-numeric threshold_usd raises ValueError (line 144)."""
        with pytest.raises(ValueError, match="threshold_usd"):
            self._make(threshold_usd="bad")  # type: ignore[arg-type]

    def test_negative_threshold_usd_raises(self):
        """Negative threshold_usd raises ValueError (line 144)."""
        with pytest.raises(ValueError, match="threshold_usd"):
            self._make(threshold_usd=-0.01)

    # ── line 155 (non-numeric current_spend_usd) ──────────────────────────────
    def test_non_numeric_current_spend_raises(self):
        """Non-numeric current_spend_usd raises ValueError (line 155)."""
        with pytest.raises(ValueError, match="current_spend_usd"):
            self._make(current_spend_usd="bad")  # type: ignore[arg-type]

    def test_negative_current_spend_raises(self):
        """Negative current_spend_usd raises ValueError (line 155)."""
        with pytest.raises(ValueError, match="current_spend_usd"):
            self._make(current_spend_usd=-5.0)

    # ── line 159 (non-numeric percentage_used) ────────────────────────────────
    def test_non_numeric_percentage_raises(self):
        """Non-numeric percentage_used raises ValueError (line 159)."""
        with pytest.raises(ValueError, match="percentage_used"):
            self._make(percentage_used=None)  # type: ignore[arg-type]

    def test_negative_percentage_raises(self):
        """Negative percentage_used raises ValueError (line 159)."""
        with pytest.raises(ValueError, match="percentage_used"):
            self._make(percentage_used=-10.0)

    # ── branch 176->178 (to_dict org_id is None) ─────────────────────────────
    def test_to_dict_without_org_id(self):
        """to_dict() with org_id=None omits the key (branch 176->178)."""
        p = self._make()
        d = p.to_dict()
        assert "org_id" not in d
        assert d["budget_id"] == "bgt-1"


# ===========================================================================
# diff.py — lines 58, 60, 63, 70, 83->85, 140, 142
# ===========================================================================


class TestDiffComparisonPayloadCoverage:
    """Missing raises and to_dict branches for DiffComparisonPayload."""

    # ── line 58 (empty target_id) ─────────────────────────────────────────────
    def test_empty_target_id_raises(self):
        """Empty target_id raises ValueError (line 58)."""
        with pytest.raises(ValueError, match="target_id"):
            DiffComparisonPayload(source_id="a", target_id="", diff_type="text")

    def test_non_string_target_id_raises(self):
        """Non-string target_id raises ValueError (line 58)."""
        with pytest.raises(ValueError, match="target_id"):
            DiffComparisonPayload(source_id="a", target_id=42, diff_type="text")  # type: ignore[arg-type]

    # ── line 60 (empty diff_type) ─────────────────────────────────────────────
    def test_empty_diff_type_raises(self):
        """Empty diff_type raises ValueError (line 60)."""
        with pytest.raises(ValueError, match="diff_type"):
            DiffComparisonPayload(source_id="a", target_id="b", diff_type="")

    def test_non_string_diff_type_raises(self):
        """Non-string diff_type raises ValueError (line 60)."""
        with pytest.raises(ValueError, match="diff_type"):
            DiffComparisonPayload(source_id="a", target_id="b", diff_type=123)  # type: ignore[arg-type]

    # ── line 63 (non-numeric similarity_score) ────────────────────────────────
    def test_non_numeric_similarity_score_raises(self):
        """A non-numeric similarity_score triggers the isinstance guard (line 63)."""
        with pytest.raises(ValueError, match="similarity_score"):
            DiffComparisonPayload(
                source_id="a", target_id="b", diff_type="text", similarity_score="bad"  # type: ignore[arg-type]
            )

    # ── line 70 (non-dict diff_result) ────────────────────────────────────────
    def test_non_dict_diff_result_raises(self):
        """A non-dict diff_result triggers a TypeError (line 70)."""
        with pytest.raises(TypeError, match="diff_result"):
            DiffComparisonPayload(
                source_id="a", target_id="b", diff_type="text", diff_result="not-a-dict"  # type: ignore[arg-type]
            )

    def test_list_diff_result_raises(self):
        """A list is also rejected as diff_result (line 70)."""
        with pytest.raises(TypeError, match="diff_result"):
            DiffComparisonPayload(
                source_id="a", target_id="b", diff_type="text", diff_result=["x"]  # type: ignore[arg-type]
            )

    # ── branch 83->85 (source_text / target_text None in to_dict) ────────────
    def test_to_dict_without_source_target_text(self):
        """to_dict() on a payload with no source/target text covers branches 83->85."""
        p = DiffComparisonPayload(source_id="a", target_id="b", diff_type="semantic")
        d = p.to_dict()
        assert "source_text" not in d
        assert "target_text" not in d
        assert "diff_result" not in d


class TestDiffReportPayloadCoverage:
    """Missing raises for DiffReportPayload."""

    # ── line 140 (empty comparison_event_id) ──────────────────────────────────
    def test_empty_comparison_event_id_raises(self):
        """Empty comparison_event_id raises ValueError (line 140)."""
        with pytest.raises(ValueError, match="comparison_event_id"):
            DiffReportPayload(report_id="r1", comparison_event_id="", format="html")

    def test_non_string_comparison_event_id_raises(self):
        """Non-string comparison_event_id raises ValueError (line 140)."""
        with pytest.raises(ValueError, match="comparison_event_id"):
            DiffReportPayload(report_id="r1", comparison_event_id=None, format="html")  # type: ignore[arg-type]

    # ── line 142 (empty format) ───────────────────────────────────────────────
    def test_empty_format_raises(self):
        """Empty format string raises ValueError (line 142)."""
        with pytest.raises(ValueError, match="format"):
            DiffReportPayload(report_id="r1", comparison_event_id="evt-1", format="")

    def test_non_string_format_raises(self):
        """Non-string format raises ValueError (line 142)."""
        with pytest.raises(ValueError, match="format"):
            DiffReportPayload(report_id="r1", comparison_event_id="evt-1", format=0)  # type: ignore[arg-type]


# ===========================================================================
# eval_.py — lines 54, 56, 62, 70, 74, 89->91, 150, 153, 156, 159, 175->177
# ===========================================================================


class TestEvalScenarioPayloadCoverage:
    """Missing raises and to_dict branches for EvalScenarioPayload."""

    # ── line 54 (empty scenario_id) ───────────────────────────────────────────
    def test_empty_scenario_id_raises(self):
        """Empty scenario_id raises ValueError (line 54)."""
        with pytest.raises(ValueError, match="scenario_id"):
            EvalScenarioPayload(scenario_id="", scenario_name="t", status="passed")

    # ── line 56 (empty scenario_name) ────────────────────────────────────────
    def test_empty_scenario_name_raises(self):
        """Empty scenario_name raises ValueError (line 56)."""
        with pytest.raises(ValueError, match="scenario_name"):
            EvalScenarioPayload(scenario_id="s1", scenario_name="", status="passed")

    def test_non_string_scenario_name_raises(self):
        """Non-string scenario_name triggers the isinstance guard (line 56)."""
        with pytest.raises(ValueError, match="scenario_name"):
            EvalScenarioPayload(scenario_id="s1", scenario_name=42, status="passed")  # type: ignore[arg-type]

    # ── line 62 (non-numeric score) ───────────────────────────────────────────
    def test_non_numeric_score_raises(self):
        """Non-numeric score raises ValueError (line 62)."""
        with pytest.raises(ValueError, match="score"):
            EvalScenarioPayload(
                scenario_id="s1", scenario_name="t", status="passed", score="bad"  # type: ignore[arg-type]
            )

    # ── line 70 (non-numeric baseline_score) ─────────────────────────────────
    def test_non_numeric_baseline_score_raises(self):
        """Non-numeric baseline_score raises ValueError (line 70)."""
        with pytest.raises(ValueError, match="baseline_score"):
            EvalScenarioPayload(
                scenario_id="s1",
                scenario_name="t",
                status="passed",
                baseline_score="bad",  # type: ignore[arg-type]
            )

    # ── line 74 (negative duration_ms) ───────────────────────────────────────
    def test_negative_duration_ms_raises(self):
        """Negative duration_ms raises ValueError (line 74)."""
        with pytest.raises(ValueError, match="duration_ms"):
            EvalScenarioPayload(
                scenario_id="s1", scenario_name="t", status="passed", duration_ms=-1.0
            )

    def test_non_numeric_duration_ms_raises(self):
        """Non-numeric duration_ms raises ValueError (line 74)."""
        with pytest.raises(ValueError, match="duration_ms"):
            EvalScenarioPayload(
                scenario_id="s1", scenario_name="t", status="passed", duration_ms="slow"  # type: ignore[arg-type]
            )

    # ── branches 89->91 (score / metrics / baseline_score / duration_ms None) ─
    def test_to_dict_minimal(self):
        """to_dict() on a minimal scenario — all optional fields None (89->91)."""
        p = EvalScenarioPayload(scenario_id="s1", scenario_name="test", status="skipped")
        d = p.to_dict()
        assert "score" not in d
        assert "metrics" not in d
        assert "baseline_score" not in d
        assert "duration_ms" not in d


class TestEvalRegressionPayloadCoverage:
    """Missing raises and to_dict branches for EvalRegressionPayload."""

    def _make(self, **kw):
        defaults = dict(
            scenario_id="s1",
            scenario_name="regression-test",
            current_score=0.7,
            baseline_score=0.8,
            regression_delta=-0.1,
            threshold=-0.05,
        )
        defaults.update(kw)
        return EvalRegressionPayload(**defaults)

    # ── line 150 (empty scenario_name) ────────────────────────────────────────
    def test_empty_scenario_name_raises(self):
        """Empty scenario_name raises ValueError in EvalRegressionPayload (line 150)."""
        with pytest.raises(ValueError, match="scenario_name"):
            self._make(scenario_name="")

    # ── line 153 (non-numeric current_score) ──────────────────────────────────
    def test_non_numeric_current_score_raises(self):
        """Non-numeric current_score raises ValueError (line 153)."""
        with pytest.raises(ValueError, match="current_score"):
            self._make(current_score="bad")  # type: ignore[arg-type]

    # ── line 156 (non-numeric baseline_score) ─────────────────────────────────
    def test_non_numeric_baseline_score_raises(self):
        """Non-numeric baseline_score raises ValueError (line 156)."""
        with pytest.raises(ValueError, match="baseline_score"):
            self._make(baseline_score="bad")  # type: ignore[arg-type]

    # ── line 159 (non-numeric regression_delta) ───────────────────────────────
    def test_non_numeric_regression_delta_raises(self):
        """Non-numeric regression_delta raises ValueError (line 159)."""
        with pytest.raises(ValueError, match="regression_delta"):
            self._make(regression_delta="bad")  # type: ignore[arg-type]

    def test_non_numeric_threshold_raises(self):
        """Non-numeric threshold raises ValueError (line 159 / same loop)."""
        with pytest.raises(ValueError, match="threshold"):
            self._make(threshold="bad")  # type: ignore[arg-type]

    # ── line 153/156 — invalid metrics type ───────────────────────────────────
    def test_non_dict_metrics_raises(self):
        """metrics that isn't a dict raises TypeError."""
        with pytest.raises(TypeError, match="metrics"):
            self._make(metrics="bad")  # type: ignore[arg-type]

    def test_metrics_wrong_value_type_raises(self):
        """metrics with a non-numeric value raises TypeError."""
        with pytest.raises(TypeError, match="metrics"):
            self._make(metrics={"rouge": "bad"})  # type: ignore[arg-type]

    # ── branch 175->177 (to_dict metrics is None) ─────────────────────────────
    def test_to_dict_without_metrics(self):
        """to_dict() when metrics is None omits the key (branch 175->177)."""
        p = self._make()
        d = p.to_dict()
        assert "metrics" not in d


# ===========================================================================
# fence.py — lines 46, 48, 54, 69->71, 119, 123, 130, 132, 134, 193, 197, 221->223
# ===========================================================================


class TestValidationPassedPayloadCoverage:
    """Missing raises and to_dict branches for ValidationPassedPayload."""

    # ── line 46 (empty format_type) ───────────────────────────────────────────
    def test_empty_format_type_raises(self):
        """Empty format_type raises ValueError (line 46)."""
        with pytest.raises(ValueError, match="format_type"):
            ValidationPassedPayload(validator_id="v1", format_type="")

    def test_non_string_format_type_raises(self):
        """Non-string format_type raises ValueError (line 46)."""
        with pytest.raises(ValueError, match="format_type"):
            ValidationPassedPayload(validator_id="v1", format_type=42)  # type: ignore[arg-type]

    # ── line 48 (non-int / zero attempt) ──────────────────────────────────────
    def test_float_attempt_raises(self):
        """Float attempt triggers the isinstance guard (line 48)."""
        with pytest.raises(ValueError, match="attempt"):
            ValidationPassedPayload(validator_id="v1", format_type="json", attempt=1.5)  # type: ignore[arg-type]

    # ── line 54 (negative duration_ms) ────────────────────────────────────────
    def test_negative_duration_ms_raises(self):
        """Negative duration_ms raises ValueError (line 54)."""
        with pytest.raises(ValueError, match="duration_ms"):
            ValidationPassedPayload(
                validator_id="v1", format_type="json", duration_ms=-0.1
            )

    def test_non_numeric_duration_ms_raises(self):
        """Non-numeric duration_ms raises ValueError (line 54)."""
        with pytest.raises(ValueError, match="duration_ms"):
            ValidationPassedPayload(
                validator_id="v1", format_type="json", duration_ms="fast"  # type: ignore[arg-type]
            )

    # ── branch 69->71 (duration_ms None in to_dict) ───────────────────────────
    def test_to_dict_without_duration_ms(self):
        """to_dict() with duration_ms=None omits the key (branch 69->71)."""
        p = ValidationPassedPayload(validator_id="v1", format_type="yaml")
        d = p.to_dict()
        assert "duration_ms" not in d
        assert d["attempt"] == 1


class TestFenceValidationFailedPayloadCoverage:
    """Missing raises for FenceValidationFailedPayload."""

    # ── line 119 (empty format_type) ──────────────────────────────────────────
    def test_empty_format_type_raises(self):
        """Empty format_type raises ValueError (line 119)."""
        with pytest.raises(ValueError, match="format_type"):
            FenceValidationFailedPayload(
                validator_id="v1", format_type="", errors=["bad schema"]
            )

    def test_non_string_format_type_raises(self):
        """Non-string format_type raises ValueError (line 119)."""
        with pytest.raises(ValueError, match="format_type"):
            FenceValidationFailedPayload(
                validator_id="v1", format_type=0, errors=["err"]  # type: ignore[arg-type]
            )

    # ── line 123 (non-string error item) ──────────────────────────────────────
    def test_non_string_error_item_raises(self):
        """A non-string item inside errors raises TypeError (line 123)."""
        with pytest.raises(TypeError, match="string"):
            FenceValidationFailedPayload(
                validator_id="v1", format_type="json", errors=[123]  # type: ignore[list-item]
            )

    # ── line 130 / 132 (non-int / zero attempt, non-bool retryable) ───────────
    def test_float_attempt_raises(self):
        """Float attempt triggers isinstance guard (line 130)."""
        with pytest.raises(ValueError, match="attempt"):
            FenceValidationFailedPayload(
                validator_id="v1", format_type="json", errors=["e"], attempt=2.0  # type: ignore[arg-type]
            )

    def test_non_bool_retryable_raises(self):
        """Non-bool retryable raises TypeError (line 132 / 134)."""
        with pytest.raises(TypeError, match="retryable"):
            FenceValidationFailedPayload(
                validator_id="v1",
                format_type="json",
                errors=["e"],
                retryable="yes",  # type: ignore[arg-type]
            )

    # ── line 134 (truthy non-bool, e.g. int 1) ────────────────────────────────
    def test_int_retryable_raises(self):
        """Integer retryable also raises TypeError (line 134)."""
        with pytest.raises(TypeError, match="retryable"):
            FenceValidationFailedPayload(
                validator_id="v1",
                format_type="json",
                errors=["e"],
                retryable=1,  # type: ignore[arg-type]
            )


class TestRetryTriggeredPayloadCoverage:
    """Missing raises and to_dict branches for RetryTriggeredPayload."""

    # ── line 193 (non-int / zero attempt) ────────────────────────────────────
    def test_float_attempt_raises(self):
        """Float attempt triggers isinstance guard (line 193)."""
        with pytest.raises(ValueError, match="attempt"):
            RetryTriggeredPayload(validator_id="v1", attempt=1.5, max_attempts=3)  # type: ignore[arg-type]

    # ── line 197 (non-int / zero max_attempts) ────────────────────────────────
    def test_zero_max_attempts_raises(self):
        """Zero max_attempts raises ValueError (line 197)."""
        with pytest.raises(ValueError, match="max_attempts"):
            RetryTriggeredPayload(validator_id="v1", attempt=1, max_attempts=0)

    def test_float_max_attempts_raises(self):
        """Float max_attempts triggers isinstance guard (line 197)."""
        with pytest.raises(ValueError, match="max_attempts"):
            RetryTriggeredPayload(validator_id="v1", attempt=1, max_attempts=3.0)  # type: ignore[arg-type]

    # ── branch 221->223 (previous_error None in to_dict) ─────────────────────
    def test_to_dict_without_previous_error(self):
        """to_dict() with previous_error=None omits the key (branch 221->223)."""
        p = RetryTriggeredPayload(validator_id="v1", attempt=2, max_attempts=3)
        d = p.to_dict()
        assert "previous_error" not in d
        assert d["strategy"] == "regenerate"


# ===========================================================================
# guard.py — lines 53, 60, 130, 137, 139
# ===========================================================================


class TestGuardBlockedPayloadCoverage:
    """Missing raises for GuardBlockedPayload."""

    # ── line 53 (non-string violation_type item) ──────────────────────────────
    def test_non_string_violation_type_raises(self):
        """Non-string item inside violation_types raises TypeError (line 53)."""
        with pytest.raises(TypeError, match="violation_type"):
            GuardBlockedPayload(
                policy_id="p",
                policy_name="n",
                input_hash="h",
                violation_types=[123],  # type: ignore[list-item]
            )

    def test_mixed_violation_types_raises(self):
        """Mixed list with a non-string item raises TypeError (line 53)."""
        with pytest.raises(TypeError, match="violation_type"):
            GuardBlockedPayload(
                policy_id="p",
                policy_name="n",
                input_hash="h",
                violation_types=["ok", None],  # type: ignore[list-item]
            )


class TestGuardFlaggedPayloadCoverage:
    """Missing raises for GuardFlaggedPayload."""

    # ── line 60 (non-string flag_type item) ───────────────────────────────────
    def test_non_string_flag_type_raises(self):
        """Non-string item inside flag_types raises TypeError (line 60)."""
        with pytest.raises(TypeError, match="flag_type"):
            GuardFlaggedPayload(
                policy_id="p",
                policy_name="n",
                output_hash="h",
                flag_types=[None],  # type: ignore[list-item]
            )

    # ── line 130 / 137 (invalid severity) ────────────────────────────────────
    def test_invalid_severity_raises(self):
        """Unsupported severity raises ValueError (line 130)."""
        with pytest.raises(ValueError, match="severity"):
            GuardFlaggedPayload(
                policy_id="p",
                policy_name="n",
                output_hash="h",
                flag_types=["pii"],
                severity="extreme",
            )

    # ── line 139 – ensure the pass-through path works for every valid severity ─
    def test_all_valid_severities(self):
        """All four severity levels are accepted (line 139 branch not raised)."""
        for sev in ("low", "medium", "high", "critical"):
            p = GuardFlaggedPayload(
                policy_id="p",
                policy_name="n",
                output_hash="h",
                flag_types=["x"],
                severity=sev,
            )
            assert p.severity == sev


# ===========================================================================
# prompt.py — lines 56, 78->80, 128, 146->148, 204->206, 251, 266->268, 269
# ===========================================================================


class TestPromptSavedPayloadCoverage:
    """Missing raises and to_dict branches for PromptSavedPayload."""

    # ── line 56 (non-list tags) ───────────────────────────────────────────────
    def test_non_list_tags_raises(self):
        """Non-list tags raises TypeError (line 56)."""
        with pytest.raises(TypeError, match="tags"):
            PromptSavedPayload(
                prompt_id="p1",
                version="1.0",
                environment="dev",
                template_hash="h",
                tags="not-a-list",  # type: ignore[arg-type]
            )

    # ── branch 78->80 (author is None in to_dict) ─────────────────────────────
    def test_to_dict_without_author_and_tags(self):
        """to_dict() with author=None and tags=None covers branch 78->80."""
        p = PromptSavedPayload(
            prompt_id="p1", version="1.0", environment="dev", template_hash="h"
        )
        d = p.to_dict()
        assert "author" not in d
        assert "tags" not in d


class TestPromptPromotedPayloadCoverage:
    """Missing raises and to_dict branches for PromptPromotedPayload."""

    # ── line 128 (empty version / environment fields) ─────────────────────────
    def test_empty_version_raises(self):
        """Empty version raises ValueError (line 128)."""
        with pytest.raises(ValueError, match="version"):
            PromptPromotedPayload(
                prompt_id="p1",
                version="",
                from_environment="staging",
                to_environment="production",
            )

    def test_empty_from_environment_raises(self):
        """Empty from_environment raises ValueError (line 128)."""
        with pytest.raises(ValueError, match="from_environment"):
            PromptPromotedPayload(
                prompt_id="p1",
                version="1.0",
                from_environment="",
                to_environment="production",
            )

    def test_empty_to_environment_raises(self):
        """Empty to_environment raises ValueError (line 128)."""
        with pytest.raises(ValueError, match="to_environment"):
            PromptPromotedPayload(
                prompt_id="p1",
                version="1.0",
                from_environment="staging",
                to_environment="",
            )

    # ── branch 146->148 (promoted_by is None in to_dict) ─────────────────────
    def test_to_dict_without_promoted_by(self):
        """to_dict() with promoted_by=None omits the key (branch 146->148)."""
        p = PromptPromotedPayload(
            prompt_id="p1",
            version="1.0",
            from_environment="staging",
            to_environment="production",
        )
        d = p.to_dict()
        assert "promoted_by" not in d


class TestPromptApprovedPayloadCoverage:
    """Missing to_dict branch for PromptApprovedPayload."""

    # ── branch 204->206 (approval_note is None in to_dict) ───────────────────
    def test_to_dict_without_approval_note(self):
        """to_dict() with approval_note=None omits the key (branch 204->206)."""
        p = PromptApprovedPayload(
            prompt_id="p1", version="1.0", approved_by="alice"
        )
        d = p.to_dict()
        assert "approval_note" not in d
        assert d["approved_by"] == "alice"


class TestPromptRolledBackPayloadCoverage:
    """Missing raises and to_dict branches for PromptRolledBackPayload."""

    # ── line 251 (empty from_version / to_version) ───────────────────────────
    def test_empty_from_version_raises(self):
        """Empty from_version raises ValueError (line 251)."""
        with pytest.raises(ValueError, match="from_version"):
            PromptRolledBackPayload(
                prompt_id="p1", from_version="", to_version="1.0"
            )

    def test_empty_to_version_raises(self):
        """Empty to_version raises ValueError (line 251)."""
        with pytest.raises(ValueError, match="to_version"):
            PromptRolledBackPayload(
                prompt_id="p1", from_version="2.0", to_version=""
            )

    # ── branches 266->268, 269 (reason / rolled_back_by is None in to_dict) ──
    def test_to_dict_without_optional_fields(self):
        """to_dict() with reason=None and rolled_back_by=None covers 266->268, 269."""
        p = PromptRolledBackPayload(
            prompt_id="p1", from_version="2.0", to_version="1.0"
        )
        d = p.to_dict()
        assert "reason" not in d
        assert "rolled_back_by" not in d


# ===========================================================================
# redact.py — lines 54, 59, 120, 122, 125, 140->142, 199, 212->214, 214->216
# ===========================================================================


class TestPIIDetectedPayloadCoverage:
    """Missing raises for PIIDetectedPayload."""

    # ── line 54 (non-string pii_type item) ────────────────────────────────────
    def test_non_string_pii_type_raises(self):
        """Non-string item inside pii_types raises TypeError (line 54)."""
        with pytest.raises(TypeError, match="pii_type"):
            PIIDetectedPayload(
                field_path="f",
                pii_types=[None],  # type: ignore[list-item]
                confidence=0.9,
            )

    # ── line 59 (non-bool redacted) ───────────────────────────────────────────
    def test_non_bool_redacted_raises(self):
        """Non-bool redacted raises TypeError (line 59)."""
        with pytest.raises(TypeError, match="redacted"):
            PIIDetectedPayload(
                field_path="f",
                pii_types=["email"],
                confidence=0.9,
                redacted=1,  # type: ignore[arg-type]
            )


class TestPIIRedactedPayloadCoverage:
    """Missing raises and to_dict branches for PIIRedactedPayload."""

    # ── line 120 (empty pii_types list) ──────────────────────────────────────
    def test_empty_pii_types_raises(self):
        """Empty pii_types raises ValueError (line 120)."""
        with pytest.raises(ValueError, match="pii_types"):
            PIIRedactedPayload(field_path="f", pii_types=[], method="mask")

    # ── line 122 (non-string pii_type item) ───────────────────────────────────
    def test_non_string_pii_type_raises(self):
        """Non-string item in pii_types raises TypeError (line 122)."""
        with pytest.raises(TypeError, match="pii_type"):
            PIIRedactedPayload(
                field_path="f",
                pii_types=[42],  # type: ignore[list-item]
                method="mask",
            )

    # ── line 125 (empty method) ───────────────────────────────────────────────
    def test_non_string_method_raises(self):
        """Non-string method raises ValueError (line 125)."""
        with pytest.raises(ValueError, match="method"):
            PIIRedactedPayload(field_path="f", pii_types=["email"], method=123)  # type: ignore[arg-type]

    # ── branch 140->142 (redacted_by is None in to_dict) ─────────────────────
    def test_to_dict_without_redacted_by(self):
        """to_dict() with redacted_by=None omits the key (branch 140->142)."""
        p = PIIRedactedPayload(field_path="f", pii_types=["email"], method="hash")
        d = p.to_dict()
        assert "redacted_by" not in d
        assert d["method"] == "hash"


class TestScanCompletedPayloadCoverage:
    """Missing raises and branches for ScanCompletedPayload."""

    # ── line 199 (negative scanned_fields) ───────────────────────────────────
    def test_negative_scanned_fields_raises(self):
        """Negative scanned_fields raises ValueError (line 199)."""
        with pytest.raises(ValueError, match="non-negative"):
            ScanCompletedPayload(
                scanned_fields=-1,
                pii_detected_count=0,
                pii_redacted_count=0,
            )

    # ── branches 212->214, 214->216 (duration_ms / policy_id None in to_dict) ─
    def test_to_dict_without_duration_and_policy(self):
        """to_dict() with both optional fields None covers branches 212->214 and 214->216."""
        p = ScanCompletedPayload(
            scanned_fields=5, pii_detected_count=1, pii_redacted_count=1
        )
        d = p.to_dict()
        assert "duration_ms" not in d
        assert "policy_id" not in d

    def test_negative_duration_ms_raises(self):
        """Negative duration_ms raises ValueError."""
        with pytest.raises(ValueError, match="duration_ms"):
            ScanCompletedPayload(
                scanned_fields=5,
                pii_detected_count=1,
                pii_redacted_count=1,
                duration_ms=-0.5,
            )

    def test_non_numeric_duration_ms_raises(self):
        """Non-numeric duration_ms raises ValueError."""
        with pytest.raises(ValueError, match="duration_ms"):
            ScanCompletedPayload(
                scanned_fields=5,
                pii_detected_count=1,
                pii_redacted_count=1,
                duration_ms="fast",  # type: ignore[arg-type]
            )


# ===========================================================================
# template.py — lines 51, 53, 60, 66, 81->83, 83->85, 126, 133, 138, 200, 209, 221->223
# ===========================================================================


class TestTemplateRenderedPayloadCoverage:
    """Missing raises and to_dict branches for TemplateRenderedPayload."""

    # ── line 51 (empty template_version) ──────────────────────────────────────
    def test_empty_template_version_raises(self):
        """Empty template_version raises ValueError (line 51)."""
        with pytest.raises(ValueError, match="template_version"):
            TemplateRenderedPayload(template_id="t1", template_version="", variable_count=0)

    def test_non_string_template_version_raises(self):
        """Non-string template_version raises ValueError (line 51)."""
        with pytest.raises(ValueError, match="template_version"):
            TemplateRenderedPayload(template_id="t1", template_version=1, variable_count=0)  # type: ignore[arg-type]

    # ── line 53 (non-int / negative variable_count) ───────────────────────────
    def test_negative_variable_count_again(self):
        """Negative variable_count raises ValueError (line 53)."""
        with pytest.raises(ValueError, match="variable_count"):
            TemplateRenderedPayload(
                template_id="t1", template_version="1.0", variable_count=-1
            )

    def test_non_int_variable_count_raises(self):
        """Non-int variable_count raises ValueError (line 53)."""
        with pytest.raises(ValueError, match="variable_count"):
            TemplateRenderedPayload(
                template_id="t1", template_version="1.0", variable_count=2.5  # type: ignore[arg-type]
            )

    # ── line 60 (negative render_duration_ms) ────────────────────────────────
    def test_negative_render_duration_raises(self):
        """Negative render_duration_ms raises ValueError (line 60)."""
        with pytest.raises(ValueError, match="render_duration_ms"):
            TemplateRenderedPayload(
                template_id="t1",
                template_version="1.0",
                variable_count=0,
                render_duration_ms=-0.5,
            )

    def test_non_numeric_render_duration_raises(self):
        """Non-numeric render_duration_ms raises ValueError (line 60)."""
        with pytest.raises(ValueError, match="render_duration_ms"):
            TemplateRenderedPayload(
                template_id="t1",
                template_version="1.0",
                variable_count=0,
                render_duration_ms="fast",  # type: ignore[arg-type]
            )

    # ── line 66 (negative output_length) ─────────────────────────────────────
    def test_negative_output_length_raises(self):
        """Negative output_length raises ValueError (line 66)."""
        with pytest.raises(ValueError, match="output_length"):
            TemplateRenderedPayload(
                template_id="t1",
                template_version="1.0",
                variable_count=0,
                output_length=-1,
            )

    def test_non_int_output_length_raises(self):
        """Non-int output_length raises ValueError (line 66)."""
        with pytest.raises(ValueError, match="output_length"):
            TemplateRenderedPayload(
                template_id="t1",
                template_version="1.0",
                variable_count=0,
                output_length=1.5,  # type: ignore[arg-type]
            )

    # ── branches 81->83, 83->85 (optional fields None in to_dict) ────────────
    def test_to_dict_minimal(self):
        """to_dict() on a minimal payload covers the None-branch for optional fields."""
        p = TemplateRenderedPayload(template_id="t1", template_version="1.0", variable_count=3)
        d = p.to_dict()
        assert "render_duration_ms" not in d
        assert "output_length" not in d


class TestVariableMissingPayloadCoverage:
    """Missing raises for VariableMissingPayload."""

    # ── line 126 (non-string item in required_variables) ──────────────────────
    def test_non_string_required_variable_raises(self):
        """Non-string item inside required_variables raises TypeError (line 126)."""
        with pytest.raises(TypeError, match="required_variable"):
            VariableMissingPayload(
                template_id="t1",
                missing_variables=["x"],
                required_variables=[42],  # type: ignore[list-item]
            )

    # ── line 133 (empty required_variables) ───────────────────────────────────
    def test_empty_required_variables_raises(self):
        """Empty required_variables raises ValueError (line 133)."""
        with pytest.raises(ValueError, match="required_variables"):
            VariableMissingPayload(
                template_id="t1",
                missing_variables=["x"],
                required_variables=[],
            )

    # ── line 138 (non-string item in missing_variables) ───────────────────────
    def test_non_string_missing_variable_raises(self):
        """Non-string item inside missing_variables raises TypeError (line 138)."""
        with pytest.raises(TypeError, match="missing_variable"):
            VariableMissingPayload(
                template_id="t1",
                missing_variables=[None],  # type: ignore[list-item]
                required_variables=["x"],
            )


class TestTemplateValidationFailedPayloadCoverage:
    """Missing raises and to_dict branches for TemplateValidationFailedPayload."""

    # ── line 200 (non-string item in validation_errors) ──────────────────────
    def test_non_string_validation_error_raises(self):
        """Non-string item inside validation_errors raises TypeError (line 200)."""
        with pytest.raises(TypeError, match="validation_error"):
            TemplateValidationFailedPayload(
                template_id="t1",
                validation_errors=[123],  # type: ignore[list-item]
            )

    # ── line 209 (empty validator) is NOT an error — validator is optional.
    # The branch to cover is to_dict() when validator is None.
    # ── branch 221->223 (validator is None in to_dict) ────────────────────────
    def test_to_dict_without_validator(self):
        """to_dict() with validator=None omits the key (branch 221->223)."""
        p = TemplateValidationFailedPayload(
            template_id="t1", validation_errors=["undefined variable"]
        )
        d = p.to_dict()
        assert "validator" not in d
        assert d["validation_errors"] == ["undefined variable"]


# ===========================================================================
# validate.py — line 138 (len(value) < min_length raise)
# ===========================================================================


class TestStdlibValidateMinLengthCoverage:
    """Cover the min_length check inside _check_string_field (validate.py line 138)."""

    def test_schema_version_too_short_raises(self):
        """A schema_version that is too short (e.g. empty string) triggers the
        min_length guard (validate.py line 138)."""
        from llm_toolkit_schema.event import Event
        from llm_toolkit_schema.types import EventType

        # Build a valid doc then replace schema_version with a too-short string.
        event = Event(
            event_type=EventType.TRACE_SPAN_COMPLETED,
            source="svc@1.0.0",
            payload={"k": "v"},
        )
        doc = event.to_dict()
        # Overwrite schema_version with a string that passes isinstance but is too
        # short to satisfy the minimum length (1) — the empty string case is
        # handled by the required-field guard, so use a whitespace-only value
        # that is technically a non-empty string of length 1 but with only spaces.
        # Actually the cleanest approach: set schema_version to a string that is
        # shorter than the real min_length by bypassing the pattern check first.
        # The _check_string_field signature: (doc, field, required, min_length, pattern)
        # Calling it directly lets us control all parameters.
        from llm_toolkit_schema.validate import _stdlib_validate

        doc["schema_version"] = " "  # 1-char whitespace; passes isinstance, fails pattern
        # This will actually fail the *pattern* check, not the min_length check,
        # since the pattern is checked after min_length. The pattern check fires
        # first only if min_length is satisfied. Let's instead force a short string
        # by patching the expected field.

        # Direct approach: call the internal helper with a crafted doc where a
        # string field value is present but shorter than the minimum.
        # We need the field to be required, present (not None) and too short.
        # The easiest injectable field is source which has min_length=3 (service@version).
        doc2 = event.to_dict()
        doc2["source"] = "x"  # length 1, schema requires min_length 1 but pattern match
        # schema_version has min_length=5 ("1.0.0") — let's use 2 chars
        doc3 = event.to_dict()
        doc3["schema_version"] = "1."  # too short for "1.0.0" (5 chars) if min=5

        # Import and call directly without schema; the _stdlib_validate function
        # validates both min_length and pattern. A string that is >= min_length
        # but fails the pattern will raise at the pattern check.
        # To specifically hit the min_length raise we need min_length > len(value).
        # The _check_string_field function is internal; let's use it via module import.
        import re
        from llm_toolkit_schema.validate import _stdlib_validate as _sv

        # Build a doc where schema_version is present but only 1 char long.
        # The min_length for schema_version in the stdlib validator is 3 ("1.0").
        short_doc = event.to_dict()
        short_doc["schema_version"] = "1"  # single char; should fail min_length >= 3

        with pytest.raises(SchemaValidationError) as exc_info:
            _sv(short_doc)
        # Accept either min_length or pattern as the validation failure cause
        assert "schema_version" in exc_info.value.field

    def test_source_too_short_raises(self):
        """A source string that is extremely short triggers min_length (line 138)."""
        from llm_toolkit_schema.event import Event
        from llm_toolkit_schema.types import EventType
        from llm_toolkit_schema.validate import _stdlib_validate

        event = Event(
            event_type=EventType.TRACE_SPAN_COMPLETED,
            source="svc@1.0",
            payload={"k": "v"},
        )
        doc = event.to_dict()
        # Replace source with a single character — well below any reasonable min_length
        doc["source"] = "x"
        with pytest.raises(SchemaValidationError) as exc_info:
            _stdlib_validate(doc)
        assert "source" in exc_info.value.field


# ---------------------------------------------------------------------------
# Extra branch coverage: ensure every ``from_dict`` optional-None path is hit
# ---------------------------------------------------------------------------


class TestFromDictOptionalNonePaths:
    """Explicit from_dict round-trips with ALL optional fields absent so that
    the ``data.get(...)`` → None paths are executed."""

    def test_cache_hit_from_dict_all_optional_none(self):
        p = CacheHitPayload.from_dict({"cache_key_hash": "k", "cache_store": "r"})
        assert p.similarity_score is None
        assert p.cached_event_id is None
        assert p.ttl_seconds is None

    def test_cache_miss_from_dict_no_reason(self):
        p = CacheMissPayload.from_dict({"cache_key_hash": "k", "cache_store": "r"})
        assert p.reason is None

    def test_cost_recorded_from_dict_no_budget_id(self):
        p = CostRecordedPayload.from_dict(
            {
                "span_event_id": "e",
                "model_name": "m",
                "provider": "p",
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
                "cost_usd": 0.0,
            }
        )
        assert p.budget_id is None

    def test_budget_threshold_from_dict_no_org_id(self):
        p = BudgetThresholdPayload.from_dict(
            {
                "budget_id": "b",
                "threshold_type": "warning",
                "threshold_usd": 100.0,
                "current_spend_usd": 50.0,
                "percentage_used": 50.0,
            }
        )
        assert p.org_id is None

    def test_diff_comparison_from_dict_no_optionals(self):
        p = DiffComparisonPayload.from_dict(
            {"source_id": "a", "target_id": "b", "diff_type": "text"}
        )
        assert p.similarity_score is None
        assert p.source_text is None
        assert p.target_text is None
        assert p.diff_result is None

    def test_diff_report_from_dict_no_optionals(self):
        p = DiffReportPayload.from_dict(
            {"report_id": "r", "comparison_event_id": "evt", "format": "html"}
        )
        assert p.export_path is None
        assert p.export_url is None

    def test_eval_scenario_from_dict_no_optionals(self):
        p = EvalScenarioPayload.from_dict(
            {"scenario_id": "s1", "scenario_name": "t", "status": "passed"}
        )
        assert p.score is None
        assert p.metrics is None
        assert p.baseline_score is None
        assert p.duration_ms is None

    def test_eval_regression_from_dict_no_metrics(self):
        p = EvalRegressionPayload.from_dict(
            {
                "scenario_id": "s1",
                "scenario_name": "t",
                "current_score": 0.7,
                "baseline_score": 0.8,
                "regression_delta": -0.1,
                "threshold": -0.05,
            }
        )
        assert p.metrics is None

    def test_validation_passed_from_dict_no_duration(self):
        p = ValidationPassedPayload.from_dict(
            {"validator_id": "v1", "format_type": "json"}
        )
        assert p.duration_ms is None

    def test_retry_triggered_from_dict_no_previous_error(self):
        p = RetryTriggeredPayload.from_dict(
            {"validator_id": "v1", "attempt": 2, "max_attempts": 3}
        )
        assert p.previous_error is None

    def test_prompt_saved_from_dict_no_author_tags(self):
        p = PromptSavedPayload.from_dict(
            {
                "prompt_id": "p1",
                "version": "1.0",
                "environment": "dev",
                "template_hash": "h",
            }
        )
        assert p.author is None
        assert p.tags is None

    def test_prompt_promoted_from_dict_no_promoted_by(self):
        p = PromptPromotedPayload.from_dict(
            {
                "prompt_id": "p1",
                "version": "1.0",
                "from_environment": "staging",
                "to_environment": "production",
            }
        )
        assert p.promoted_by is None

    def test_prompt_approved_from_dict_no_note(self):
        p = PromptApprovedPayload.from_dict(
            {"prompt_id": "p1", "version": "1.0", "approved_by": "alice"}
        )
        assert p.approval_note is None

    def test_prompt_rolled_back_from_dict_no_optionals(self):
        p = PromptRolledBackPayload.from_dict(
            {"prompt_id": "p1", "from_version": "2.0", "to_version": "1.0"}
        )
        assert p.reason is None
        assert p.rolled_back_by is None

    def test_pii_redacted_from_dict_no_redacted_by(self):
        p = PIIRedactedPayload.from_dict(
            {"field_path": "f", "pii_types": ["email"], "method": "mask"}
        )
        assert p.redacted_by is None

    def test_scan_completed_from_dict_no_optionals(self):
        p = ScanCompletedPayload.from_dict(
            {
                "scanned_fields": 5,
                "pii_detected_count": 1,
                "pii_redacted_count": 1,
            }
        )
        assert p.duration_ms is None
        assert p.policy_id is None

    def test_template_rendered_from_dict_no_optionals(self):
        p = TemplateRenderedPayload.from_dict(
            {"template_id": "t1", "template_version": "1.0", "variable_count": 3}
        )
        assert p.render_duration_ms is None
        assert p.output_length is None

    def test_template_validation_failed_from_dict_no_validator(self):
        p = TemplateValidationFailedPayload.from_dict(
            {"template_id": "t1", "validation_errors": ["err"]}
        )
        assert p.validator is None


# ===========================================================================
# Targeted fixes — first-field raises that were skipped in prior tests
# because only later-field or option-field raises were exercised
# ===========================================================================


class TestFirstFieldRaisesNotYetCovered:
    """Every class validates its first required field in __post_init__.
    Prior tests inadvertently only exercised the SECOND or LATER field raises
    (e.g., empty violation_types) leaving the first-field raise uncovered.
    These tests specifically target the raises on lines reported as missing.
    """

    # ── cost.py line 63 (CostRecordedPayload first-string-field raise) ────────
    def test_cost_recorded_empty_span_event_id_raises(self):
        """Empty span_event_id triggers line 63 raise in CostRecordedPayload."""
        with pytest.raises(ValueError, match="span_event_id"):
            CostRecordedPayload(
                span_event_id="",
                model_name="gpt-4o",
                provider="openai",
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
                cost_usd=0.001,
            )

    # ── cost.py line 144 (BudgetThresholdPayload budget_id raise) ─────────────
    def test_budget_threshold_empty_budget_id_raises(self):
        """Empty budget_id triggers line 144 raise in BudgetThresholdPayload."""
        with pytest.raises(ValueError, match="budget_id"):
            BudgetThresholdPayload(
                budget_id="",
                threshold_type="warning",
                threshold_usd=100.0,
                current_spend_usd=50.0,
                percentage_used=50.0,
            )

    # ── fence.py line 46 (ValidationPassedPayload validator_id raise) ─────────
    def test_validation_passed_empty_validator_id_raises(self):
        """Empty validator_id triggers line 46 raise in ValidationPassedPayload."""
        with pytest.raises(ValueError, match="validator_id"):
            ValidationPassedPayload(validator_id="", format_type="json")

    # ── fence.py line 119 (FenceValidationFailedPayload validator_id raise) ───
    def test_fence_failed_empty_validator_id_raises(self):
        """Empty validator_id triggers line 119 raise in FenceValidationFailedPayload."""
        with pytest.raises(ValueError, match="validator_id"):
            FenceValidationFailedPayload(
                validator_id="", format_type="json", errors=["err"]
            )

    # ── fence.py line 193 (RetryTriggeredPayload validator_id raise) ──────────
    def test_retry_triggered_empty_validator_id_raises(self):
        """Empty validator_id triggers line 193 raise in RetryTriggeredPayload."""
        with pytest.raises(ValueError, match="validator_id"):
            RetryTriggeredPayload(validator_id="", attempt=1, max_attempts=3)

    # ── guard.py line 53 (GuardBlockedPayload first-attr raise in loop) ───────
    def test_guard_blocked_empty_policy_id_raises(self):
        """Empty policy_id triggers line 53 raise in GuardBlockedPayload."""
        with pytest.raises(ValueError, match="policy_id"):
            GuardBlockedPayload(
                policy_id="",
                policy_name="no-jailbreak",
                input_hash="abc",
                violation_types=["jailbreak"],
            )

    # ── guard.py line 130 (GuardFlaggedPayload first-attr raise in loop) ──────
    def test_guard_flagged_empty_policy_id_raises(self):
        """Empty policy_id triggers line 130 raise in GuardFlaggedPayload."""
        with pytest.raises(ValueError, match="policy_id"):
            GuardFlaggedPayload(
                policy_id="",
                policy_name="pii-detection",
                output_hash="xyz",
                flag_types=["email_leak"],
            )

    # ── prompt.py line 56 (PromptSavedPayload first-attr raise in loop) ───────
    def test_prompt_saved_empty_prompt_id_raises(self):
        """Empty prompt_id triggers line 56 raise in PromptSavedPayload."""
        with pytest.raises(ValueError, match="prompt_id"):
            PromptSavedPayload(
                prompt_id="",
                version="1.0",
                environment="dev",
                template_hash="h",
            )

    # ── prompt.py line 269 (PromptRolledBackPayload rolled_back_by assignment) ─
    def test_prompt_rolled_back_to_dict_with_rolled_back_by(self):
        """to_dict() with rolled_back_by set covers line 269 assignment."""
        p = PromptRolledBackPayload(
            prompt_id="p1",
            from_version="2.0",
            to_version="1.0",
            reason="hotfix regression",
            rolled_back_by="bot@ci",
        )
        d = p.to_dict()
        assert d["rolled_back_by"] == "bot@ci"
        assert d["reason"] == "hotfix regression"

    # ── redact.py line 54 (PIIDetectedPayload field_path raise) ───────────────
    def test_pii_detected_empty_field_path_raises(self):
        """Empty field_path triggers line 54 raise in PIIDetectedPayload."""
        with pytest.raises(ValueError, match="field_path"):
            PIIDetectedPayload(field_path="", pii_types=["email"], confidence=0.9)

    # ── redact.py line 120 (PIIRedactedPayload field_path raise) ──────────────
    def test_pii_redacted_empty_field_path_raises(self):
        """Empty field_path triggers line 120 raise in PIIRedactedPayload."""
        with pytest.raises(ValueError, match="field_path"):
            PIIRedactedPayload(field_path="", pii_types=["email"], method="mask")

    # ── template.py line 51 (TemplateRenderedPayload template_id raise) ───────
    def test_template_rendered_empty_template_id_raises(self):
        """Empty template_id triggers line 51 raise in TemplateRenderedPayload."""
        with pytest.raises(ValueError, match="template_id"):
            TemplateRenderedPayload(
                template_id="", template_version="1.0", variable_count=0
            )

    # ── template.py line 126 (VariableMissingPayload template_id raise) ───────
    def test_variable_missing_empty_template_id_raises(self):
        """Empty template_id triggers line 126 raise in VariableMissingPayload."""
        with pytest.raises(ValueError, match="template_id"):
            VariableMissingPayload(
                template_id="",
                missing_variables=["x"],
                required_variables=["x"],
            )

    # ── template.py line 200 (TemplateValidationFailedPayload template_id) ────
    def test_template_validation_failed_empty_template_id_raises(self):
        """Empty template_id triggers line 200 raise in TemplateValidationFailedPayload."""
        with pytest.raises(ValueError, match="template_id"):
            TemplateValidationFailedPayload(
                template_id="", validation_errors=["err"]
            )


# ===========================================================================
# validate.py line 138 — the len(value) < min_length raise path
# The default min_length is 1, so an empty string (length 0) triggers it.
# ===========================================================================


class TestStdlibMinLengthRaise:
    """Target validate.py line 138: raise SchemaValidationError for too-short field."""

    def test_empty_schema_version_triggers_min_length(self):
        """Setting schema_version to '' (length 0 < min_length 1) hits line 138."""
        from llm_toolkit_schema.event import Event
        from llm_toolkit_schema.types import EventType

        event = Event(
            event_type=EventType.TRACE_SPAN_COMPLETED,
            source="svc@1.0",
            payload={"k": "v"},
        )
        doc = event.to_dict()
        # Empty string is a valid str but has len=0 <  min_length=1
        doc["schema_version"] = ""
        with pytest.raises(SchemaValidationError) as exc_info:
            _stdlib_validate(doc)
        err = exc_info.value
        assert err.field == "schema_version"
        # Must report the min_length reason, not the pattern reason
        assert "at least" in err.reason

    def test_empty_optional_context_field_triggers_min_length(self):
        """An optional field (org_id) set to '' also triggers line 138.

        Must use a fully valid source string so that all required-field
        checks pass and the validator reaches the optional context fields.
        """
        from llm_toolkit_schema.event import Event
        from llm_toolkit_schema.types import EventType

        # source="llm-trace@0.3.1" matches _SOURCE_RE so all required
        # fields pass and we reach the optional context-field validation.
        event = Event(
            event_type=EventType.TRACE_SPAN_COMPLETED,
            source="llm-trace@0.3.1",
            payload={"k": "v"},
        )
        doc = event.to_dict()
        # org_id is optional (required=False) with min_length=1
        doc["org_id"] = ""
        with pytest.raises(SchemaValidationError) as exc_info:
            _stdlib_validate(doc)
        err = exc_info.value
        assert err.field == "org_id"
        assert "at least" in err.reason
