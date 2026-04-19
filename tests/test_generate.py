import json
import sys
import pytest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import generate
import content_stage
import issue_schema
import render_stage


def test_get_next_issue_number_no_files(tmp_path):
    assert generate.get_next_issue_number(tmp_path) == 1


def test_get_next_issue_number_with_existing(tmp_path):
    (tmp_path / "sophies-world-2026-04-09.html").touch()
    (tmp_path / "sophies-world-2026-04-16.html").touch()
    assert generate.get_next_issue_number(tmp_path) == 3


def test_get_output_path(tmp_path):
    result = generate.get_output_path(tmp_path, date(2026, 4, 23))
    assert result == tmp_path / "sophies-world-2026-04-23.html"


def test_get_recent_headlines_no_previous(tmp_path):
    assert generate.get_recent_headlines(tmp_path, date(2026, 4, 18)) == []


def test_get_recent_headlines_excludes_today(tmp_path):
    (tmp_path / "sophies-world-2026-04-18.html").write_text(
        "<h3>Today's Story</h3>"
    )
    assert generate.get_recent_headlines(tmp_path, date(2026, 4, 18)) == []


def test_get_recent_headlines_returns_previous_h3s(tmp_path):
    (tmp_path / "sophies-world-2026-04-11.html").write_text(
        "<h3>🌍 Big Story One</h3><h3>🎤 K-pop News</h3>"
    )
    result = generate.get_recent_headlines(tmp_path, date(2026, 4, 18))
    assert result == ["🌍 Big Story One", "🎤 K-pop News"]


def test_get_recent_headlines_uses_most_recent(tmp_path):
    (tmp_path / "sophies-world-2026-04-04.html").write_text("<h3>Old Story</h3>")
    (tmp_path / "sophies-world-2026-04-11.html").write_text("<h3>Recent Story</h3>")
    result = generate.get_recent_headlines(tmp_path, date(2026, 4, 18))
    assert result == ["Recent Story"]


def test_idempotent_skips_existing(tmp_path, capsys):
    existing = tmp_path / "sophies-world-2026-04-23.html"
    existing.write_text("<html/>")
    result = generate.check_output_exists(existing)
    assert result is True
    captured = capsys.readouterr()
    assert "already exists" in captured.out


def test_idempotent_proceeds_when_missing(tmp_path):
    path = tmp_path / "sophies-world-2026-04-23.html"
    assert generate.check_output_exists(path) is False


MINIMAL_SECTIONS_YAML = """\
sections:
  weird_but_true:
    title: "🤔 Weird But True"
    goal: "Share 2–3 wild fun facts"
    block_type: fact_list
    content_rules:
      - Facts should be surprising
    link_style: link-purple
    source_preferences:
      - Nat Geo Kids
  world_watch:
    title: "🌍 World Watch"
    goal: "Explain 2 real current events"
    block_type: story_list
    content_rules:
      - Include an analogy
    link_style: link-green
    source_preferences:
      - BBC Newsround
  singapore_spotlight:
    title: "🇸🇬 Singapore Spotlight"
    goal: "Share a Singapore fact"
    block_type: spotlight
    content_rules:
      - Timeless or surprising facts are great
    link_style: link-pink
    source_preferences:
      - Britannica
  usa_corner:
    title: "🇺🇸 USA Corner"
    goal: "Share something about the USA"
    block_type: spotlight
    content_rules:
      - Keep it current
    link_style: link-blue
    source_preferences:
      - Time for Kids
  gymnastics_corner:
    title: "🤸 Gymnastics Corner"
    goal: "Share gymnastics news"
    block_type: interest_feature
    content_rules:
      - Keep it age-appropriate
      - Use .interest-item structure for each item
    link_style: link-rose
    source_preferences:
      - USA Gymnastics
  money_moves:
    title: "💰 Money Moves"
    goal: "Share one money lesson"
    block_type: story_list
    content_rules:
      - Include a money highlight
    link_style: link-amber
    source_preferences:
      - Financial literacy sites for kids
  sophies_challenge:
    title: "🧠 Sophie's Challenge"
    goal: "Present a challenge"
    block_type: challenge
    content_rules:
      - Tie it to World Watch
    link_style: link-orange
    source_preferences:
      - Derived from World Watch
"""

MINIMAL_THEME_YAML = """\
theme_id: default
template_path: scripts/template.html
section_order_mode: profile_driven
"""


