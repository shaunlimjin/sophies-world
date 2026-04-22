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