"""Deterministic query normalization for catalog search.

This is a small, auditable vocabulary layer rather than an LLM call. It
handles common spelling fragments, inflections, and intent synonyms while
leaving the catalog as the only source of returned place facts.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from functools import lru_cache

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


@lru_cache(maxsize=1024)
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


# Pure functions called for every (query term, catalog word) pair across the
# whole candidate set on each search; the same pairs recur constantly, so
# memoizing them removes most of the SequenceMatcher cost.
@lru_cache(maxsize=200_000)
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
    # ratio() = 2*matches/(len_a+len_b) can never exceed 2*min_len/(len_a+len_b),
    # and quick_ratio()/real_quick_ratio() are cheaper upper bounds of ratio(),
    # so these early exits skip hopeless pairs without changing any result.
    shorter, longer = sorted((len(query_token), len(candidate_token)))
    if 2 * shorter / (shorter + longer) < 0.82:
        return False
    matcher = SequenceMatcher(None, query_token, candidate_token)
    return (
        matcher.real_quick_ratio() >= 0.82
        and matcher.quick_ratio() >= 0.82
        and matcher.ratio() >= 0.82
    )


@lru_cache(maxsize=65_536)
def _tokens(text: str) -> frozenset[str]:
    return frozenset(_TOKEN_RE.findall(text.casefold()))


def _term_matches_any(term: str, candidates: frozenset[str]) -> bool:
    return term in candidates or any(token_matches(term, candidate) for candidate in candidates)


def text_match_score(query: str, text: str) -> float:
    """Score how many meaningful query terms match text, including synonyms."""
    raw_terms = _TOKEN_RE.findall(query.casefold())
    candidate_terms = _tokens(text)
    if not raw_terms or not candidate_terms:
        return 0.0
    expanded = query_terms(query)
    matched = sum(1.0 for term in expanded if _term_matches_any(term, candidate_terms))
    # Synonym expansion must improve recall without overwhelming exact intent.
    return min(1.0, matched / max(1, len(raw_terms)))


__all__ = ["query_terms", "text_match_score", "token_matches"]