def make_config(tmp_path, sophie_yaml, sections_yaml=MINIMAL_SECTIONS_YAML, theme_yaml=MINIMAL_THEME_YAML, theme_name="default"):
    (tmp_path / "config" / "children").mkdir(parents=True)
    (tmp_path / "config" / "themes").mkdir(parents=True)
    (tmp_path / "config" / "children" / "sophie.yaml").write_text(sophie_yaml)
    (tmp_path / "config" / "sections.yaml").write_text(sections_yaml)
    if theme_yaml is not None:
        (tmp_path / "config" / "themes" / f"{theme_name}.yaml").write_text(theme_yaml)


VALID_SOPHIE_YAML = """\
id: sophie
name: Sophie
age_band: 4th-grade
location: Fremont, California
cultural_context:
  - Singaporean family in the USA
interests:
  active:
    - gymnastics
    - fun facts
newsletter:
  active_sections:
    - weird_but_true
    - world_watch
    - singapore_spotlight
    - usa_corner
    - gymnastics_corner
    - money_moves
    - sophies_challenge
  theme: default
  editorial:
    reading_level: 4th grade
    tone:
      - warm
      - fun
      - curious
    use_emojis: true
    global_source_preferences:
      - Time for Kids
      - Britannica
"""


def test_load_config_success(tmp_path):
    make_config(tmp_path, VALID_SOPHIE_YAML)
    config = generate.load_config(tmp_path)
    assert "profile" in config
    assert "sections" in config
    assert "theme" in config
    assert config["profile"]["name"] == "Sophie"


def test_load_config_missing_child(tmp_path):
    (tmp_path / "config").mkdir(parents=True)
    with pytest.raises(SystemExit):
        generate.load_config(tmp_path)


def test_load_config_unknown_section_id(tmp_path):
    sophie_with_bad_section = """\
id: sophie
name: Sophie
age_band: 4th-grade
location: Fremont, California
cultural_context: []
interests:
  active: []
newsletter:
  active_sections:
    - nonexistent_section
  theme: default
"""
    make_config(tmp_path, sophie_with_bad_section)
    with pytest.raises(SystemExit):
        generate.load_config(tmp_path)


def test_load_config_missing_theme(tmp_path):
    sophie_missing_theme = """\
id: sophie
name: Sophie
age_band: 4th-grade
location: Fremont, California
cultural_context: []
interests:
  active: []
newsletter:
  active_sections:
    - weird_but_true
  theme: missing_theme
"""
    make_config(tmp_path, sophie_missing_theme, theme_yaml=None)
    with pytest.raises(SystemExit):
        generate.load_config(tmp_path)


def test_get_template_path_success(tmp_path):
    template = tmp_path / "scripts" / "template.html"
    template.parent.mkdir(parents=True)
    template.write_text("<html/>")
    result = generate.get_template_path(tmp_path, {"template_path": "scripts/template.html"})
    assert result == template


def test_get_template_path_missing_field(tmp_path):
    with pytest.raises(SystemExit):
        generate.get_template_path(tmp_path, {})


def test_get_template_path_missing_file(tmp_path):
    with pytest.raises(SystemExit):
        generate.get_template_path(tmp_path, {"template_path": "scripts/missing.html"})


def test_build_profile_summary():
    summary = content_stage.build_profile_summary({
        "id": "sophie",
        "name": "Sophie",
        "age_band": "4th-grade",
        "location": "Fremont, California",
        "cultural_context": ["Singaporean family in the USA"],
        "interests": {"active": ["gymnastics", "fun facts"]},
        "newsletter": {
            "editorial": {
                "reading_level": "4th grade",
                "tone": ["warm", "fun", "curious"],
                "use_emojis": True,
            }
        },
    })
    assert summary["name"] == "Sophie"
    assert summary["reading_level"] == "4th grade"
    assert "gymnastics" in summary["active_interests"]



def test_build_section_summaries_limits_rules_and_sources():
    profile = {"newsletter": {"active_sections": ["weird_but_true"]}}
    sections = {
        "weird_but_true": {
            "title": "🤔 Weird But True",
            "goal": "Share wild facts",
            "block_type": "fact_list",
            "content_rules": ["r1", "r2", "r3", "r4"],
            "source_preferences": ["s1", "s2", "s3", "s4"],
            "link_style": "link-purple",
        }
    }
    summaries = content_stage.build_section_summaries(profile, sections)
    assert summaries[0]["rules"] == ["r1", "r2", "r3"]
    assert summaries[0]["preferred_sources"] == ["s1", "s2", "s3"]



