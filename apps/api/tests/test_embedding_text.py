"""Canonical text construction tests (Phase 6) — document text uses only
real stored fields (never fabricates missing ones), query text excludes
hard numeric constraints."""

from __future__ import annotations

from src.models.category import ExperienceCategory
from src.models.experience import Experience
from src.models.location import Location
from src.models.provider import Provider
from src.services.embedding_text import build_experience_document_text, build_query_text


def _make_experience(**overrides) -> Experience:
    category = ExperienceCategory(slug="culture-heritage", name="Culture & Heritage", sort_order=1)
    location = Location(
        latitude=18.93, longitude=72.83, city="Mumbai", locality="Fort",
        source_type="synthetic", is_synthetic=True,
    )
    provider = Provider(business_name="Test Co", source_type="synthetic", is_synthetic=True)
    defaults = dict(
        title="Heritage Walking Tour",
        short_description="A guided heritage walk.",
        full_description="A longer description of the heritage walking tour through Fort.",
        currency="INR", price=500.0, price_type="fixed", price_source="estimated",
        is_price_estimated=True, status="active", verification_status="unverified",
        opening_hours_status="unavailable", source_type="synthetic", is_synthetic=True,
    )
    defaults.update(overrides)
    return Experience(provider=provider, category=category, location=location, **defaults)


def test_document_text_includes_real_fields():
    exp = _make_experience(tags=["walking", "history"])
    doc = build_experience_document_text(exp)
    assert "Heritage Walking Tour" in doc.text
    assert "Culture & Heritage" in doc.text
    assert "walking" in doc.text
    assert "Fort" in doc.text


def test_document_text_omits_missing_fields_never_fabricates():
    exp = _make_experience(tags=None, suitability=None)
    doc = build_experience_document_text(exp)
    # No rating/hours/availability/accessibility text should ever appear —
    # they simply aren't in the builder's field list at all.
    assert "rating" not in doc.text.lower()
    assert "wheelchair" not in doc.text.lower()
    assert "available" not in doc.text.lower()


def test_document_text_hash_changes_with_content():
    exp1 = _make_experience(short_description="Version one.")
    exp2 = _make_experience(short_description="Version two, totally different.")
    doc1 = build_experience_document_text(exp1)
    doc2 = build_experience_document_text(exp2)
    assert doc1.content_hash != doc2.content_hash


def test_document_text_hash_stable_for_same_content():
    exp1 = _make_experience()
    exp2 = _make_experience()
    doc1 = build_experience_document_text(exp1)
    doc2 = build_experience_document_text(exp2)
    assert doc1.content_hash == doc2.content_hash


def test_document_preserves_is_synthetic_flag():
    exp = _make_experience(is_synthetic=True)
    doc = build_experience_document_text(exp)
    assert doc.is_synthetic is True


def test_query_text_excludes_hard_constraints():
    text = build_query_text(raw_query="cheap food for 4 people under 2 hours", interests=["food"])
    # The builder itself never appends budget/duration/party-size text —
    # whatever the raw_query happens to contain is the caller's business,
    # but the builder adds no additional hard-constraint content.
    assert "budget_max" not in text
    assert "party_size" not in text


def test_query_text_includes_semantic_fields_only():
    text = build_query_text(
        raw_query=None,
        interests=["street food", "history"],
        category="Food & Drink",
        location_text="Fort, Mumbai",
    )
    assert "street food" in text
    assert "Food & Drink" in text
    assert "Fort, Mumbai" in text
