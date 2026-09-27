from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.synthetic_data import generate_synthetic_dataset  # noqa: E402


def test_generate_synthetic_dataset_hits_targets() -> None:
    providers, experiences = generate_synthetic_dataset(target_experience_count=40, provider_count=20)
    assert len(providers) == 20
    assert len(experiences) == 40


def test_generate_synthetic_dataset_is_deterministic() -> None:
    providers_a, experiences_a = generate_synthetic_dataset(target_experience_count=30, provider_count=15, seed=42)
    providers_b, experiences_b = generate_synthetic_dataset(target_experience_count=30, provider_count=15, seed=42)
    assert [p.business_name for p in providers_a] == [p.business_name for p in providers_b]
    assert [e.title for e in experiences_a] == [e.title for e in experiences_b]


def test_generate_synthetic_dataset_titles_are_unique() -> None:
    _, experiences = generate_synthetic_dataset(target_experience_count=60, provider_count=40)
    titles = [e.title for e in experiences]
    assert len(titles) == len(set(titles))


def test_generate_synthetic_dataset_provider_names_are_unique() -> None:
    providers, _ = generate_synthetic_dataset(target_experience_count=10, provider_count=30)
    names = [p.business_name for p in providers]
    assert len(names) == len(set(names))


def test_generate_synthetic_dataset_experiences_reference_real_providers() -> None:
    providers, experiences = generate_synthetic_dataset(target_experience_count=25, provider_count=15)
    provider_keys = {p.key for p in providers}
    assert all(e.provider_key in provider_keys for e in experiences)
