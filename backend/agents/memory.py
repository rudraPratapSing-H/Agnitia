"""Incident Memory: Matches current incident against historical repository of resolved incidents.

TASK 3.5 (Member 3):
- Function: find_similar(rca: RCA, root_service: str) -> SimilarIncident | None
- Loads past_incidents.json once and caches it. Returns None if missing or invalid.
- Scoring formula:
    score = 0.40 * (category equal) + 0.25 * (root_service equal)
          + 0.35 * jaccard(tokens(rca.root_cause), tokens(past.root_cause + " " + " ".join(past.keywords)))
- Tokenise lower-case, split on non-alphanumerics, drop stop words:
    (the, was, for, its, a, of, by, to, in, on, and)
- Returns SimilarIncident(id=..., similarity=round(score, 2)) when score >= 0.6, else None.
- Ties: the first in the file.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from backend.models import RCA, SimilarIncident

PAST_INCIDENTS_PATH: Path = Path(__file__).resolve().parent / "past_incidents.json"
_CACHE: dict[Path, list[dict[str, Any]] | None] = {}

STOP_WORDS: set[str] = {
    "the",
    "was",
    "for",
    "its",
    "a",
    "of",
    "by",
    "to",
    "in",
    "on",
    "and",
}


def clear_cache() -> None:
    """Clears the cached incidents dictionary."""
    _CACHE.clear()


def tokenize(text: str) -> set[str]:
    """Tokenise lower-case, split on non-alphanumerics, drop stop words."""
    if not text:
        return set()
    raw = re.split(r"[^a-zA-Z0-9]+", text.lower())
    return {tok for tok in raw if tok and tok not in STOP_WORDS}


def jaccard(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Computes Jaccard similarity between two token sets."""
    if not tokens_a and not tokens_b:
        return 0.0
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    intersection = tokens_a & tokens_b
    return len(intersection) / len(union)


def _load_past_incidents(path: Path) -> list[dict[str, Any]] | None:
    """Loads past incidents from the specified path once and caches the result."""
    if path in _CACHE:
        return _CACHE[path]
    try:
        if not path.is_file():
            _CACHE[path] = None
            return None
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
        if not isinstance(data, list):
            _CACHE[path] = None
            return None
        _CACHE[path] = data
        return data
    except Exception:
        _CACHE[path] = None
        return None


def find_similar(rca: RCA, root_service: str) -> SimilarIncident | None:
    """Finds the closest matching historical incident from past_incidents.json.

    Score = 0.40 * (category equal) + 0.25 * (root_service equal)
          + 0.35 * jaccard(tokens(rca.root_cause), tokens(past.root_cause + ' ' + ' '.join(past.keywords)))
    Threshold: score >= 0.6. Ties: first in file.
    """
    incidents = _load_past_incidents(PAST_INCIDENTS_PATH)
    if not incidents:
        return None

    tokens_curr = tokenize(rca.root_cause)

    best_match: str | None = None
    best_score: float = -1.0

    for past in incidents:
        if not isinstance(past, dict):
            continue

        past_cat = str(past.get("category", "")).strip().lower()
        curr_cat = str(rca.category).strip().lower()
        cat_score = 1.0 if (curr_cat and curr_cat == past_cat) else 0.0

        past_root = str(past.get("root_service", "")).strip().lower()
        curr_root = str(root_service).strip().lower()
        root_score = 1.0 if (curr_root and curr_root == past_root) else 0.0

        past_rc = past.get("root_cause") or past.get("summary") or ""
        past_keywords = past.get("keywords") or past.get("similarity_keywords") or []
        if isinstance(past_keywords, list):
            kws_str = " ".join(str(k) for k in past_keywords)
        else:
            kws_str = str(past_keywords)

        past_text = f"{past_rc} {kws_str}"
        tokens_past = tokenize(past_text)

        jaccard_score = jaccard(tokens_curr, tokens_past)

        score = (0.40 * cat_score) + (0.25 * root_score) + (0.35 * jaccard_score)

        # Ties: the first in the file (strictly greater replaces)
        if score > best_score:
            best_score = score
            best_match = past.get("id")

    if best_match is not None and (best_score >= 0.6 or round(best_score, 2) >= 0.6):
        return SimilarIncident(id=best_match, similarity=round(best_score, 2))

    return None


def match_similar_incident(service: str, text_context: str) -> SimilarIncident | None:
    """Backward-compatible helper function."""
    fake_rca = RCA(
        root_cause=text_context,
        category="",
        confidence=0.0,
    )
    return find_similar(fake_rca, service)
