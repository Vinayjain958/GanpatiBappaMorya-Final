"""WikimediaCommonsAdapter unit tests — fake HTTP client only, no live
network calls (tests/adapter_fakes.py pattern). Live verification lives
in tests/test_experience_images_live.py, run separately/manually."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from src.adapters.errors import AdapterUnavailableError
from src.adapters.wikimedia_commons import RealWikimediaCommonsAdapter
from src.core.config import Settings
from tests.adapter_fakes import FakeAsyncClient, make_response, sequence_responder

SEARCH_RESPONSE = {
    "query": {"search": [{"title": "File:Example Venue.jpg", "pageid": 111}]}
}

IMAGEINFO_RESPONSE = {
    "query": {
        "pages": {
            "111": {
                "pageid": 111,
                "title": "File:Example Venue.jpg",
                "imageinfo": [
                    {
                        "url": "https://upload.wikimedia.org/example.jpg",
                        "thumburl": "https://thumb.wikimedia.org/example_thumb.jpg",
                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Example_Venue.jpg",
                        "width": 1600,
                        "height": 1200,
                        "extmetadata": {
                            "LicenseShortName": {"value": "CC BY-SA 4.0"},
                            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"},
                            "Artist": {"value": '<a href="#">Jane Doe</a>'},
                            "AttributionRequired": {"value": "true"},
                            "Categories": {"value": "Venues|Example"},
                        },
                    }
                ],
            }
        }
    }
}

GEOSEARCH_RESPONSE = {
    "query": {
        "geosearch": [{"title": "File:Example Venue.jpg", "lat": 19.08, "lon": 72.93, "dist": 250.5}]
    }
}


def _settings(**overrides) -> Settings:
    return Settings(wikimedia_min_interval_seconds=0.0, **overrides)


def _install_fake_client(monkeypatch, fake: FakeAsyncClient) -> None:
    monkeypatch.setattr("src.adapters.wikimedia_commons.get_http_client", lambda: fake)


def test_search_by_title_sends_user_agent(monkeypatch) -> None:
    client = FakeAsyncClient(
        responder=sequence_responder(
            [make_response(200, SEARCH_RESPONSE), make_response(200, IMAGEINFO_RESPONSE)]
        )
    )
    _install_fake_client(monkeypatch, client)
    adapter = RealWikimediaCommonsAdapter(_settings(wikimedia_user_agent="TestApp/1.0 (test@example.com)"))

    asyncio.run(adapter.search_by_title("Example Venue", limit=5))

    assert client.calls[0]["headers"]["User-Agent"] == "TestApp/1.0 (test@example.com)"


def test_search_by_title_normalizes_result(monkeypatch) -> None:
    client = FakeAsyncClient(
        responder=sequence_responder(
            [make_response(200, SEARCH_RESPONSE), make_response(200, IMAGEINFO_RESPONSE)]
        )
    )
    _install_fake_client(monkeypatch, client)
    adapter = RealWikimediaCommonsAdapter(_settings())

    results = asyncio.run(adapter.search_by_title("Example Venue", limit=5))

    assert len(results) == 1
    image = results[0]
    assert image.image_url == "https://upload.wikimedia.org/example.jpg"
    assert image.license == "CC BY-SA 4.0"
    assert image.license_url == "https://creativecommons.org/licenses/by-sa/4.0"
    assert image.author == "Jane Doe"  # HTML stripped
    assert image.attribution_required is True
    assert image.categories == ["Venues", "Example"]


def test_geosearch_populates_distance_km(monkeypatch) -> None:
    client = FakeAsyncClient(
        responder=sequence_responder(
            [make_response(200, GEOSEARCH_RESPONSE), make_response(200, IMAGEINFO_RESPONSE)]
        )
    )
    _install_fake_client(monkeypatch, client)
    adapter = RealWikimediaCommonsAdapter(_settings())

    results = asyncio.run(adapter.search_nearby(19.08, 72.93, 1000, limit=10))

    assert len(results) == 1
    assert results[0].distance_km == pytest.approx(0.2505)


def test_missing_license_metadata_rejected(monkeypatch) -> None:
    bad_response = {
        "query": {
            "pages": {
                "111": {
                    "pageid": 111,
                    "title": "File:No License.jpg",
                    "imageinfo": [
                        {
                            "url": "https://upload.wikimedia.org/no_license.jpg",
                            "thumburl": "https://thumb.wikimedia.org/no_license_thumb.jpg",
                            "descriptionurl": "https://commons.wikimedia.org/wiki/File:No_License.jpg",
                            "width": 1600,
                            "height": 1200,
                            "extmetadata": {"Categories": {"value": "Example"}},
                        }
                    ],
                }
            }
        }
    }
    client = FakeAsyncClient(
        responder=sequence_responder([make_response(200, SEARCH_RESPONSE), make_response(200, bad_response)])
    )
    _install_fake_client(monkeypatch, client)
    adapter = RealWikimediaCommonsAdapter(_settings())

    results = asyncio.run(adapter.search_by_title("Example Venue", limit=5))

    assert results == []


def test_too_small_image_rejected(monkeypatch) -> None:
    small_response = {
        "query": {
            "pages": {
                "111": {
                    "pageid": 111,
                    "title": "File:Tiny.jpg",
                    "imageinfo": [
                        {
                            "url": "https://upload.wikimedia.org/tiny.jpg",
                            "thumburl": "https://thumb.wikimedia.org/tiny_thumb.jpg",
                            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Tiny.jpg",
                            "width": 50,
                            "height": 50,
                            "extmetadata": {
                                "LicenseShortName": {"value": "CC0"},
                                "Categories": {"value": "Example"},
                            },
                        }
                    ],
                }
            }
        }
    }
    client = FakeAsyncClient(
        responder=sequence_responder([make_response(200, SEARCH_RESPONSE), make_response(200, small_response)])
    )
    _install_fake_client(monkeypatch, client)
    adapter = RealWikimediaCommonsAdapter(_settings())

    results = asyncio.run(adapter.search_by_title("Example Venue", limit=5))

    assert results == []


def test_non_photo_file_type_rejected_even_with_valid_dimensions(monkeypatch) -> None:
    # Real bug found via the full-dataset enrichment run: a PDF's
    # rendered-page dimensions passed the width/height check and was
    # selected as a "photo" for several unrelated experiences.
    pdf_response = {
        "query": {
            "pages": {
                "333": {
                    "pageid": 333,
                    "title": "File:UNESCO WORLD HERITAGE SITE IN INDIAN.pdf",
                    "imageinfo": [
                        {
                            "url": "https://upload.wikimedia.org/x.pdf",
                            "thumburl": "https://thumb.wikimedia.org/x_thumb.png",
                            "descriptionurl": "https://commons.wikimedia.org/wiki/x",
                            "width": 1600,
                            "height": 1200,
                            "extmetadata": {
                                "LicenseShortName": {"value": "CC0"},
                                "Categories": {"value": "Example"},
                            },
                        }
                    ],
                }
            }
        }
    }
    search_response = {"query": {"search": [{"title": "File:UNESCO WORLD HERITAGE SITE IN INDIAN.pdf", "pageid": 333}]}}
    client = FakeAsyncClient(
        responder=sequence_responder([make_response(200, search_response), make_response(200, pdf_response)])
    )
    _install_fake_client(monkeypatch, client)
    adapter = RealWikimediaCommonsAdapter(_settings())

    results = asyncio.run(adapter.search_by_title("heritage site", limit=5))

    assert results == []


@pytest.mark.parametrize(
    "title",
    [
        "File:Company Logo.svg",
        "File:Location map India.png",
        "File:National Flag Icon.png",
        "File:App Screenshot.png",
    ],
)
def test_irrelevant_file_types_rejected(monkeypatch, title) -> None:
    search_response = {"query": {"search": [{"title": title, "pageid": 222}]}}
    imageinfo_response = {
        "query": {
            "pages": {
                "222": {
                    "pageid": 222,
                    "title": title,
                    "imageinfo": [
                        {
                            "url": "https://upload.wikimedia.org/x.jpg",
                            "thumburl": "https://thumb.wikimedia.org/x_thumb.jpg",
                            "descriptionurl": "https://commons.wikimedia.org/wiki/x",
                            "width": 1600,
                            "height": 1200,
                            "extmetadata": {
                                "LicenseShortName": {"value": "CC0"},
                                "Categories": {"value": "Example"},
                            },
                        }
                    ],
                }
            }
        }
    }
    client = FakeAsyncClient(
        responder=sequence_responder([make_response(200, search_response), make_response(200, imageinfo_response)])
    )
    _install_fake_client(monkeypatch, client)
    adapter = RealWikimediaCommonsAdapter(_settings())

    results = asyncio.run(adapter.search_by_title("query", limit=5))

    assert results == []


def test_timeout_raises_unavailable(monkeypatch) -> None:
    client = FakeAsyncClient(responder=lambda **_kwargs: (_ for _ in ()).throw(httpx.TimeoutException("timed out")))
    _install_fake_client(monkeypatch, client)
    adapter = RealWikimediaCommonsAdapter(_settings())

    with pytest.raises(AdapterUnavailableError):
        asyncio.run(adapter.search_by_title("Example Venue", limit=5))


def test_rate_limit_raises_unavailable(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(429)]))
    _install_fake_client(monkeypatch, client)
    adapter = RealWikimediaCommonsAdapter(_settings())

    with pytest.raises(AdapterUnavailableError):
        asyncio.run(adapter.search_by_title("Example Venue", limit=5))


def test_malformed_json_raises_unavailable(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, None)]))
    _install_fake_client(monkeypatch, client)
    adapter = RealWikimediaCommonsAdapter(_settings())

    with pytest.raises(AdapterUnavailableError):
        asyncio.run(adapter.search_by_title("Example Venue", limit=5))


def test_empty_search_results_returns_empty_list(monkeypatch) -> None:
    client = FakeAsyncClient(responder=sequence_responder([make_response(200, {"query": {"search": []}})]))
    _install_fake_client(monkeypatch, client)
    adapter = RealWikimediaCommonsAdapter(_settings())

    results = asyncio.run(adapter.search_by_title("Nonexistent Venue XYZ", limit=5))

    assert results == []
