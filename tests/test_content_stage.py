"""Tests for content_stage provider injection."""
from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest

from scripts.content_stage import run_content_provider, run_packet_synthesis_provider


def test_run_content_provider_uses_provider(monkeypatch):
    mock_provider = MagicMock()
    mock_provider.generate.return_value = {"result": '{"test": true}'}

    monkeypatch.setattr("scripts.content_stage.parse_content_output", lambda raw, repo=None: {"test": True})

    result = run_content_provider("prompt", Path("/tmp"), provider=mock_provider)
    mock_provider.generate.assert_called_once()


def test_run_packet_synthesis_provider_uses_provider(monkeypatch):
    mock_provider = MagicMock()
    mock_provider.generate.return_value = {"result": '{"test": true}'}

    monkeypatch.setattr("scripts.content_stage.parse_content_output", lambda raw, repo=None: {"test": True})

    result = run_packet_synthesis_provider("prompt", Path("/tmp"), provider=mock_provider)
    mock_provider.generate.assert_called_once()