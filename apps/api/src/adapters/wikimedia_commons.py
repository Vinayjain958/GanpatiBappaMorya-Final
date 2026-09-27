"""WikimediaCommonsAdapter — real, unauthenticated Wikimedia Commons image
lookup (action=query on commons.wikimedia.org/w/api.php).

No API key: Wikimedia's public MediaWiki API requires none, but every
request must carry a meaningful identifying User-Agent per
https://meta.wikimedia.org/wiki/User-Agent_policy — see
Settings.wikimedia_user_agent.

Same adapter pattern as src/adapters/poi.py (Overpass)/geocoding.py
(Nominatim): shared httpx client (src/core/http_client.py),
IntervalRateLimiter, TTLCache. Never exposes raw MediaWiki response
shapes to the rest of the application — everything is normalized to
WikimediaImage before leaving this module.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from src.adapters.errors import AdapterUnavailableError
from src.core.cache import TTLCache
from src.core.config import Settings
from src.core.http_client import get_http_client
from src.core.rate_limit import IntervalRateLimiter

# File-namespace search results whose titles/categories indicate the file
# is not a photograph of a place — logos, maps, icons, flags, portraits,
# screenshots, diagrams — are rejected outright regardless of match score
# (task requirement: never select maps/logos/icons/flags/portraits/
# screenshots/technical images). Flags are allowed only when the category
# search itself is for a landmark (handled by the caller, not here).
_REJECTED_TITLE_PATTERNS = re.compile(
    r"\b(logo|icon|flag|map|diagram|chart|screenshot|favicon|wordmark|"
    r"emblem|coat of arms|seal of|signature|stub|placeholder|blank|"
    r"question mark|no image|noimage|under construction|wiki letter|"
    r"symbol)\b",
    re.IGNORECASE,
)
_REJECTED_CATEGORY_PATTERNS = re.compile(
    r"\b(logos|icons|flags|maps|diagrams|screenshots|clip art|"
    r"stub images|wikimedia sister projects)\b",
    re.IGNORECASE,
)

# Minimum pixel dimensions to reject obviously-too-small/broken thumbnails.
_MIN_WIDTH_PX = 300
_MIN_HEIGHT_PX = 200

# Only real raster photo formats — Commons also hosts PDFs, SVGs (mostly
# diagrams/logos already caught by _looks_rejectable, but not always),
# audio/video, and other document types that MediaWiki's imageinfo API
# still happily reports pixel dimensions for (e.g. a PDF's rendered page
# size) and are otherwise indistinguishable from a real photo by width/
# height alone — a real bug found via the full-dataset enrichment run,
# where a PDF titled "UNESCO_WORLD_HERITAGE_SITE_IN_INDIAN.pdf" was
# selected as a "photo" for several unrelated experiences.
_ALLOWED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


@dataclass(frozen=True)
class WikimediaImage:
    """Normalized Wikimedia Commons file result — the only shape the rest
    of the application ever sees. Never fabricated: every field is taken
    directly from the MediaWiki API response, license/attribution fields
    are validated present before this is constructed (see
    src/services/experience_images.py)."""

    title: str  # "File:Example.jpg"
    page_id: int
    image_url: str
    thumbnail_url: str
    description_url: str
    width: int
    height: int
    license: str | None
    license_url: str | None
    author: str | None
    attribution_required: bool
    categories: list[str]
    latitude: float | None
    longitude: float | None
    distance_km: float | None  # populated only by geosearch results


class WikimediaCommonsAdapter(Protocol):
    async def search_by_title(self, query: str, *, limit: int) -> list[WikimediaImage]: ...

    async def search_nearby(
        self, lat: float, lng: float, radius_m: int, *, limit: int
    ) -> list[WikimediaImage]: ...

    async def resolve_file(self, title: str) -> WikimediaImage | None: ...


class MockWikimediaCommonsAdapter:
    """Used when Wikimedia is disabled/unreachable. Never fabricates a
    plausible-looking image — returns nothing."""

    async def search_by_title(self, query: str, *, limit: int) -> list[WikimediaImage]:
        return []

    async def search_nearby(self, lat: float, lng: float, radius_m: int, *, limit: int) -> list[WikimediaImage]:
        return []

    async def resolve_file(self, title: str) -> WikimediaImage | None:
        return None


def _strip_html(value: str | None) -> str | None:
    """Wikimedia's extmetadata Artist/Credit fields are HTML fragments
    (e.g. an <a> tag around a username) — never rendered as raw HTML
    (task requirement: sanitize attribution text). Tags are stripped and
    entities unescaped, leaving plain text only."""
    if not value:
        return None
    text = re.sub(r"<[^>]+>", "", value)
    text = html.unescape(text).strip()
    return text or None


def _extract_meta(extmetadata: dict[str, Any], key: str) -> str | None:
    entry = extmetadata.get(key)
    if not isinstance(entry, dict):
        return None
    value = entry.get("value")
    return str(value) if value not in (None, "") else None


def _looks_rejectable(title: str, categories: list[str]) -> bool:
    if _REJECTED_TITLE_PATTERNS.search(title):
        return True
    return any(_REJECTED_CATEGORY_PATTERNS.search(c) for c in categories)


class RealWikimediaCommonsAdapter:
    """Real Wikimedia Commons-backed implementation."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._limiter = IntervalRateLimiter(settings.wikimedia_min_interval_seconds)
        self._cache: TTLCache[list[WikimediaImage]] = TTLCache(settings.wikimedia_cache_ttl_seconds)
        self._file_cache: TTLCache[WikimediaImage | None] = TTLCache(settings.wikimedia_cache_ttl_seconds)

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        await self._limiter.wait()
        client = get_http_client()
        request_params = {**params, "format": "json"}
        try:
            response = await client.get(
                self._settings.wikimedia_api_base_url,
                params=request_params,
                headers={"User-Agent": self._settings.wikimedia_user_agent},
                timeout=httpx.Timeout(self._settings.wikimedia_request_timeout_seconds),
            )
        except httpx.TimeoutException as exc:
            raise AdapterUnavailableError("Wikimedia Commons request timed out") from exc
        except httpx.HTTPError as exc:
            raise AdapterUnavailableError(f"Wikimedia Commons request failed: {exc}") from exc

        if response.status_code == 429:
            raise AdapterUnavailableError("Wikimedia Commons rate-limited this client (HTTP 429)")
        if response.status_code >= 400:
            raise AdapterUnavailableError(f"Wikimedia Commons returned HTTP {response.status_code}")

        try:
            body = response.json()
        except ValueError as exc:
            raise AdapterUnavailableError("Wikimedia Commons returned malformed JSON") from exc
        if not isinstance(body, dict):
            raise AdapterUnavailableError("Wikimedia Commons returned an unexpected payload shape")
        return body

    def _normalize_imageinfo_page(
        self, page: dict[str, Any], *, distance_km: float | None = None
    ) -> WikimediaImage | None:
        imageinfo_list = page.get("imageinfo")
        if not isinstance(imageinfo_list, list) or not imageinfo_list:
            return None
        info = imageinfo_list[0]
        if not isinstance(info, dict):
            return None

        title = page.get("title", "")
        if not title.lower().endswith(_ALLOWED_IMAGE_EXTENSIONS):
            return None

        width = info.get("width")
        height = info.get("height")
        if not isinstance(width, int) or not isinstance(height, int):
            return None
        if width < _MIN_WIDTH_PX or height < _MIN_HEIGHT_PX:
            return None

        extmetadata = info.get("extmetadata") or {}
        categories_raw = _extract_meta(extmetadata, "Categories") or ""
        categories = [c.strip() for c in categories_raw.split("|") if c.strip()]

        if _looks_rejectable(title, categories):
            return None

        image_url = info.get("url")
        thumb_url = info.get("thumburl") or image_url
        description_url = info.get("descriptionurl")
        if not isinstance(image_url, str) or not isinstance(description_url, str):
            return None

        license_short = _extract_meta(extmetadata, "LicenseShortName")
        license_url = _extract_meta(extmetadata, "LicenseUrl")
        author = _strip_html(_extract_meta(extmetadata, "Artist"))
        attribution_required_raw = _extract_meta(extmetadata, "AttributionRequired")
        attribution_required = (attribution_required_raw or "").lower() == "true"

        # License/attribution metadata must be resolvable to reuse the
        # image responsibly (task requirement: reject when missing).
        if not license_short and not license_url:
            return None

        coords = page.get("coordinates")
        lat = lng = None
        if isinstance(coords, list) and coords and isinstance(coords[0], dict):
            lat = coords[0].get("lat")
            lng = coords[0].get("lon")

        return WikimediaImage(
            title=title,
            page_id=int(page.get("pageid", 0)),
            image_url=image_url,
            thumbnail_url=thumb_url if isinstance(thumb_url, str) else image_url,
            description_url=description_url,
            width=width,
            height=height,
            license=license_short,
            license_url=license_url,
            author=author,
            attribution_required=attribution_required,
            categories=categories,
            latitude=lat,
            longitude=lng,
            distance_km=distance_km,
        )

    async def resolve_file(self, title: str) -> WikimediaImage | None:
        # Note: a cache hit that is genuinely None (file existed but was
        # rejected/had no usable imageinfo) is indistinguishable from a
        # miss here, so it is simply re-resolved — acceptable since a
        # rejected file is cheap to re-check and rare in practice.
        cache_key = f"file:{title}"
        cached = self._file_cache.get(cache_key)
        if cached is not None:
            return cached

        body = await self._get(
            {
                "action": "query",
                "titles": title,
                "prop": "imageinfo|coordinates",
                "iiprop": "url|extmetadata|size",
                "iiurlwidth": 800,
            }
        )
        pages = (body.get("query") or {}).get("pages") or {}
        result: WikimediaImage | None = None
        for page in pages.values():
            if not isinstance(page, dict) or "missing" in page:
                continue
            result = self._normalize_imageinfo_page(page)
            if result is not None:
                break

        self._file_cache.set(cache_key, result)
        return result

    async def search_by_title(self, query: str, *, limit: int = 10) -> list[WikimediaImage]:
        normalized_query = " ".join(query.strip().split())
        if not normalized_query:
            return []
        cache_key = f"search:{normalized_query.lower()}:{limit}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        body = await self._get(
            {
                "action": "query",
                "list": "search",
                "srsearch": normalized_query,
                "srnamespace": 6,  # File: namespace
                "srlimit": limit,
            }
        )
        search_results = ((body.get("query") or {}).get("search")) or []
        titles = [r["title"] for r in search_results if isinstance(r, dict) and "title" in r]
        if not titles:
            self._cache.set(cache_key, [])
            return []

        results: list[WikimediaImage] = []
        for title in titles:
            image = await self.resolve_file(title)
            if image is not None:
                results.append(image)

        self._cache.set(cache_key, results)
        return results

    async def search_nearby(self, lat: float, lng: float, radius_m: int, *, limit: int = 20) -> list[WikimediaImage]:
        cache_key = f"geo:{round(lat, 4)}:{round(lng, 4)}:{radius_m}:{limit}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        body = await self._get(
            {
                "action": "query",
                "list": "geosearch",
                "gscoord": f"{lat}|{lng}",
                "gsradius": radius_m,
                "gsnamespace": 6,
                "gslimit": limit,
            }
        )
        geo_results = ((body.get("query") or {}).get("geosearch")) or []
        results: list[WikimediaImage] = []
        for entry in geo_results:
            if not isinstance(entry, dict) or "title" not in entry:
                continue
            image = await self.resolve_file(entry["title"])
            if image is None:
                continue
            dist_km = entry.get("dist")
            results.append(
                WikimediaImage(
                    **{
                        **image.__dict__,
                        "distance_km": (dist_km / 1000.0) if isinstance(dist_km, (int, float)) else None,
                        "latitude": entry.get("lat", image.latitude),
                        "longitude": entry.get("lon", image.longitude),
                    }
                )
            )

        self._cache.set(cache_key, results)
        return results


__all__ = [
    "MockWikimediaCommonsAdapter",
    "RealWikimediaCommonsAdapter",
    "WikimediaCommonsAdapter",
    "WikimediaImage",
]
