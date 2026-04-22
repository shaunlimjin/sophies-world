import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# tests/providers/test_llm_providers.py -> tests/ -> repo root -> scripts/
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from providers.llm_providers import model_rank_candidates


def test_rank_candidates_wires_provider_from_config():
    """rank_candidates passes make_provider result to model_rank_candidates."""
    mock_provider = MagicMock()
    mock_provider.generate.return_value = {
        "result": '[{"index": 0, "title": "Test", "reasons": ["test"]}]'
    }

    with patch("providers.model_providers.make_provider", return_value=mock_provider):
        pool = {
            "sections": [{
                "section_id": "weird_but_true",
                "filtered_candidates": [{"title": "Test", "url": "http://example.com", "domain": "example.com", "snippet": "Test"}]
            }],
            "recent_headlines": []
        }
        config = {
            "profile": {
                "name": "Sophie",
                "age_band": "4th-grade",
                "interests": {"active": []},
                "newsletter": {
                    "generation": {
                        "providers": {
                            "ranking": {"provider": "claude", "model": "sonnet"}
                        }
                    }
                }
            },
            "research": {
                "ranking": {
                    "sections": {"weird_but_true": {"max_ranked": 3}}
                }
            }
        }
        from ranking_stage import rank_candidates
        result = rank_candidates(pool, config, "hosted_model_ranker", Path("/tmp"))
        assert mock_provider.generate.called


def test_model_rank_candidates_accepts_provider():
    mock_provider = MagicMock()
    mock_provider.generate.return_value = {
        "result": '[{"index": 0, "title": "Test", "reasons": ["test"]}]'
    }

    pool = {
        "sections": [
            {
                "section_id": "weird_but_true",
                "filtered_candidates": [
                    {"title": "Test", "url": "http://example.com", "domain": "example.com", "snippet": "Test snippet"}
                ]
            }
        ],
        "recent_headlines": []
    }
    config = {
        "profile": {"name": "Sophie", "age_band": "4th-grade", "interests": {"active": []}},
        "research": {"ranking": {"sections": {"weird_but_true": {"max_ranked": 3}}}}
    }

    repo_root = Path("/tmp/test_sophies_world")
    result = model_rank_candidates(pool, config, repo_root, provider=mock_provider)
    mock_provider.generate.assert_called_once()
    assert "sections" in result


def test_parse_ranker_output_strips_leading_non_json():
    """_parse_ranker_output handles blank lines / warnings before the JSON payload."""
    from providers.llm_providers import _parse_ranker_output

    candidates = [
        {"title": "A", "url": "http://a.com", "domain": "a.com", "snippet": "a"},
        {"title": "B", "url": "http://b.com", "domain": "b.com", "snippet": "b"},
    ]

    # Envelope dict format with leading blank lines and warning
    raw_envelope = """\n\nWARNING: some model message
{"result": '[{"index": 0, "reasons": ["reason A"]}]'}"""
    result = _parse_ranker_output(raw_envelope, candidates)
    assert len(result) == 1
    assert result[0]["title"] == "A"
    assert result[0]["reasons"] == ["reason A"]

    # Direct array string format with leading garbage
    raw_direct = 'some stderr noise\n[{"index": 1, "reasons": ["reason B"]}]'
    result = _parse_ranker_output(raw_direct, candidates)
    assert len(result) == 1
    assert result[0]["title"] == "B"
    assert result[0]["reasons"] == ["reason B"]

    # Pure valid JSON still works
    raw_pure = '{"result": [{"index": 0, "reasons": ["reason C"]}]}''
    result = _parse_ranker_output(raw_pure, candidates)
    assert len(result) == 1
    assert result[0]["reasons"] == ["reason C"]