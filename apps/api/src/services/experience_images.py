"""Experience image resolution — matches a real Wikimedia Commons image to
an Experience, or honestly reports that none was found.

Matching priority (never let a distant/unrelated image beat a closer
relevant one; see docs/DECISIONS.md image ADR):

  1. Exact Wikimedia/OSM-linked reference (Location.wikimedia_commons_file,
     if the upstream source ever provides one — Overture Places does not
     today, so this tier is dead code against the current dataset but is
     implemented for forward-compatibility with a future OSM-backed import).
  2. Exact place/name match via Commons title search, scored by
     deterministic name-relevance against experience/provider/location name.
  3. Exact Wikidata/Wikipedia place relationship (same forward-compat note
     as #1 — no such field exists in the current schema).
  4. Geographic proximity + strong name/category match (geosearch result
     whose title/categories still relate to the experience).
  5. Geographic proximity only (geosearch result with no name signal) —
     used only as a weak, clearly-labelled contextual image.
  6. Semantic/category fallback (Commons search on category terms) —
     always is_place_specific=False.

Scoring is entirely deterministic (no LLM) per task requirement: an image
either has enough combined signal to pass `wikimedia_min_match_score`, or
it is rejected — "no suitable image" beats "wrong image".
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime

from src.adapters.wikimedia_commons import WikimediaCommonsAdapter, WikimediaImage
from src.core.config import Settings
from src.core.geo import haversine_km

MatchMethod = str  # "exact_commons_link" | "exact_title" | "exact_wikidata" |
# "nearby_strong_match" | "nearby_geographic" | "semantic_fallback"

# Category slug -> Commons search terms tried in order for the semantic
# fallback tier. Kept short and generic — never city-wide, never an
# attempt to describe the specific venue.
CATEGORY_SEARCH_TERMS: dict[str, list[str]] = {
    "food-drink": ["restaurant interior", "Indian restaurant"],
    "street-food": ["street food India", "food stall India"],
    "cafes": ["cafe interior", "coffee shop interior"],
    "culture-heritage": ["heritage site India", "historic monument India"],
    "art-galleries": ["art gallery interior"],
    "museums": ["museum interior", "museum exhibit"],
    "workshops": ["craft workshop", "art workshop"],
    "crafts": ["handicraft India", "artisan craft"],
    "shopping-markets": ["shopping mall interior India", "market India"],
    "outdoors": ["park India", "outdoor recreation"],
    "adventure": ["adventure sports", "amusement park ride"],
    "photography": ["photography studio"],
    "family": ["family entertainment center"],
    "nightlife": ["nightclub interior", "bar interior"],
    "music": ["live music venue", "concert stage"],
    "community": ["community center India"],
    "hidden-gems": ["local landmark India"],
    "wellness": ["spa interior", "yoga studio"],
    "entertainment": ["arcade games", "entertainment center"],
    "local-experiences": ["local experience India"],
}


@dataclass(frozen=True)
class ImageMatch:
    """Normalized resolution result — maps 1:1 onto the Experience
    image_* columns (src/models/experience.py)."""

    image_url: str
    thumbnail_url: str
    source: str  # "wikimedia_commons"
    source_url: str
    source_id: str
    license: str | None
    license_url: str | None
    author: str | None
    attribution_text: str
    is_place_specific: bool
    is_synthetic: bool  # always False for Wikimedia
    matched_by: MatchMethod
    match_score: float
    latitude: float | None
    longitude: float | None
    distance_km: float | None
    retrieved_at: datetime


def normalize_name(name: str) -> str:
    """Lowercase, Unicode-normalize, strip punctuation/whitespace, and
    drop common venue-name suffixes so near-identical names compare
    equal (task requirement #9)."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Strip common trailing descriptors that vary between our title and a
    # Commons file's caption without changing what place is meant.
    for suffix in (" pvt ltd", " private limited", " llp", " inc", " ltd"):
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
    return text


_STOPWORDS = {
    "the", "a", "an", "and", "of", "in", "at", "for",
    "mall", "centre", "center", "pvt", "ltd", "private", "limited",
    # Wikimedia file-title boilerplate — never a signal of what the image
    # actually depicts, so it must not dilute the Jaccard token overlap.
    "file", "jpg", "jpeg", "png", "svg", "gif", "webp", "tif", "tiff",
}
# Deliberately NOT stripped as generic stopwords even though they recur
# often: removing "mumbai"/"india" collapsed genuine two-word names like
# "KidZania Mumbai" down to a single significant token ("kidzania"),
# which then tripped the single-shared-token rejection floor below and
# turned true positives into false negatives.


def _name_tokens(name: str) -> set[str]:
    return {t for t in normalize_name(name).split() if t and t not in _STOPWORDS}


def name_similarity(a: str, b: str) -> float:
    """Deterministic token-overlap similarity in [0, 1]. Exact
    normalized-string match short-circuits to 1.0.

    A SINGLE shared significant token is deliberately never enough to
    call this a match, no matter how high the resulting Jaccard/
    containment ratio would be — real-world testing against live
    Wikimedia data found this rejects false positives such as a shared
    common brand word ("Timezone" matching an unrelated branch in a
    different country) or a shared surname ("Ajmera" matching an
    unrelated person's uploaded photo) that happen to be the only
    overlapping token. At least two overlapping significant tokens (or
    a single-word candidate name that fully equals a single-word
    match) are required before any score above 0 is returned.

    Otherwise uses whichever is higher of: Jaccard index (penalizes
    both sides for unrelated extra tokens) and containment (all of the
    *shorter* token set's significant tokens present in the other) — a
    long Wikimedia file title like "KidZania Mumbai entrance play area"
    that contains every token of a shorter candidate name "KidZania
    Mumbai" should count as a strong match despite low Jaccard from its
    own extra descriptive words."""
    norm_a, norm_b = normalize_name(a), normalize_name(b)
    if norm_a and norm_a == norm_b:
        return 1.0

    tokens_a, tokens_b = _name_tokens(a), _name_tokens(b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b

    # Guard against single shared-token false positives (see docstring).
    # A single-significant-token candidate name (e.g. provider name
    # "Timezone" or "Ajmera" alone) is explicitly NOT exempted from this
    # floor — real-world testing found exactly that shape of false
    # positive (a common/short brand word or surname matching an
    # unrelated file that happens to contain the same single word).
    # Only a multi-token name has enough distinctiveness to ever pass.
    if len(intersection) < 2:
        return 0.0

    union = tokens_a | tokens_b
    jaccard = len(intersection) / len(union) if union else 0.0

    shorter, longer = (tokens_a, tokens_b) if len(tokens_a) <= len(tokens_b) else (tokens_b, tokens_a)
    containment = len(shorter & longer) / len(shorter) if shorter else 0.0

    return max(jaccard, containment)


def _ordered_significant_tokens(name: str) -> list[str]:
    """Like _name_tokens but preserves the original word order (a plain
    set has none) — required for phrase/adjacency checks, where "kidzania
    mumbai" and "mumbai kidzania" are not interchangeable."""
    return [t for t in normalize_name(name).split() if t and t not in _STOPWORDS]


def _contains_name_phrase(search_text: str, name: str) -> bool:
    """True when the candidate name's significant tokens appear as a
    contiguous phrase, in their original order (allowing the
    concatenated/no-space form too), inside the search text — not
    merely scattered anywhere.

    This is what distinguishes a genuine "Snow World" venue photo
    ("Photo from Snow world Hyderabad" / "Snowworldhyderabad.png") from
    an unrelated file that happens to contain the same two words apart
    and reordered ("Polo World Cup ... on Snow") — a real false positive
    found in live testing that plain token-overlap scoring could not
    tell apart, since both words are present either way."""
    tokens = _ordered_significant_tokens(name)
    if len(tokens) < 2:
        return False
    normalized_text = normalize_name(search_text)
    phrase = " ".join(tokens)
    concatenated = "".join(tokens)
    return phrase in normalized_text or concatenated in normalized_text.replace(" ", "")


def score_title_match(image: WikimediaImage, candidate_names: list[str]) -> float:
    """Score a title-search result against the experience's known names.
    A file whose title/categories share no meaningful token with any
    candidate name is treated as unrelated even though it matched the
    Commons full-text search (task requirement #31 — e.g. a venue's
    generic uploaded stock photo like "Natural Disaster06.jpg").

    A multi-word candidate name must appear as a contiguous phrase to
    reach the "strong" tier — scattered/reordered word overlap alone
    (e.g. "world" and "snow" both present but apart) is capped at the
    weaker tier even when token-overlap similarity is otherwise high."""
    search_text = f"{image.title} {' '.join(image.categories)}"
    best_similarity = 0.0
    best_is_phrase = False
    for name in candidate_names:
        similarity = name_similarity(search_text, name)
        if similarity <= 0:
            continue
        is_phrase = _contains_name_phrase(search_text, name) or len(_name_tokens(name)) == 1
        if similarity > best_similarity or (similarity == best_similarity and is_phrase and not best_is_phrase):
            best_similarity = similarity
            best_is_phrase = is_phrase

    if best_similarity >= 0.6 and best_is_phrase:
        return 80.0  # PRIORITY 2 — strong exact/near-exact name match
    if best_similarity >= 0.3:
        return 50.0  # weaker but real title/name match (or strong-but-scattered)
    return -100.0  # obviously unrelated despite matching full-text search


def score_geosearch_match(
    image: WikimediaImage, candidate_names: list[str], radius_km: float
) -> float:
    """Score a geosearch result — distance alone is never sufficient
    (task requirement #31); a title/category name signal is required to
    reach the "strong match" tier, otherwise it only qualifies as a weak
    contextual image."""
    search_text = f"{image.title} {' '.join(image.categories)}"
    name_score = max((name_similarity(search_text, name) for name in candidate_names), default=0.0)
    distance_km = image.distance_km if image.distance_km is not None else radius_km

    proximity_score = 30.0 * max(0.0, 1.0 - distance_km / radius_km) if radius_km > 0 else 0.0

    if name_score >= 0.3:
        return 60.0 + proximity_score  # PRIORITY 4 — proximity + name/category match
    if name_score > 0:
        return 20.0 + proximity_score
    return proximity_score - 10.0  # PRIORITY 5 — proximity only, weak signal


def score_semantic_match(image: WikimediaImage, category_terms: list[str]) -> float:
    """Category-fallback images always score low and are never
    place-specific — resolution quality alone (dimensions) contributes a
    small bonus (task's "+10 useful resolution")."""
    resolution_bonus = 10.0 if image.width >= 1200 and image.height >= 800 else 0.0
    return 25.0 + resolution_bonus


def _build_attribution_text(image: WikimediaImage) -> str:
    parts = ["Photo: Wikimedia Commons"]
    if image.author:
        parts.append(f"Author: {image.author}")
    if image.license:
        parts.append(f"License: {image.license}")
    return " · ".join(parts)


def _to_match(
    image: WikimediaImage, *, matched_by: MatchMethod, score: float, is_place_specific: bool
) -> ImageMatch:
    return ImageMatch(
        image_url=image.image_url,
        thumbnail_url=image.thumbnail_url,
        source="wikimedia_commons",
        source_url=image.description_url,
        source_id=image.title,
        license=image.license,
        license_url=image.license_url,
        author=image.author,
        attribution_text=_build_attribution_text(image),
        is_place_specific=is_place_specific,
        is_synthetic=False,
        matched_by=matched_by,
        match_score=score,
        latitude=image.latitude,
        longitude=image.longitude,
        distance_km=image.distance_km,
        retrieved_at=datetime.now(UTC),
    )


async def resolve_experience_image(
    *,
    experience_title: str,
    provider_name: str,
    location_name: str | None,
    category_slug: str,
    latitude: float,
    longitude: float,
    known_commons_file: str | None,
    adapter: WikimediaCommonsAdapter,
    settings: Settings,
) -> ImageMatch | None:
    """Runs the full priority ladder for one experience. Returns the
    highest-scoring match at or above `settings.wikimedia_min_match_score`,
    or None if nothing suitable was found — never a fabricated result."""
    candidate_names = [n for n in (experience_title, provider_name, location_name) if n]

    best: ImageMatch | None = None

    def _consider(match: ImageMatch) -> None:
        nonlocal best
        if best is None or match.match_score > best.match_score:
            best = match

    # PRIORITY 1 — exact Commons reference from the source record, when
    # the upstream dataset provides one (not Overture Places today).
    if known_commons_file:
        exact = await adapter.resolve_file(known_commons_file)
        if exact is not None:
            _consider(_to_match(exact, matched_by="exact_commons_link", score=100.0, is_place_specific=True))

    # PRIORITY 2 — exact/near-exact name match via title search.
    for name in candidate_names:
        results = await adapter.search_by_title(name, limit=settings.wikimedia_search_limit)
        for image in results:
            score = score_title_match(image, candidate_names)
            if score > 0:
                _consider(_to_match(image, matched_by="exact_title", score=score, is_place_specific=True))

    # If priority 1/2 already cleared a high-confidence bar, don't spend
    # more requests on weaker geographic/semantic tiers.
    if best is not None and best.match_score >= 80.0:
        return best if best.match_score >= settings.wikimedia_min_match_score else None

    # PRIORITY 4/5 — geosearch, escalating radius only if nothing found.
    for radius_m in settings.wikimedia_geosearch_radii_m:
        nearby = await adapter.search_nearby(
            latitude, longitude, radius_m, limit=settings.wikimedia_geosearch_limit
        )
        if not nearby:
            continue
        radius_km = radius_m / 1000.0
        for image in nearby:
            score = score_geosearch_match(image, candidate_names, radius_km)
            matched_by = "nearby_strong_match" if score >= 60.0 else "nearby_geographic"
            _consider(_to_match(image, matched_by=matched_by, score=score, is_place_specific=score >= 60.0))
        if best is not None and best.match_score >= 60.0:
            break

    if best is not None and best.match_score >= settings.wikimedia_min_match_score:
        return best

    # PRIORITY 6 — semantic/category fallback. Never claims place-specificity.
    for term in CATEGORY_SEARCH_TERMS.get(category_slug, []):
        results = await adapter.search_by_title(term, limit=settings.wikimedia_search_limit)
        for image in results:
            score = score_semantic_match(image, CATEGORY_SEARCH_TERMS.get(category_slug, []))
            _consider(_to_match(image, matched_by="semantic_fallback", score=score, is_place_specific=False))
        if best is not None and best.matched_by == "semantic_fallback":
            break

    if best is not None and best.match_score >= settings.wikimedia_min_match_score:
        return best
    return None


__all__ = [
    "ImageMatch",
    "CATEGORY_SEARCH_TERMS",
    "name_similarity",
    "normalize_name",
    "resolve_experience_image",
    "score_geosearch_match",
    "score_semantic_match",
    "score_title_match",
]
