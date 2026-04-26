#!/usr/bin/env python3
"""Local deterministic HTML renderer for Sophie's World issues."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List


def render_links(links: List[Dict[str, str]], link_style: str, extra_class: str = "learn-more") -> str:
    if not links:
        return ""
    links_html = "".join(
        f'<a href="{link["url"]}" class="{link_style}">{link["label"]}</a>' for link in links
    )
    return f'<div class="{extra_class}">{links_html}</div>'


def render_fact_list(items: List[Dict[str, Any]]) -> str:
    body = "".join(
        f'<div class="fact-item"><strong>{item["title"]}</strong> {item["body"]}</div>' for item in items
    )
    return f'<div class="fact-list">{body}</div>'


def render_story_list(items: List[Dict[str, Any]], link_style: str, section_class: str = "world") -> str:
    stories = []
    card_class = "world-story" if section_class == "world" else f"{section_class}-story"
    wrapper_class = "world-stories" if section_class == "world" else f"{section_class}-stories"
    for item in items:
        paragraphs = "".join(f"<p>{paragraph}</p>" for paragraph in item.get("body", []))
        highlight = item.get("highlight")
        highlight_html = f'<div class="money-highlight"><strong>{highlight}</strong></div>' if highlight else ""
        analogy = item.get("analogy")
        analogy_html = f'<div class="analogy">{analogy}</div>' if analogy else ""
        links_html = render_links(item.get("links", []), link_style, extra_class="story-links learn-more")
        stories.append(
            f'<div class="{card_class}"><h3>{item["headline"]}</h3>{paragraphs}{highlight_html}{analogy_html}{links_html}</div>'
        )
    return f'<div class="{wrapper_class}">{"".join(stories)}</div>'


def render_spotlight(items: List[Dict[str, Any]], variant: str = "spotlight") -> str:
    wrapper_class = f'{variant}-spots'
    item_class = f'{variant}-spot'
    body = "".join(
        f'<div class="{item_class}"><h3>{item["headline"]}</h3>{"".join(f"<p>{paragraph}</p>" for paragraph in item.get("body", []))}</div>' for item in items
    )
    return f'<div class="{wrapper_class}">{body}</div>'


def render_interest_feature(items: List[Dict[str, Any]], link_style: str) -> str:
    body = []
    for item in items:
        paragraphs = "".join(f"<p>{paragraph}</p>" for paragraph in item.get("body", []))
        links_html = render_links(item.get("links", []), link_style, extra_class="story-links learn-more")
        body.append(f'<div class="interest-item"><h3>{item["headline"]}</h3>{paragraphs}{links_html}</div>')
    return f'<div class="interest-grid">{"".join(body)}</div>'


def render_challenge(items: List[Dict[str, Any]], link_style: str) -> str:
    item = items[0]
    intro = item.get("prompt_intro")
    bonus = item.get("bonus")
    intro_html = f'<p class="challenge-intro">{intro}</p>' if intro else ""
    bonus_html = f'<div class="challenge-bonus">⭐ Bonus: {bonus}</div>' if bonus else ""
    links_html = render_links(item.get("links", []), link_style)
    return (
        f'{intro_html}'
        f'<div class="challenge-q">{item["prompt"]}</div>'
        f'{bonus_html}'
        f'<div class="challenge-hint">{item["hint"]}</div>'
        f'{links_html}'
    )


def render_section_body(section: Dict[str, Any]) -> str:
    block_type = section["block_type"]
    items = section["items"]
    link_style = section.get("link_style", "link-blue")
    section_id = section.get("id")

    if block_type == "fact_list":
        return render_fact_list(items)
    if block_type == "story_list":
        if section_id == "money_moves":
            return render_story_list(items, link_style, section_class="money")
        return render_story_list(items, link_style)
    if block_type == "spotlight":
        variant = "usa" if section_id == "usa_corner" else "sg"
        return render_spotlight(items, variant=variant)
    if block_type == "interest_feature":
        return render_interest_feature(items, link_style)
    if block_type == "challenge":
        return render_challenge(items, link_style)
    raise ValueError(f"unsupported block_type: {block_type}")


def render_footer(footer: Dict[str, str]) -> str:
    return (
        '<div class="footer" style="background:#fff;border-radius:0 0 24px 24px;margin-top:3px;">'
        '<span class="hearts">💖 🌏 💖</span>'
        f'<strong>Sophie\'s World</strong> · Issue #{footer["issue_number"]} · {footer["issue_date_display"]}<br>'
        f'{footer["tagline"]}<br>'
        f'<span style="font-size:12px;color:#bbb;">{footer["location_line"]}</span></div>'
    )


def build_page_title(issue: Dict[str, Any]) -> str:
    return f"Sophie's World · {issue['footer']['issue_date_display']} · Issue #{issue['issue_number']}"


def build_date_badge_html(issue: Dict[str, Any]) -> str:
    return f'<div class="date-badge">📅 {issue["footer"]["issue_date_display"]} · Issue #{issue["issue_number"]}</div>'


def build_greeting_html(issue: Dict[str, Any]) -> str:
    child_name = issue.get("child_name", "Sophie")
    intro = issue.get("greeting_text", "your latest adventure in <span>Sophie's World</span> is ready, packed with fun facts and big ideas.")
    return f'<div class="greeting">Hey {child_name}! 👋 {intro}</div>'


def render_issue_html(template_html: str, issue: Dict[str, Any]) -> str:
    html = template_html
    html = html.replace("<title><!-- PAGE_TITLE --></title>", f'<title>{build_page_title(issue)}</title>')
    html = html.replace(
        "<!-- DATE_BADGE: e.g. <div class=\"date-badge\">📅 April 23, 2026 · Issue #2</div> -->",
        build_date_badge_html(issue),
    )
    html = html.replace(
        "<!-- GREETING: <div class=\"greeting\">Hey Sophie! 👋 ... <span>Sophie's World</span> ... </div> -->",
        build_greeting_html(issue),
    )

    placeholder_map = {
        "weird_but_true": "<!-- WEIRD_BUT_TRUE: h2 title, then .fact-list with 2-3 .fact-item divs (each with <strong>emoji Title</strong> body), then .learn-more links using .link-purple -->",
        "world_watch": "<!-- WORLD_WATCH: h2 title, then .world-stories with 2 .world-story divs. Each story: h3, p tags, .analogy div, .story-links.learn-more with .link-green links -->",
        "singapore_spotlight": "<!-- SINGAPORE_SPOTLIGHT: h2 title, .sg-spots with 1-2 .sg-spot divs (h3 + p) containing a fun fact about Singapore (cultural, historical, economic, nature, food, or quirky — timeless facts are great), then .learn-more with .link-pink links -->",
        "usa_corner": "<!-- USA_CORNER: h2 title, p tags for content, .learn-more with .link-blue links -->",
        "gymnastics_corner": "<!-- INTEREST_FEATURE: h2 title, .interest-grid with 2 .interest-item divs (h3 + p), .learn-more with .link-rose links. Use the active interest section title and content from config. -->",
        "kpop_corner": "<!-- INTEREST_FEATURE: h2 title, .interest-grid with 2 .interest-item divs (h3 + p), .learn-more with .link-rose links. Use the active interest section title and content from config. -->",
        "money_moves": "<!-- MONEY_MOVES: h2 title, p tags, .money-highlight div, p for kid entrepreneur story, .learn-more with .link-amber links -->",
        "sophies_challenge": "<!-- SOPHIES_CHALLENGE: h2 \"Can You Figure This Out?\", .challenge-q div with the puzzle (tied to World Watch), .challenge-hint p, .learn-more with .link-orange links -->",
    }

    for section in issue["sections"]:
        body_html = render_section_body(section)
        section_title = f'<h2>{section["render_title"]}</h2>'
        section_intro = section.get("section_intro")
        intro_html = f'<p class="section-intro">{section_intro}</p>' if section_intro else ""
        links_html = render_links(section.get("links", []), section.get("link_style", "link-blue"))
        replacement = f"{section_title}{intro_html}{body_html}{links_html}"
        html = html.replace(placeholder_map[section["id"]], replacement)

    html = html.replace(
        "<!-- FOOTER: <div class=\"footer\" style=\"background:#fff;border-radius:0 0 24px 24px;margin-top:3px;\"><span class=\"hearts\">💖 🌏 💖</span><strong>Sophie's World</strong> · Issue #N · Month DD, YYYY<br>Made with love by Dad &amp; Claude 🤖❤️<br><span style=\"font-size:12px;color:#bbb;\">Fremont, California ↔ Singapore</span></div> -->",
        render_footer(issue["footer"]),
    )
    return html


def load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_render_stage(
    config: dict,
    today: date,
    repo_root: Path,
    artifacts_root: Path,
    log: Callable[[str], None] = print,
) -> Path:
    """Render HTML from issue artifact. Returns output path."""
    from issue_schema import get_issue_artifact_path, load_issue_artifact

    issue_path = get_issue_artifact_path(
        repo_root, "sophie", today.isoformat(), artifacts_root=artifacts_root
    )
    if not issue_path.exists():
        raise FileNotFoundError(
            f"Issue artifact not found: {issue_path}. Run synthesis stage first."
        )
    log(f"Loading issue artifact...")
    issue = load_issue_artifact(issue_path)

    theme = config.get("theme", {})
    template_path = repo_root / theme.get("template_path", "scripts/template.html")
    template_html = load_template(template_path)

    html = render_issue_html(template_html, issue)

    newsletters_dir = artifacts_root / "newsletters"
    newsletters_dir.mkdir(parents=True, exist_ok=True)
    output_path = newsletters_dir / f"sophies-world-{today.isoformat()}.html"
    output_path.write_text(html, encoding="utf-8")
    log(f"Newsletter rendered: {output_path}")
    return output_path
