import subprocess
from unittest.mock import MagicMock, patch
from scripts.providers.model_providers.base import ModelProvider
from scripts.providers.model_providers.claude import ClaudeProvider
from scripts.providers.model_providers.openai_compatible import OpenAICompatibleProvider


def test_openai_compatible_requires_model():
    try:
        OpenAICompatibleProvider({})
        raise AssertionError("Expected ValueError for missing model")
    except ValueError as exc:
        assert "model" in str(exc).lower()


def test_openai_compatible_name():
    provider = OpenAICompatibleProvider({"model": "llama3"})
    assert provider.name == "openai_compatible"


def test_openai_compatible_generate_success():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="synthesized output"))]

    with patch("scripts.providers.model_providers.openai_compatible.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        from scripts.providers.model_providers.openai_compatible import OpenAICompatibleProvider
        provider = OpenAICompatibleProvider({
            "model": "llama3",
            "base_url": "http://localhost:1234/v1",
            "api_key": "test-key",
        })

        result = provider.generate("test prompt")
        assert result["result"] == "synthesized output"
        mock_client.chat.completions.create.assert_called_once()


from scripts.providers.model_providers import make_provider, PROVIDER_MAP


def test_make_provider_unknown_raises():
    try:
        make_provider({"provider": "nonexistent"})
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "nonexistent" in str(exc)


def test_make_provider_missing_provider_key():
    try:
        make_provider({})
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "provider" in str(exc)


def test_make_provider_claude():
    provider = make_provider({"provider": "claude", "model": "sonnet"})
    assert provider.name == "claude"


def test_make_provider_openai_compatible():
    provider = make_provider({
        "provider": "openai_compatible",
        "model": "llama3",
        "base_url": "http://localhost:1234/v1",
    })
    assert provider.name == "openai_compatible"


def test_model_provider_is_abc():
    try:
        provider = ModelProvider()
        raise AssertionError("ModelProvider cannot be instantiated directly")
    except TypeError:
        pass  # ABC raises TypeError


def test_model_provider_name_property():
    """Subclasses must implement the name property."""
    class DummyProvider(ModelProvider):
        @property
        def name(self):
            return "dummy"

        def generate(self, prompt: str, **kwargs) -> dict:
            return {"result": ""}

    p = DummyProvider({})
    assert p.name == "dummy"


def test_claude_provider_requires_model():
    try:
        ClaudeProvider({})
        raise AssertionError("Expected ValueError for missing model")
    except ValueError as exc:
        assert "model" in str(exc).lower()


def test_claude_provider_name():
    provider = ClaudeProvider({"model": "sonnet"})
    assert provider.name == "claude"


def test_claude_provider_generate_success():
    provider = ClaudeProvider({"model": "sonnet"})
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"result": "test output", "terminal_reason": "completed"}'
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = provider.generate("test prompt")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "--model" in args
        assert "sonnet" in args
        assert result["result"] == "test output"


def test_claude_provider_generate_with_tools_and_max_turns():
    """Mode A calls generate with allowed_tools and max_turns=10."""
    provider = ClaudeProvider({"model": "sonnet"})
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '{"result": "web search output", "terminal_reason": "completed"}'
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        result = provider.generate(
            "search prompt",
            allowed_tools="WebSearch,WebFetch",
            max_turns=10,
        )
        args = mock_run.call_args[0][0]
        assert "--allowedTools" in args
        assert "WebSearch,WebFetch" in args
        idx = args.index("--max-turns")
        assert args[idx + 1] == "10"
        assert result["result"] == "web search output"


def test_claude_provider_generate_retry_on_nonzero_exit():
    provider = ClaudeProvider({"model": "sonnet"})
    mock_fail = MagicMock()
    mock_fail.returncode = 1
    mock_fail.stdout = ""
    mock_fail.stderr = "rate limit"

    mock_success = MagicMock()
    mock_success.returncode = 0
    mock_success.stdout = '{"result": "recovered", "terminal_reason": "completed"}'
    mock_success.stderr = ""

    with patch("subprocess.run", side_effect=[mock_fail, mock_success]):
        with patch("time.sleep"):
            result = provider.generate("test prompt", max_retries=1, base_delay=0.01)
            assert result["result"] == "recovered"


def test_openai_compatible_minimax_key_missing_raises():
    """OpenAICompatibleProvider raises when MINIMAX_API_KEY is absent from .env and env."""
    with patch.dict("os.environ", {}, clear=True):
        with patch(
            "scripts.providers.model_providers.openai_compatible.load_api_key",
            side_effect=RuntimeError("MINIMAX_API_KEY not found in .env or environment"),
        ):
            try:
                OpenAICompatibleProvider(
                    {"model": "MiniMax-Text-01", "base_url": "https://api.minimax.io/v1"},
                    repo_root=None,
                )
                raise AssertionError("Expected RuntimeError")
            except RuntimeError as exc:
                assert "MINIMAX_API_KEY" in str(exc)


def test_openai_compatible_uses_env_key_for_minimax():
    """When base_url contains minimax.io and key is absent, env var is used."""
    with patch.dict("os.environ", {"MINIMAX_API_KEY": "env-secret-key"}):
        with patch(
            "scripts.providers.model_providers.openai_compatible.OpenAI"
        ) as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client

            from scripts.providers.model_providers.openai_compatible import (
                OpenAICompatibleProvider,
            )

            provider = OpenAICompatibleProvider(
                {
                    "model": "MiniMax-Text-01",
                    "base_url": "https://api.minimax.io/v1",
                },
                repo_root=None,
            )

            # Verify OpenAI client was called with the env key
            mock_openai_class.assert_called_once_with(
                base_url="https://api.minimax.io/v1",
                api_key="env-secret-key",
            )


def test_claude_provider_generate_error_on_exhausted_retries():
    provider = ClaudeProvider({"model": "sonnet"})
    mock_fail = MagicMock()
    mock_fail.returncode = 1
    mock_fail.stdout = ""
    mock_fail.stderr = ""

    with patch("subprocess.run", return_value=mock_fail):
        with patch("time.sleep"):
            result = provider.generate("test prompt", max_retries=0, base_delay=0.01)
            assert "error" in result
            assert result["result"] == ""
