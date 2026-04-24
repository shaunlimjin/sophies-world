"""Tests for OpenAIAgenticProvider."""

import json
from unittest.mock import MagicMock, patch

import pytest
from scripts.providers.model_providers.openai_agentic import OpenAIAgenticProvider


def test_openai_agentic_requires_model():
    with pytest.raises(ValueError, match="requires 'model'"):
        OpenAIAgenticProvider({})


def test_openai_agentic_name():
    provider = OpenAIAgenticProvider({"model": "test-model"})
    assert provider.name == "openai_agentic"


def test_openai_agentic_generate_no_tools():
    provider = OpenAIAgenticProvider({
        "model": "test-model",
        "api_key": "test-key"
    })
    
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "direct response"
    mock_message.tool_calls = None
    mock_response.choices = [MagicMock(message=mock_message, finish_reason="stop")]
    
    with patch("openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        provider.client = mock_client
        result = provider.generate("test prompt")
        
        assert result["result"] == "direct response"
        mock_client.chat.completions.create.assert_called_once()
        kwargs = mock_client.chat.completions.create.call_args[1]
        assert "tools" not in kwargs


def test_openai_agentic_generate_with_tools():
    provider = OpenAIAgenticProvider({
        "model": "test-model",
        "api_key": "test-key"
    })
    
    # Mock BraveSearchClient
    mock_brave = MagicMock()
    mock_brave.search.return_value = [{"title": "Test News", "snippet": "Test snippet"}]
    provider._brave_client = mock_brave
    
    # First response: tool call
    mock_response1 = MagicMock()
    mock_tc = MagicMock()
    mock_tc.id = "call_123"
    mock_tc.function.name = "WebSearch"
    mock_tc.function.arguments = json.dumps({"query": "latest news"})
    
    mock_message1 = MagicMock()
    mock_message1.content = None
    mock_message1.tool_calls = [mock_tc]
    mock_response1.choices = [MagicMock(message=mock_message1, finish_reason="tool_calls")]
    
    # Second response: final answer
    mock_response2 = MagicMock()
    mock_message2 = MagicMock()
    mock_message2.content = "The latest news is test news."
    mock_message2.tool_calls = None
    mock_response2.choices = [MagicMock(message=mock_message2, finish_reason="stop")]
    
    with patch("openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [mock_response1, mock_response2]
        mock_openai_class.return_value = mock_client
        
        provider.client = mock_client
        result = provider.generate("test prompt", allowed_tools="WebSearch")
        
        assert result["result"] == "The latest news is test news."
        assert mock_client.chat.completions.create.call_count == 2
        mock_brave.search.assert_called_once_with(q="latest news", count=5)


def test_assistant_message_is_dict_in_multiturn():
    """Second API call must receive a plain dict for the assistant turn, not an SDK Pydantic object."""
    provider = OpenAIAgenticProvider({"model": "test-model", "api_key": "test-key"})

    mock_brave = MagicMock()
    mock_brave.search.return_value = [{"title": "T", "url": "U", "snippet": "S"}]
    provider._brave_client = mock_brave

    mock_tc = MagicMock()
    mock_tc.id = "call_abc"
    mock_tc.type = "function"
    mock_tc.function.name = "WebSearch"
    mock_tc.function.arguments = json.dumps({"query": "news"})

    mock_msg1 = MagicMock()
    mock_msg1.content = None
    mock_msg1.tool_calls = [mock_tc]

    mock_msg2 = MagicMock()
    mock_msg2.content = "Answer."
    mock_msg2.tool_calls = None

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=mock_msg1, finish_reason="tool_calls")]),
        MagicMock(choices=[MagicMock(message=mock_msg2, finish_reason="stop")]),
    ]
    provider.client = mock_client

    provider.generate("test prompt", allowed_tools="WebSearch")

    second_call_messages = mock_client.chat.completions.create.call_args_list[1][1]["messages"]
    # [user_dict, assistant_msg, tool_result_dict]
    assistant_msg = second_call_messages[1]
    assert isinstance(assistant_msg, dict), "assistant message must be a plain dict, not an SDK Pydantic object"
    assert assistant_msg["role"] == "assistant"
    assert "tool_calls" in assistant_msg
