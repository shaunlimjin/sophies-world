import subprocess
from pathlib import Path
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


def test_openai_compatible_loads_api_key_from_env_var(tmp_path, monkeypatch):
    """When api_key_env is in config, the named env var is read for the key."""
    monkeypatch.setenv("MY_TEST_KEY", "secret-value")
    p = OpenAICompatibleProvider({
        "provider": "openai_compatible",
        "model": "test-model",
        "base_url": "https://example.com/v1",
        "api_key_env": "MY_TEST_KEY",
    }, repo_root=tmp_path)
    assert p.client.api_key == "secret-value"


def test_openai_compatible_no_minimax_url_special_case(tmp_path, monkeypatch):
    """Without api_key_env, MiniMax URL no longer triggers implicit key loading."""
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    p = OpenAICompatibleProvider({
        "provider": "openai_compatible",
        "model": "MiniMax-M2",
        "base_url": "https://api.minimax.io/v1",
    }, repo_root=tmp_path)
    assert p.client.api_key == "not-needed"


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


def test_make_provider_passes_repo_root():
    fake_cls = MagicMock(return_value=MagicMock(name="claude"))
    with patch.dict("scripts.providers.model_providers.PROVIDER_MAP", {"claude": fake_cls}, clear=False):
        make_provider({"provider": "claude", "model": "sonnet"}, repo_root=Path("/tmp/repo"))
        fake_cls.assert_called_once_with({"provider": "claude", "model": "sonnet"}, repo_root=Path("/tmp/repo"))


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
    mock_result.stdout = '{"result": "test output"}'
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
    mock_result.stdout = '{"result": "web search output"}'
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
    mock_success.stdout = '{"result": "recovered"}'
    mock_success.stderr = ""

    with patch("subprocess.run", side_effect=[mock_fail, mock_success]):
        with patch("time.sleep"):
            result = provider.generate("test prompt", max_retries=1, base_delay=0.01)
            assert result["result"] == "recovered"


def test_openai_compatible_minimax_key_missing_raises():
    """OpenAICompatibleProvider raises when api_key_env is set but the env var is absent."""
    with patch.dict("os.environ", {}, clear=True):
        with patch(
            "scripts.providers.model_providers._api_key.load_api_key",
            side_effect=RuntimeError("MINIMAX_API_KEY not found in .env or environment"),
        ):
            try:
                OpenAICompatibleProvider(
                    {"model": "MiniMax-Text-01", "base_url": "https://api.minimax.io/v1", "api_key_env": "MINIMAX_API_KEY"},
                    repo_root=None,
                )
                raise AssertionError("Expected RuntimeError")
            except RuntimeError as exc:
                assert "MINIMAX_API_KEY" in str(exc)


def test_openai_compatible_uses_env_key_for_minimax():
    """When api_key_env is set, the env var is loaded."""
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
                    "api_key_env": "MINIMAX_API_KEY",
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
            assert "exit 1" in result["error"]
            assert result["stderr"] == ""
            assert result["stdout"] == ""


def test_claude_provider_generate_returns_stderr_details_on_exit_failure():
    provider = ClaudeProvider({"model": "sonnet"})
    mock_fail = MagicMock()
    mock_fail.returncode = 1
    mock_fail.stdout = ""
    mock_fail.stderr = "temporary upstream failure"

    with patch("subprocess.run", return_value=mock_fail):
        with patch("time.sleep"):
            result = provider.generate("test prompt", max_retries=0, base_delay=0.01)
            assert result["result"] == ""
            assert result["returncode"] == 1
            assert "temporary upstream failure" in result["error"]
            assert result["stderr"] == "temporary upstream failure"


def test_claude_provider_generate_returns_raw_stdout_on_parse_error():
    provider = ClaudeProvider({"model": "sonnet"})
    mock_bad = MagicMock()
    mock_bad.returncode = 0
    mock_bad.stdout = '{"unexpected": true}'
    mock_bad.stderr = ""

    with patch("subprocess.run", return_value=mock_bad):
        with patch("time.sleep"):
            result = provider.generate("test prompt", max_retries=0, base_delay=0.01)
            assert result["result"] == ""
            assert "parse_error" in result["error"]
            assert result["stdout"] == '{"unexpected": true}'