def test_build_content_prompt_contains_editorial_defaults():
    config = {
        "profile": {
            "id": "sophie",
            "name": "Sophie",
            "age_band": "4th-grade",
            "location": "Fremont, California",
            "cultural_context": ["Singaporean family in the USA"],
            "interests": {"active": ["gymnastics"]},
            "newsletter": {
                "active_sections": ["weird_but_true"],
                "editorial": {
                    "reading_level": "4th grade",
                    "tone": ["warm", "fun", "curious"],
                    "use_emojis": True,
                },
            },
        },
        "sections": {
            "weird_but_true": {
                "title": "🤔 Weird But True",
                "goal": "Share wild facts",
                "block_type": "fact_list",
                "content_rules": [],
                "source_preferences": [],
                "link_style": "link-purple",
            }
        },
    }
    prompt = content_stage.build_content_prompt(date(2026, 4, 18), 4, config, ["Old Headline"])
    assert '"reading_level": "4th grade"' in prompt
    assert '"active_interests": [' in prompt
    assert "Old Headline" in prompt
    assert '"block_type": "fact_list"' in prompt
    assert "Child summary:" in prompt
    assert "Active section summaries:" in prompt
    assert "Block-type item contracts:" in prompt
    assert '"greeting_text"' in prompt
    assert '"section_intro"' in prompt


def test_parse_content_output_success(tmp_path):
    payload = json.dumps({
        "is_error": False,
        "result": json.dumps({
            "issue_date": "2026-04-18",
            "issue_number": 4,
            "child_id": "sophie",
            "theme_id": "default",
            "editorial": {},
            "child_name": "Sophie",
            "greeting_text": "Welcome back to <span>Sophie's World</span>!",
            "sections": [{"id": "weird_but_true", "title": "A", "render_title": "A", "block_type": "fact_list", "items": [{"title": "x", "body": "y"}], "links": [], "link_style": "link-purple"}],
            "footer": {"issue_number": 4, "issue_date_display": "April 18, 2026", "tagline": "x", "location_line": "y"}
        })
    })
    parsed = content_stage.parse_content_output(payload, tmp_path)
    assert parsed["child_id"] == "sophie"


def test_parse_content_output_error():
    payload = json.dumps({"is_error": True, "result": ""})
    with pytest.raises(ValueError):
        content_stage.parse_content_output(payload)


def test_parse_content_output_handles_fenced_json_with_trailing_text(tmp_path):
    payload = json.dumps({
        "is_error": False,
        "result": "```json\n{\n  \"issue_date\": \"2026-04-18\",\n  \"issue_number\": 4,\n  \"child_id\": \"sophie\",\n  \"theme_id\": \"default\",\n  \"editorial\": {},\n  \"child_name\": \"Sophie\",\n  \"greeting_text\": \"Issue #4 of <span>Sophie's World</span> is here!\",\n  \"sections\": [],\n  \"footer\": {\"issue_number\": 4, \"issue_date_display\": \"April 18, 2026\", \"tagline\": \"x\", \"location_line\": \"y\"}\n}\n```\nextra"
    })
    parsed = content_stage.parse_content_output(payload, tmp_path)
    assert parsed["child_name"] == "Sophie"


def test_issue_artifact_round_trip(tmp_path):
    issue = {
        "issue_date": "2026-04-18",
        "issue_number": 4,
        "child_id": "sophie",
        "theme_id": "default",
        "editorial": {},
        "child_name": "Sophie",
        "greeting_text": "Welcome back to <span>Sophie's World</span>!",
        "sections": [{"id": "weird_but_true", "title": "A", "render_title": "A", "block_type": "fact_list", "items": [{"title": "x", "body": "y"}], "links": [], "link_style": "link-purple"}],
        "footer": {"issue_number": 4, "issue_date_display": "April 18, 2026", "tagline": "x", "location_line": "y"}
    }
    out_path = issue_schema.write_issue_artifact(tmp_path, issue)
    loaded = issue_schema.load_issue_artifact(out_path)
    assert loaded["issue_date"] == "2026-04-18"


