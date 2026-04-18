import json
import sys
import pytest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import generate


def test_get_next_issue_number_no_files(tmp_path):
    assert generate.get_next_issue_number(tmp_path) == 1


def test_get_next_issue_number_with_existing(tmp_path):
    (tmp_path / "sophies-world-2026-04-09.html").touch()
    (tmp_path / "sophies-world-2026-04-16.html").touch()
    assert generate.get_next_issue_number(tmp_path) == 3


def test_get_output_path(tmp_path):
    result = generate.get_output_path(tmp_path, date(2026, 4, 23))
    assert result == tmp_path / "sophies-world-2026-04-23.html"


def test_parse_claude_output_success():
    payload = json.dumps({
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": "<html><body>Hello</body></html>",
    })
    assert generate.parse_claude_output(payload) == "<html><body>Hello</body></html>"


def test_parse_claude_output_error():
    payload = json.dumps({
        "type": "result",
        "subtype": "error",
        "is_error": True,
        "result": "",
    })
    assert generate.parse_claude_output(payload) is None


def test_parse_claude_output_non_html():
    payload = json.dumps({
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": "Here is your newsletter:",
    })
    assert generate.parse_claude_output(payload) is None


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_SECTIONS_YAML = """\
sections:
  weird_but_true:
    title: "🤔 Weird But True"
    goal: "Share 2–3 wild fun facts"
    content_rules:
      - Facts should be surprising
    link_style: link-purple
    source_preferences:
      - Nat Geo Kids
  gymnastics_corner:
    title: "🤸 Gymnastics Corner"
    goal: "Share gymnastics news"
    content_rules:
      - Keep it age-appropriate
    link_style: link-rose
    source_preferences:
      - USA Gymnastics
  kpop_corner:
    title: "🎤 K-pop Corner"
    goal: "Share K-pop news"
    content_rules:
      - Keep content age-appropriate
    link_style: link-rose
    source_preferences:
      - YouTube
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
  theme: default
"""


# ---------------------------------------------------------------------------
# load_config tests
# ---------------------------------------------------------------------------

def test_load_config_success(tmp_path):
    make_config(tmp_path, VALID_SOPHIE_YAML)
    config = generate.load_config(tmp_path)
    assert "profile" in config
    assert "sections" in config
    assert "theme" in config
    assert config["profile"]["name"] == "Sophie"


def test_load_config_missing_child(tmp_path):
    # No config files created at all — missing children/sophie.yaml
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
    # Create config but with no themes/missing_theme.yaml
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


# ---------------------------------------------------------------------------
# build_profile_description tests
# ---------------------------------------------------------------------------

def test_build_profile_description():
    profile = {
        "name": "Sophie",
        "age_band": "4th-grade",
        "location": "Fremont, California",
        "cultural_context": ["Singaporean family in the USA"],
        "interests": {"active": ["gymnastics", "fun facts"]},
    }
    result = generate.build_profile_description(profile)
    assert "Sophie" in result
    assert "Fremont, California" in result
    assert "gymnastics" in result


def test_build_editorial_defaults():
    profile = {
        "newsletter": {
            "editorial": {
                "reading_level": "4th grade",
                "tone": ["warm", "fun", "curious"],
                "use_emojis": True,
                "global_source_preferences": ["Time for Kids", "Britannica"],
            }
        }
    }
    result = generate.build_editorial_defaults(profile)
    assert "Reading level: 4th grade." in result
    assert "Tone: warm, fun, curious." in result
    assert "Use emojis naturally." in result
    assert "Links: prefer Time for Kids, Britannica." in result



def test_build_editorial_defaults_empty():
    result = generate.build_editorial_defaults({})
    assert result == ""


# ---------------------------------------------------------------------------
# build_section_rules tests
# ---------------------------------------------------------------------------

def test_build_section_rules_includes_active_sections():
    profile = {
        "newsletter": {
            "active_sections": ["weird_but_true"],
        }
    }
    sections = {
        "weird_but_true": {
            "goal": "Share wild fun facts",
            "content_rules": ["Facts should be surprising"],
            "link_style": "link-purple",
            "source_preferences": ["Nat Geo Kids"],
        }
    }
    result = generate.build_section_rules(profile, sections)
    assert "WEIRD_BUT_TRUE" in result


def test_build_section_rules_section_swap():
    profile = {
        "newsletter": {
            "active_sections": ["gymnastics_corner"],
        }
    }
    sections = {
        "gymnastics_corner": {
            "goal": "Share gymnastics news",
            "content_rules": ["Keep it age-appropriate", "Use .interest-item structure for each item"],
            "link_style": "link-rose",
            "source_preferences": ["USA Gymnastics"],
        },
        "kpop_corner": {
            "goal": "Share K-pop news",
            "content_rules": ["Keep content age-appropriate", "Use .interest-item structure for each item"],
            "link_style": "link-rose",
            "source_preferences": ["YouTube"],
        },
    }
    result = generate.build_section_rules(profile, sections)
    assert "GYMNASTICS_CORNER" in result
    assert "KPOP_CORNER" not in result
    assert ".interest-item" in result


def test_template_uses_generic_interest_slot():
    template = (Path(__file__).parent.parent / "scripts" / "template.html").read_text(encoding="utf-8")
    assert "INTEREST_FEATURE" in template
    assert "Interest Corner" in template
    assert ".interest-grid" in template
    assert ".interest-item" in template
    assert "K-pop Corner" not in template
    assert "KPOP_CORNER" not in template


# ---------------------------------------------------------------------------
# build_prompt tests
# ---------------------------------------------------------------------------

def _minimal_config(name="TestChild"):
    return {
        "profile": {
            "name": name,
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
                    "global_source_preferences": ["Time for Kids", "Britannica"],
                },
            },
        },
        "sections": {
            "weird_but_true": {
                "goal": "Share wild fun facts",
                "content_rules": [],
                "link_style": "link-purple",
                "source_preferences": [],
            }
        },
        "theme": {"theme_id": "default"},
    }


def test_build_prompt_contains_profile_info():
    config = _minimal_config("TestChild")
    result = generate.build_prompt(
        template_html="<html/>",
        issue_date=date(2026, 4, 23),
        issue_num=5,
        config=config,
    )
    assert "TestChild" in result
    assert "Reading level: 4th grade." in result
    assert "Tone: warm, fun, curious." in result
    assert "Links: prefer Time for Kids, Britannica." in result


def test_build_prompt_with_headlines():
    config = _minimal_config()
    result = generate.build_prompt(
        template_html="<html/>",
        issue_date=date(2026, 4, 23),
        issue_num=5,
        config=config,
        recent_headlines=["Big Story One", "K-pop News"],
    )
    assert "do NOT repeat" in result
    assert "Big Story One" in result
    assert "K-pop News" in result


def test_build_prompt_without_headlines():
    config = _minimal_config()
    result = generate.build_prompt(
        template_html="<html/>",
        issue_date=date(2026, 4, 23),
        issue_num=5,
        config=config,
        recent_headlines=[],
    )
    assert "do NOT repeat" not in result
