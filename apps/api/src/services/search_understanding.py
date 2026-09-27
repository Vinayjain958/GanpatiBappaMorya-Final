"""Deterministic query normalization for catalog search.

This is a small, auditable vocabulary layer rather than an LLM call. It
handles common spelling fragments, inflections, and intent synonyms while
leaving the catalog as the only source of returned place facts.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_SYNONYM_GROUPS = (
    {"heritage", "herit", "history", "historical", "historic", "monument", "museum", "culture", "cultural"},
    {"food", "eat", "eating", "restaurant", "restaurants", "cuisine", "dining", "meal"},
    {"art", "arts", "gallery", "galleries", "craft", "crafts"},
    {"nature", "park", "parks", "garden", "gardens", "outdoors", "greenery"},
    {"religious", "religion", "temple", "temples", "mosque", "church", "spiritual"},
    {"shopping", "market", "markets", "shop", "shops", "bazaar"},
    {"adventure", "adventurous", "hiking", "trek", "trekking", "outdoor"},
)
_SYNONYMS = {word: group for group in _SYNONYM_GROUPS for word in group}


def query_terms(query: str) -> tuple[str, ...]:
    """Return original and related terms, including recognized prefixes."""
    tokens = _TOKEN_RE.findall(query.casefold())
    expanded: set[str] = set(tokens)
    for token in tokens:
        if token in _SYNONYMS:
            expanded.update(_SYNONYMS[token])
        # Prefix input such as "herit" should discover history/heritage.
        if len(token) >= 4:
            for group in _SYNONYM_GROUPS:
                if any(word.startswith(token) or token.startswith(word) for word in group):
                    expanded.update(group)
    return tuple(sorted(expanded))


def token_matches(query_token: str, candidate_token: str) -> bool:
    """Exact/prefix/single-token typo match with conservative thresholds."""
    if query_token == candidate_token:
        return True
    if min(len(query_token), len(candidate_token)) >= 4 and (
        query_token.startswith(candidate_token) or candidate_token.startswith(query_token)
    ):
        return True
    if min(len(query_token), len(candidate_token)) < 5:
        return False
    return SequenceMatcher(None, query_token, candidate_token).ratio() >= 0.82


def text_match_score(query: str, text: str) -> float:
    """Score how many meaningful query terms match text, including synonyms."""
    raw_terms = _TOKEN_RE.findall(query.casefold())
    candidate_terms = _TOKEN_RE.findall(text.casefold())
    if not raw_terms or not candidate_terms:
        return 0.0
    expanded = query_terms(query)
    matched = sum(
        1.0 for term in expanded if any(token_matches(term, candidate) for candidate in candidate_terms)
    )
    # Synonym expansion must improve recall without overwhelming exact intent.
    return min(1.0, matched / max(1, len(raw_terms)))


__all__ = ["query_terms", "text_match_score", "token_matches"]
