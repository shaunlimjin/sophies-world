import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import novelty_gate


def _issue(issue_date, title, body, url="https://example.com/story", section="weird_but_true"):
    return {
        "issue_date": issue_date,
        "child_id": "sophie",
        "sections": [
            {
                "id": section,
                "items": [
                    {
                        "title": title,
                        "body": body,
                        "links": [{"label": "Read", "url": url}],
                    }
                ],
            }
        ],
    }


def test_extract_issue_items_reads_fact_titles_bodies_and_links():
    issue = _issue(
        "2026-05-16",
        "Geckos Never Blink",
        "Geckos use their tongues to lick their eyes clean.",
    )
    items = novelty_gate.extract_issue_items(issue)
    assert len(items) == 1
    assert items[0].section_id == "weird_but_true"
    assert items[0].title == "Geckos Never Blink"
    assert "lick their eyes" in items[0].text
    assert items[0].urls == ("https://example.com/story",)


def test_check_issue_novelty_flags_gecko_repeat_from_prior_fact():
    previous = novelty_gate.extract_issue_items(
        _issue(
            "2026-05-03",
            "Geckos can't blink — so they lick their eyeballs",
            "Geckos do not have eyelids, so they clean dust by licking their eyeballs.",
        )
    )
    current = _issue(
        "2026-05-16",
        "Geckos Never Blink",
        "Geckos cannot blink because they do not have eyelids. They lick their eyes clean.",
    )
    findings = novelty_gate.check_issue_novelty(current, previous)
    assert any(f.severity == "error" and "Geckos" in f.current_title for f in findings)


def test_check_issue_novelty_ignores_generic_collection_url_reuse_when_topic_is_fresh():
    generic = "https://kids.nationalgeographic.com/weird-but-true/article/animals"
    previous = novelty_gate.extract_issue_items(
        _issue("2026-05-03", "Geckos Can't Blink", "Geckos lick their eyes clean.", url=generic)
    )
    current = _issue(
        "2026-05-16",
        "Octopus Hearts",
        "An octopus has three hearts, and two help pump blood to the gills.",
        url=generic,
    )
    findings = novelty_gate.check_issue_novelty(current, previous)
    assert [f for f in findings if f.severity == "error"] == []


def test_assert_issue_novelty_loads_recent_artifacts_and_raises(tmp_path):
    issues_dir = tmp_path / "artifacts" / "issues"
    issues_dir.mkdir(parents=True)
    prior = _issue(
        "2026-05-09",
        "Meet the Kid Who Earned $10,000!",
        "A kid earned ten thousand dollars by thinking like an entrepreneur.",
        section="money_moves",
    )
    (issues_dir / "sophie-2026-05-09.json").write_text(json.dumps(prior), encoding="utf-8")

    current = _issue(
        "2026-05-16",
        "One Parent's Secret to Kid Entrepreneurs",
        "This parent taught kids entrepreneurship, and the teens made about $10,000 so far.",
        section="money_moves",
    )

    with pytest.raises(ValueError, match="Novelty gate failed"):
        novelty_gate.assert_issue_novelty(current, tmp_path)
