from __future__ import annotations


def test_list_categories_returns_seeded_category(client, seeded_ids) -> None:
    response = client.get("/api/v1/categories")
    assert response.status_code == 200
    slugs = [c["slug"] for c in response.json()]
    assert "food-drink" in slugs