def test_validate_issue_artifact_missing_fields():
    with pytest.raises(ValueError):
        issue_schema.validate_issue_artifact({"issue_date": "2026-04-18"})


def test_render_links_empty():
    assert render_stage.render_links([], "link-blue") == ""


def test_render_issue_html_fact_section():
    template = (Path(__file__).parent.parent / "scripts" / "template.html").read_text(encoding="utf-8")
    issue = {
        "issue_number": 4,
        "child_name": "Sophie",
        "greeting_text": "Welcome back to <span>Sophie's World</span>!",
        "sections": [
            {
                "id": "weird_but_true",
                "render_title": "Nature Is Wild!",
                "block_type": "fact_list",
                "items": [{"title": "🐝 Fact", "body": "Bees are amazing."}],
                "links": [{"label": "Nat Geo Kids", "url": "https://example.com"}],
                "link_style": "link-purple",
            }
        ],
        "footer": {
            "issue_number": 4,
            "issue_date_display": "April 18, 2026",
            "tagline": "Made with love by Dad & Claude 🤖❤️",
            "location_line": "Fremont, California ↔ Singapore",
        },
    }
    html = render_stage.render_issue_html(template, issue)
    assert "Nature Is Wild!" in html
    assert "🐝 Fact" in html
    assert "Nat Geo Kids" in html


def test_render_section_body_story_list():
    html = render_stage.render_section_body({
        "block_type": "story_list",
        "items": [{
            "headline": "Big Story",
            "body": ["Paragraph one", "Paragraph two"],
            "analogy": "Like a timeout",
            "links": [{"label": "BBC", "url": "https://example.com"}],
        }],
        "link_style": "link-green",
    })
    assert "Big Story" in html
    assert "Like a timeout" in html
    assert "BBC" in html


def test_render_section_body_interest_feature():
    html = render_stage.render_section_body({
        "block_type": "interest_feature",
        "items": [{"headline": "Gym News", "body": ["A great meet happened."], "links": [{"label": "Read", "url": "https://example.com"}]}],
        "link_style": "link-rose",
    })
    assert "Gym News" in html
    assert "interest-item" in html
    assert "Read" in html


def test_render_section_body_challenge():
    html = render_stage.render_section_body({
        "block_type": "challenge",
        "items": [{"prompt_intro": "You just learned about tariffs.", "prompt": "What is half of 10?", "bonus": "What is double 10?", "hint": "Think division", "links": []}],
        "link_style": "link-orange",
    })
    assert "You just learned about tariffs." in html
    assert "What is half of 10?" in html
    assert "What is double 10?" in html
    assert "Think division" in html


def test_render_section_body_spotlight_uses_variant_classes():
    html = render_stage.render_section_body({
        "id": "usa_corner",
        "block_type": "spotlight",
        "items": [{"headline": "Solar Boom", "body": ["California is cooking with sunshine."]}],
        "link_style": "link-blue",
    })
    assert "usa-spot" in html
    assert "Solar Boom" in html


def test_render_section_body_money_story_list_uses_money_variant():
    html = render_stage.render_section_body({
        "id": "money_moves",
        "block_type": "story_list",
        "items": [{"headline": "Pay Yourself First", "body": ["Save before you spend."], "links": []}],
        "link_style": "link-amber",
    })
    assert "money-story" in html
    assert "Pay Yourself First" in html


def test_build_page_title_and_greeting_helpers():
    issue = {
        "issue_number": 4,
        "child_name": "Sophie",
        "greeting_text": "Welcome back to <span>Sophie's World</span>!",
        "footer": {"issue_date_display": "April 18, 2026", "tagline": "x", "location_line": "y"},
    }
    assert "Issue #4" in render_stage.build_page_title(issue)
    assert "April 18, 2026" in render_stage.build_date_badge_html(issue)
    assert "Hey Sophie!" in render_stage.build_greeting_html(issue)
    assert "Welcome back" in render_stage.build_greeting_html(issue)


def test_template_uses_generic_interest_slot():
    template = (Path(__file__).parent.parent / "scripts" / "template.html").read_text(encoding="utf-8")
    assert "INTEREST_FEATURE" in template
    assert "Interest Corner" in template
    assert ".interest-grid" in template
    assert ".interest-item" in template
    assert "K-pop Corner" not in template
    assert "KPOP_CORNER" not in template
