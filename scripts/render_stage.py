#!/usr/bin/env python3
"""Local deterministic HTML renderer for Sophie's World issues."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


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


def render_story_list(items: List[Dict[str, Any]], link_style: str) -> str:
    stories = []
    for item in items:
        paragraphs = "".join(f"<p>{paragraph}</p>" for paragraph in item.get("body", []))
        analogy = item.get("analogy")
        analogy_html = f'<div class="analogy">{analogy}</div>' if analogy else ""
        links_html = render_links(item.get("links", []), link_style, extra_class="story-links learn-more")
        stories.append(
            f'<div class="world-story"><h3>{item["headline"]}</h3>{paragraphs}{analogy_html}{links_html}</div>'
        )
    return f'<div class="world-stories">{"".join(stories)}</div>'


def render_spotlight(items: List[Dict[str, Any]]) -> str:
    body = "".join(
        f'<div class="sg-spot"><h3>{item["headline"]}</h3><p>{" ".join(item.get("body", []))}</p></div>' for item in items
    )
    return f'<div class="sg-spots">{body}</div>'


def render_interest_feature(items: List[Dict[str, Any]]) -> str:
    body = "".join(
        f'<div class="interest-item"><h3>{item["headline"]}</h3><p>{" ".join(item.get("body", []))}</p></div>' for item in items
    )
    return f'<div class="interest-grid">{body}</div>'


def render_challenge(items: List[Dict[str, Any]], link_style: str) -> str:
    item = items[0]
    links_html = render_links(item.get("links", []), link_style)
    return (
        f'<div class="challenge-q">{item["prompt"]}</div>'
        f'<div class="challenge-hint">{item["hint"]}</div>'
        f'{links_html}'
    )


def render_section_body(section: Dict[str, Any]) -> str:
    block_type = section["block_type"]
    items = section["items"]
    link_style = section.get("link_style", "link-blue")

    if block_type == "fact_list":
        return render_fact_list(items)
    if block_type == "story_list":
        return render_story_list(items, link_style)
    if block_type == "spotlight":
        return render_spotlight(items)
    if block_type == "interest_feature":
        return render_interest_feature(items)
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


def render_issue_html(template_html: str, issue: Dict[str, Any]) -> str:
    html = template_html
    html = html.replace("<title><!-- PAGE_TITLE --></title>", f'<title>{issue["page_title"]}</title>')
    html = html.replace(
        "<!-- DATE_BADGE: e.g. <div class=\"date-badge\">📅 April 23, 2026 · Issue #2</div> -->",
        issue["date_badge_html"],
    )
    html = html.replace(
        "<!-- GREETING: <div class=\"greeting\">Hey Sophie! 👋 ... <span>Sophie's World</span> ... </div> -->",
        issue["greeting_html"],
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
        links_html = render_links(section.get("links", []), section.get("link_style", "link-blue"))
        replacement = f"{section_title}{body_html}{links_html}"
        html = html.replace(placeholder_map[section["id"]], replacement)

    html = html.replace(
        "<!-- FOOTER: <div class=\"footer\" style=\"background:#fff;border-radius:0 0 24px 24px;margin-top:3px;\"><span class=\"hearts\">💖 🌏 💖</span><strong>Sophie's World</strong> · Issue #N · Month DD, YYYY<br>Made with love by Dad &amp; Claude 🤖❤️<br><span style=\"font-size:12px;color:#bbb;\">Fremont, California ↔ Singapore</span></div> -->",
        render_footer(issue["footer"]),
    )
    return html


def load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")
