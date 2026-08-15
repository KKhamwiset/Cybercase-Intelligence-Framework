import unittest

from pydantic import ValidationError

from app.config import Settings
from app.services.llm.core_llm import (
    CoreLlmConfigurationError,
    resolve_core_llm_target,
)


class CoreLlmProviderTests(unittest.TestCase):
    @staticmethod
    def _settings(
        *,
        provider: str = "openrouter",
        openrouter_key: str = "",
        anthropic_key: str = "",
    ) -> Settings:
        return Settings(
            _env_file=None,
            core_llm_provider=provider,
            openrouter_cybercase=openrouter_key,
            anthropic_api_key=anthropic_key,
        )

    def test_default_provider_is_openrouter(self) -> None:
        self.assertEqual(
            Settings.model_fields["core_llm_provider"].default,
            "openrouter",
        )

    def test_openrouter_target_uses_dedicated_secret_and_bearer_auth(self) -> None:
        target = resolve_core_llm_target(
            "claude-feature-model",
            configured_settings=self._settings(openrouter_key="core-secret"),
        )

        self.assertEqual(target.provider, "openrouter")
        self.assertEqual(target.model, "openai/gpt-5.6-luna")
        self.assertEqual(target.messages_url, "https://openrouter.ai/api/v1/messages")
        self.assertEqual(target.headers["Authorization"], "Bearer core-secret")
        self.assertNotIn("x-api-key", target.headers)

    def test_openrouter_target_resolves_aliases(self) -> None:
        target = resolve_core_llm_target(
            "sonnet",
            configured_settings=self._settings(openrouter_key="core-secret"),
        )
        self.assertEqual(target.model, "anthropic/claude-3.5-sonnet")

    def test_anthropic_target_preserves_feature_model_and_native_auth(self) -> None:
        target = resolve_core_llm_target(
            "claude-feature-model",
            configured_settings=self._settings(
                provider="anthropic",
                anthropic_key="anthropic-secret",
            ),
        )

        self.assertEqual(target.provider, "anthropic")
        self.assertEqual(target.model, "claude-feature-model")
        self.assertEqual(target.messages_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(target.headers["x-api-key"], "anthropic-secret")
        self.assertNotIn("Authorization", target.headers)

    def test_invalid_provider_is_rejected_by_settings(self) -> None:
        with self.assertRaises(ValidationError):
            self._settings(provider="invalid")

    def test_selected_provider_missing_key_has_no_fallback(self) -> None:
        configured = self._settings(
            provider="openrouter",
            openrouter_key="",
            anthropic_key="available-but-not-selected",
        )

        with self.assertRaisesRegex(
            CoreLlmConfigurationError,
            "OPENROUTER_CYBERCASE",
        ):
            resolve_core_llm_target(
                "claude-feature-model",
                configured_settings=configured,
            )

    def test_openrouter_api_key_cannot_satisfy_production_target(self) -> None:
        configured = self._settings(provider="openrouter", openrouter_key="")
        self.assertFalse(hasattr(configured, "openrouter_api_key"))

        with self.assertRaises(CoreLlmConfigurationError):
            resolve_core_llm_target(
                "claude-feature-model",
                configured_settings=configured,
            )


if __name__ == "__main__":
    unittest.main()
