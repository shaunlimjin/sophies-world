from pathlib import Path
from unittest.mock import MagicMock
from scripts.providers.llm_providers import model_rank_candidates


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