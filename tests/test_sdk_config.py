"""Tests for tracium.config — TraciumConfig, configure(), get_config(), env vars.

Phase 1 SDK coverage target.
"""

from __future__ import annotations

import os
import threading
from typing import Generator

import pytest

from tracium.config import TraciumConfig, configure, get_config


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _restore_config() -> Generator[None, None, None]:
    """Restore the global config after every test."""
    cfg = get_config()
    saved = {k: getattr(cfg, k) for k in vars(cfg)}
    yield
    for k, v in saved.items():
        setattr(cfg, k, v)


# ===========================================================================
# TraciumConfig defaults
# ===========================================================================


@pytest.mark.unit
class TestTraciumConfigDefaults:
    def test_default_exporter(self) -> None:
        cfg = TraciumConfig()
        assert cfg.exporter == "console"

    def test_default_endpoint_is_none(self) -> None:
        cfg = TraciumConfig()
        assert cfg.endpoint is None

    def test_default_org_id_is_none(self) -> None:
        cfg = TraciumConfig()
        assert cfg.org_id is None

    def test_default_service_name(self) -> None:
        cfg = TraciumConfig()
        assert cfg.service_name == "unknown-service"

    def test_default_env(self) -> None:
        cfg = TraciumConfig()
        assert cfg.env == "production"

    def test_default_service_version(self) -> None:
        cfg = TraciumConfig()
        assert cfg.service_version == "0.0.0"

    def test_default_signing_key_is_none(self) -> None:
        cfg = TraciumConfig()
        assert cfg.signing_key is None

    def test_default_redaction_policy_is_none(self) -> None:
        cfg = TraciumConfig()
        assert cfg.redaction_policy is None

    def test_custom_construction(self) -> None:
        cfg = TraciumConfig(
            exporter="jsonl",
            endpoint="./events.jsonl",
            service_name="my-agent",
            env="staging",
        )
        assert cfg.exporter == "jsonl"
        assert cfg.endpoint == "./events.jsonl"
        assert cfg.service_name == "my-agent"
        assert cfg.env == "staging"


# ===========================================================================
# configure() function
# ===========================================================================


@pytest.mark.unit
class TestConfigureFunction:
    def test_configure_no_args_is_noop(self) -> None:
        before = get_config().service_name
        configure()
        assert get_config().service_name == before

    def test_configure_sets_exporter(self) -> None:
        configure(exporter="jsonl")
        assert get_config().exporter == "jsonl"

    def test_configure_sets_service_name(self) -> None:
        configure(service_name="test-service")
        assert get_config().service_name == "test-service"

    def test_configure_sets_endpoint(self) -> None:
        configure(endpoint="./test.jsonl")
        assert get_config().endpoint == "./test.jsonl"

    def test_configure_sets_org_id(self) -> None:
        configure(org_id="org_abc123")
        assert get_config().org_id == "org_abc123"

    def test_configure_sets_env(self) -> None:
        configure(env="staging")
        assert get_config().env == "staging"

    def test_configure_sets_service_version(self) -> None:
        configure(service_version="1.2.3")
        assert get_config().service_version == "1.2.3"

    def test_configure_sets_signing_key(self) -> None:
        configure(signing_key="abc123==")
        assert get_config().signing_key == "abc123=="

    def test_configure_multiple_fields(self) -> None:
        configure(exporter="console", service_name="foo", env="dev")
        cfg = get_config()
        assert cfg.exporter == "console"
        assert cfg.service_name == "foo"
        assert cfg.env == "dev"

    def test_configure_unknown_key_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown tracium configuration key"):
            configure(unknown_key="value")

    def test_configure_multiple_calls_accumulate(self) -> None:
        configure(exporter="jsonl")
        configure(service_name="chained")
        cfg = get_config()
        assert cfg.exporter == "jsonl"
        assert cfg.service_name == "chained"

    def test_configure_resets_exporter_cache(self) -> None:
        """configure() should invalidate the _stream exporter cache."""
        configure(exporter="console")
        # Calling configure again should not raise.
        configure(exporter="console")
        assert get_config().exporter == "console"


# ===========================================================================
# get_config() returns live singleton
# ===========================================================================


@pytest.mark.unit
class TestGetConfig:
    def test_returns_same_instance(self) -> None:
        cfg1 = get_config()
        cfg2 = get_config()
        assert cfg1 is cfg2

    def test_mutation_reflected_immediately(self) -> None:
        cfg = get_config()
        cfg.service_name = "direct-mutation"
        assert get_config().service_name == "direct-mutation"


# ===========================================================================
# Environment variable loading
# ===========================================================================


@pytest.mark.unit
class TestEnvVars:
    def test_tracium_exporter_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRACIUM_EXPORTER", "jsonl")
        # Force re-import by directly calling _load_from_env
        import tracium.config as config_mod
        old = config_mod._config.exporter
        config_mod._load_from_env()
        assert config_mod._config.exporter == "jsonl"
        # Restore
        config_mod._config.exporter = old

    def test_tracium_service_name_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRACIUM_SERVICE_NAME", "env-service")
        import tracium.config as config_mod
        old = config_mod._config.service_name
        config_mod._load_from_env()
        assert config_mod._config.service_name == "env-service"
        config_mod._config.service_name = old

    def test_tracium_endpoint_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRACIUM_ENDPOINT", "http://localhost:4317")
        import tracium.config as config_mod
        old = config_mod._config.endpoint
        config_mod._load_from_env()
        assert config_mod._config.endpoint == "http://localhost:4317"
        config_mod._config.endpoint = old

    def test_tracium_org_id_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRACIUM_ORG_ID", "org_test")
        import tracium.config as config_mod
        old = config_mod._config.org_id
        config_mod._load_from_env()
        assert config_mod._config.org_id == "org_test"
        config_mod._config.org_id = old

    def test_tracium_env_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRACIUM_ENV", "development")
        import tracium.config as config_mod
        old = config_mod._config.env
        config_mod._load_from_env()
        assert config_mod._config.env == "development"
        config_mod._config.env = old

    def test_tracium_service_version_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRACIUM_SERVICE_VERSION", "2.0.0")
        import tracium.config as config_mod
        old = config_mod._config.service_version
        config_mod._load_from_env()
        assert config_mod._config.service_version == "2.0.0"
        config_mod._config.service_version = old

    def test_tracium_signing_key_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRACIUM_SIGNING_KEY", "test_key==")
        import tracium.config as config_mod
        old = config_mod._config.signing_key
        config_mod._load_from_env()
        assert config_mod._config.signing_key == "test_key=="
        config_mod._config.signing_key = old

    def test_unset_env_vars_do_not_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TRACIUM_SERVICE_NAME", raising=False)
        import tracium.config as config_mod
        config_mod._config.service_name = "my-service"
        config_mod._load_from_env()
        assert config_mod._config.service_name == "my-service"


# ===========================================================================
# Thread safety
# ===========================================================================


@pytest.mark.unit
class TestConfigureThreadSafety:
    def test_concurrent_configure_does_not_raise(self) -> None:
        errors = []

        def worker(n: int) -> None:
            try:
                configure(service_name=f"worker-{n}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        # config should have a valid service_name (one of the workers' values)
        assert get_config().service_name.startswith("worker-")
