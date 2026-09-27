"""Deterministic synthetic provider/experience generator.

Open POI data (Overture Places) does not describe guided experiences,
workshop durations, group capacity, or hosted local activities — it
describes places. This module fills that gap with a small, clearly
labelled (`is_synthetic=True`) layer of fictional-but-realistic demo
providers and experiences, built from controlled templates rather than
free generation, per docs/PRODUCT_CONTRACT.md's demo strategy.

Every business name, provider, and experience produced here is fictional.
Any resemblance to a real business is coincidental and unintended.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

NEIGHBORHOODS = [
    "Fort", "Kala Ghoda", "Colaba", "Churchgate", "Marine Drive",
    "Dadar", "Matunga", "Bandra", "Juhu", "Andheri", "Lower Parel", "Powai",
]

# Approximate neighborhood centroids (same set used by the ingestion
# script) with a small jitter applied per synthetic location so records
# don't all stack on one exact point.
NEIGHBORHOOD_CENTROIDS: dict[str, tuple[float, float]] = {
    "Fort": (72.8356, 18.9346),
    "Kala Ghoda": (72.8317, 18.9281),
    "Colaba": (72.8147, 18.9067),
    "Churchgate": (72.8267, 18.9354),
    "Marine Drive": (72.8235, 18.9440),
    "Dadar": (72.8438, 19.0176),
    "Matunga": (72.8570, 19.0270),
    "Bandra": (72.8295, 19.0596),
    "Juhu": (72.8263, 19.1075),
    "Andheri": (72.8468, 19.1197),
    "Lower Parel": (72.8300, 18.9960),
    "Powai": (72.9060, 19.1176),
}

PROVIDER_TYPE_TEMPLATES = [
    "{n} Studio Collective", "{n} Host Circle", "{n} Experience Co.",
    "{n} Heritage Trails", "{n} Creative Studio", "{n} Local Guides",
    "{n} Workshop House", "{n} Wellness Co.", "{n} Food Collective",
    "{n} Community Kitchen",
]

# category_slug -> (experience noun phrases, suitability defaults, provider_type)
CATEGORY_TEMPLATES: dict[str, dict] = {
    "street-food": {
        "phrases": ["Street Food Trail", "Chaat & Bites Crawl", "Night Market Tasting Walk"],
        "suitability": ["solo", "friends", "family"],
        "provider_type": "provider",
    },
    "hidden-gems": {
        "phrases": ["Hidden Lane Walk", "Offbeat Corner Discovery", "Secret Courtyard Visit"],
        "suitability": ["solo", "couple", "friends"],
        "provider_type": "guide",
    },
    "food-drink": {
        "phrases": ["Home Kitchen Tasting Menu", "Supper Club Evening", "Regional Thali Tasting"],
        "suitability": ["couple", "friends", "family"],
        "provider_type": "kitchen",
    },
    "cafes": {
        "phrases": ["Specialty Coffee Tasting", "Brew Bar Session", "Filter Coffee Cupping"],
        "suitability": ["solo", "couple", "friends"],
        "provider_type": "studio",
    },
    "culture-heritage": {
        "phrases": ["Heritage Walking Tour", "Temple & Lanes Walk", "Old City Storytelling Walk"],
        "suitability": ["solo", "friends", "family"],
        "provider_type": "guide",
    },
    "art-galleries": {
        "phrases": ["Gallery Hop", "Artist Studio Visit", "Contemporary Art Walkthrough"],
        "suitability": ["solo", "couple", "friends"],
        "provider_type": "studio",
    },
    "museums": {
        "phrases": ["Guided Museum Walkthrough", "Curator-Led Exhibit Tour"],
        "suitability": ["solo", "family", "friends"],
        "provider_type": "guide",
    },
    "workshops": {
        "phrases": ["Pottery Workshop", "Block Printing Workshop", "Hands-On Cooking Workshop"],
        "suitability": ["solo", "friends"],
        "provider_type": "workshop",
    },
    "crafts": {
        "phrases": ["Leathercraft Session", "Macrame Workshop", "Sketching & Journaling Session"],
        "suitability": ["solo", "friends"],
        "provider_type": "workshop",
    },
    "shopping-markets": {
        "phrases": ["Market Shopping Walk", "Bazaar Exploration Trail", "Local Makers Market Visit"],
        "suitability": ["solo", "friends", "family"],
        "provider_type": "guide",
    },
    "outdoors": {
        "phrases": ["Garden Morning Walk", "Waterfront Stroll", "Sunrise Park Walk"],
        "suitability": ["solo", "couple", "family"],
        "provider_type": "guide",
    },
    "adventure": {
        "phrases": ["Kayaking Session", "Cycling Trail Ride", "Coastal Trek"],
        "suitability": ["solo", "friends"],
        "provider_type": "operator",
    },
    "photography": {
        "phrases": ["Golden Hour Photo Walk", "Street Photography Session", "Architecture Photo Walk"],
        "suitability": ["solo", "couple", "friends"],
        "provider_type": "guide",
    },
    "family": {
        "phrases": ["Family Discovery Trail", "Kids Craft Afternoon", "Family Story Walk"],
        "suitability": ["family"],
        "provider_type": "operator",
    },
    "nightlife": {
        "phrases": ["Rooftop Evening Experience", "Live Music Night", "Sunset Terrace Evening"],
        "suitability": ["couple", "friends"],
        "provider_type": "venue",
    },
    "music": {
        "phrases": ["Live Music Session", "Open Mic Evening", "Acoustic Set Evening"],
        "suitability": ["solo", "couple", "friends"],
        "provider_type": "venue",
    },
    "community": {
        "phrases": ["Community Potluck", "Neighbourhood Meetup", "Skill-Share Evening"],
        "suitability": ["solo", "friends"],
        "provider_type": "collective",
    },
    "wellness": {
        "phrases": ["Sunrise Yoga Session", "Wellness Retreat Morning", "Guided Meditation Session"],
        "suitability": ["solo", "couple"],
        "provider_type": "studio",
    },
    "entertainment": {
        "phrases": ["Evening Entertainment Show", "Weekend Open-Air Screening"],
        "suitability": ["friends", "family", "couple"],
        "provider_type": "venue",
    },
    "local-experiences": {
        "phrases": ["Local Host Experience", "Neighbourhood Immersion Walk", "Day-in-the-Life Local Walk"],
        "suitability": ["solo", "friends", "family"],
        "provider_type": "guide",
    },
}

ESTIMATED_DURATION_MINUTES = {
    "food-drink": 90, "street-food": 60, "cafes": 60, "culture-heritage": 90,
    "art-galleries": 75, "museums": 90, "workshops": 120, "crafts": 105,
    "shopping-markets": 75, "outdoors": 75, "adventure": 150, "photography": 90,
    "family": 105, "nightlife": 120, "music": 105, "community": 90,
    "hidden-gems": 60, "wellness": 90, "entertainment": 120, "local-experiences": 150,
}

ESTIMATED_PRICE_RANGE = {
    "food-drink": (500, 1500), "street-food": (150, 500), "cafes": (250, 700),
    "culture-heritage": (200, 600), "art-galleries": (200, 700), "museums": (150, 500),
    "workshops": (800, 2500), "crafts": (600, 1800), "shopping-markets": (0, 500),
    "outdoors": (0, 300), "adventure": (900, 3500), "photography": (500, 1500),
    "family": (300, 1200), "nightlife": (600, 2000), "music": (300, 1200),
    "community": (0, 300), "hidden-gems": (200, 600), "wellness": (500, 2000),
    "entertainment": (300, 1000), "local-experiences": (600, 2200),
}

OPENING_HOUR_PRESETS: dict[str, list[tuple[int, str, str]]] = {
    "default": [(d, "10:00", "19:00") for d in range(6)],  # Mon-Sat
    "evening": [(d, "17:00", "23:00") for d in range(7)],
    "morning": [(d, "07:00", "12:00") for d in range(7)],
}

PROVIDER_TYPE_LABEL = {
    "provider": "Independent local vendor",
    "guide": "Independent local guide",
    "kitchen": "Home-hosted kitchen",
    "studio": "Creative studio",
    "workshop": "Workshop host",
    "operator": "Activity operator",
    "venue": "Independent venue",
    "collective": "Community collective",
}


@dataclass
class SyntheticProvider:
    key: str
    business_name: str
    provider_type: str
    city: str = "Mumbai"


@dataclass
class SyntheticExperience:
    provider_key: str
    category_slug: str
    title: str
    locality: str
    latitude: float
    longitude: float
    duration_minutes: int
    price_low: int
    price_high: int
    suitability: list[str]
    opening_hours: list[tuple[int, str, str]]


def _jitter(value: float, rng: random.Random, spread: float = 0.006) -> float:
    return round(value + rng.uniform(-spread, spread), 6)


def generate_synthetic_dataset(
    target_experience_count: int, provider_count: int = 50, seed: int = 20260922
) -> tuple[list[SyntheticProvider], list[SyntheticExperience]]:
    rng = random.Random(seed)

    providers: list[SyntheticProvider] = []
    used_provider_names: set[str] = set()
    provider_keys_by_type: dict[str, list[str]] = {}

    while len(providers) < provider_count:
        neighborhood = rng.choice(NEIGHBORHOODS)
        name_template = rng.choice(PROVIDER_TYPE_TEMPLATES)
        name = name_template.format(n=neighborhood)
        if name in used_provider_names:
            continue
        used_provider_names.add(name)
        provider_type = rng.choice(list(PROVIDER_TYPE_LABEL))
        key = f"synthetic-provider-{len(providers) + 1}"
        providers.append(SyntheticProvider(key=key, business_name=name, provider_type=provider_type))
        provider_keys_by_type.setdefault(provider_type, []).append(key)

    experiences: list[SyntheticExperience] = []
    used_titles: set[str] = set()
    category_slugs = list(CATEGORY_TEMPLATES)
    attempts = 0

    while len(experiences) < target_experience_count and attempts < target_experience_count * 20:
        attempts += 1
        category_slug = category_slugs[len(experiences) % len(category_slugs)]
        category_template = CATEGORY_TEMPLATES[category_slug]
        neighborhood = rng.choice(NEIGHBORHOODS)
        phrase = rng.choice(category_template["phrases"])
        title = f"{neighborhood} {phrase}"
        if title in used_titles:
            continue
        used_titles.add(title)

        provider_type = category_template["provider_type"]
        candidates = provider_keys_by_type.get(provider_type) or [p.key for p in providers]
        provider_key = rng.choice(candidates)

        lon, lat = NEIGHBORHOOD_CENTROIDS[neighborhood]
        duration = ESTIMATED_DURATION_MINUTES[category_slug]
        low, high = ESTIMATED_PRICE_RANGE[category_slug]

        preset_key = "evening" if category_slug in {"nightlife", "music", "entertainment"} else (
            "morning" if category_slug in {"outdoors", "wellness"} else "default"
        )

        experiences.append(
            SyntheticExperience(
                provider_key=provider_key,
                category_slug=category_slug,
                title=title,
                locality=neighborhood,
                latitude=_jitter(lat, rng),
                longitude=_jitter(lon, rng),
                duration_minutes=duration,
                price_low=low,
                price_high=high,
                suitability=category_template["suitability"],
                opening_hours=OPENING_HOUR_PRESETS[preset_key],
            )
        )

    return providers, experiences
