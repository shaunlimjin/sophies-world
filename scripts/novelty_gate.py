"""Novelty gate for Sophie's World issues.

Checks a newly generated structured issue against recent issue artifacts before it is
rendered/sent. The goal is to catch repeated stories/facts such as the recurring
"geckos can't blink" item before Sophie receives another duplicate.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "could",
    "did", "do", "does", "for", "from", "had", "has", "have", "he", "her",
    "here", "his", "how", "i", "if", "in", "into", "is", "it", "its", "just",
    "kids", "kid", "learn", "more", "new", "news", "not", "of", "on", "or",
    "our", "read", "she", "so", "story", "that", "the", "their", "them", "this",
    "to", "too", "up", "was", "we", "what", "when", "where", "which", "who",
    "why", "will", "with", "world", "you", "your",
}

# These collection/list pages are useful research pools but weak freshness signals.
# If they repeat, the synthesized item needs to be checked by text/topic, not waved
# through because the page is generic.
GENERIC_COLLECTION_HINTS = (
    "weird-but-true",
    "category/",
    "/animals",
    "/videos/topic/",
    "timeforkids.com/g",
    "kids.nationalgeographic.com/geography/countries/",
)


@dataclass(frozen=True)
class IssueItem:
    issue_date: str
    section_id: str
    title: str
    text: str
    urls: tuple[str, ...]


@dataclass(frozen=True)
class NoveltyFinding:
    severity: str  # "error" or "warning"
    section_id: str
    current_title: str
    previous_title: str
    previous_date: str
    reason: str

    def format(self) -> str:
        return (
            f"[{self.severity}] {self.section_id}: '{self.current_title}' repeats "
            f"{self.previous_date} '{self.previous_title}' — {self.reason}"
        )


def extract_issue_items(issue: dict) -> List[IssueItem]:
    """Extract comparable content items from a structured issue artifact."""
    issue_date = str(issue.get("issue_date", ""))
    items: List[IssueItem] = []
    for section in issue.get("sections", []):
        section_id = section.get("id") or section.get("section_id") or "unknown"
        for item in section.get("items", []):
            title = (
                item.get("headline")
                or item.get("title")
                or item.get("prompt")
                or item.get("prompt_intro")
                or ""
            )
            body_parts: list[str] = []
            for key in ("body", "analogy", "prompt_intro", "prompt", "bonus", "hint"):
                value = item.get(key)
                if isinstance(value, list):
                    body_parts.extend(str(v) for v in value if v)
                elif value:
                    body_parts.append(str(value))
            urls = tuple(
                link.get("url", "")
                for link in item.get("links", [])
                if isinstance(link, dict) and link.get("url")
            )
            text = " ".join([title, *body_parts])
            if title or text or urls:
                items.append(IssueItem(issue_date, section_id, str(title), text, urls))
    return items


def load_recent_issue_items(
    repo_root: Path,
    current_issue_date: str,
    child_id: str = "sophie",
    window: int = 6,
    artifacts_root: Optional[Path] = None,
) -> List[IssueItem]:
    """Load comparable items from the most recent previous issue artifacts."""
    root = artifacts_root or (repo_root / "artifacts")
    issues_dir = root / "issues"
    if not issues_dir.exists():
        return []

    dated: list[tuple[str, Path]] = []
    for path in issues_dir.glob(f"{child_id}-*.json"):
        match = re.match(rf"{re.escape(child_id)}-(\d{{4}}-\d{{2}}-\d{{2}})(?:-.+)?\.json$", path.name)
        if not match:
            continue
        issue_date = match.group(1)
        if issue_date >= current_issue_date:
            continue
        dated.append((issue_date, path))

    # If several run-tagged artifacts exist for a date, keep the plain production
    # artifact when present; otherwise keep the lexicographically last one.
    by_date: dict[str, Path] = {}
    for issue_date, path in sorted(dated):
        plain = issues_dir / f"{child_id}-{issue_date}.json"
        by_date[issue_date] = plain if plain.exists() else path

    recent_paths = [by_date[d] for d in sorted(by_date)[-window:]]
    items: List[IssueItem] = []
    for path in recent_paths:
        try:
            items.extend(extract_issue_items(json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            # A broken historical artifact should not hide a freshly generated issue.
            continue
    return items


def check_issue_novelty(
    issue: dict,
    previous_items: Iterable[IssueItem],
    *,
    similarity_threshold: float = 0.28,
    warning_threshold: float = 0.22,
) -> List[NoveltyFinding]:
    """Return novelty findings comparing current issue items to prior items."""
    findings: List[NoveltyFinding] = []
    previous = list(previous_items)
    for current in extract_issue_items(issue):
        current_tokens = _tokenize(current.text)
        current_urls = {u for u in current.urls if not _is_generic_collection_url(u)}
        for prior in previous:
            same_section = current.section_id == prior.section_id
            if not same_section:
                continue

            prior_urls = {u for u in prior.urls if not _is_generic_collection_url(u)}
            repeated_urls = sorted(current_urls & prior_urls)
            if repeated_urls:
                findings.append(NoveltyFinding(
                    "error",
                    current.section_id,
                    current.title,
                    prior.title,
                    prior.issue_date,
                    f"same source URL reused: {repeated_urls[0]}",
                ))
                continue

            sim = _jaccard(current_tokens, _tokenize(prior.text))
            if sim >= similarity_threshold:
                findings.append(NoveltyFinding(
                    "error",
                    current.section_id,
                    current.title,
                    prior.title,
                    prior.issue_date,
                    f"high text/topic similarity ({sim:.2f})",
                ))
            elif sim >= warning_threshold and _has_distinctive_overlap(current_tokens, _tokenize(prior.text)):
                findings.append(NoveltyFinding(
                    "warning",
                    current.section_id,
                    current.title,
                    prior.title,
                    prior.issue_date,
                    f"possible topic repeat ({sim:.2f})",
                ))
    return _dedupe_findings(findings)


def assert_issue_novelty(
    issue: dict,
    repo_root: Path,
    *,
    artifacts_root: Optional[Path] = None,
    child_id: Optional[str] = None,
    window: int = 6,
) -> List[NoveltyFinding]:
    """Check an issue against recent artifacts and raise on blocking repeats."""
    resolved_child = child_id or issue.get("child_id", "sophie")
    previous_items = load_recent_issue_items(
        repo_root,
        str(issue.get("issue_date", "")),
        child_id=resolved_child,
        window=window,
        artifacts_root=artifacts_root,
    )
    findings = check_issue_novelty(issue, previous_items)
    errors = [f for f in findings if f.severity == "error"]
    if errors:
        rendered = "\n".join(f"- {f.format()}" for f in errors[:8])
        raise ValueError(
            "Novelty gate failed: generated issue repeats recent Sophie's World content.\n"
            + rendered
        )
    return findings


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in tokens if len(t) > 2 and t not in STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _has_distinctive_overlap(a: set[str], b: set[str]) -> bool:
    overlap = a & b
    if len(overlap) >= 3:
        return True
    return any(len(token) >= 7 for token in overlap)


def _is_generic_collection_url(url: str) -> bool:
    lowered = url.lower()
    return any(hint in lowered for hint in GENERIC_COLLECTION_HINTS)


def _dedupe_findings(findings: List[NoveltyFinding]) -> List[NoveltyFinding]:
    seen = set()
    unique = []
    for finding in findings:
        key = (
            finding.severity,
            finding.section_id,
            finding.current_title,
            finding.previous_title,
            finding.previous_date,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique
