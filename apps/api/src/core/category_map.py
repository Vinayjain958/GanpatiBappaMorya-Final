"""Single source of truth for the LocaLens category taxonomy and the
mapping from Overture Places `categories.primary` (a.k.a. `basic_category`)
values into it. Used by the ingestion pipeline and by synthetic data
generation — nowhere else should category translation logic live.

The Overture side of this mapping was built by inspecting the actual
distinct `categories.primary` values returned for the Mumbai bounding box
against Overture release 2026-08-19.0 (see data/README.md). It is not
exhaustive of Overture's full taxonomy — only categories plausibly
relevant to local experience discovery are mapped; everything else
(real estate, banks, hospitals, IT companies, schools, ...) is
intentionally excluded from ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryDef:
    slug: str
    name: str
    description: str
    icon: str
    sort_order: int


CATEGORIES: list[CategoryDef] = [
    CategoryDef("food-drink", "Food & Drink", "Restaurants and dining spots.", "utensils", 1),
    CategoryDef("street-food", "Street Food", "Street food stalls and carts.", "soup", 2),
    CategoryDef("cafes", "Cafés", "Cafés, coffee shops, and bakeries.", "coffee", 3),
    CategoryDef("culture-heritage", "Culture & Heritage", "Heritage sites, temples, and landmarks.", "landmark", 4),
    CategoryDef("art-galleries", "Art & Galleries", "Art galleries and museums of art.", "palette", 5),
    CategoryDef("museums", "Museums", "History, science, and specialty museums.", "building-2", 6),
    CategoryDef("workshops", "Workshops", "Hands-on classes and skill-building sessions.", "hammer", 7),
    CategoryDef("crafts", "Crafts", "Craft studios and artisan shops.", "scissors", 8),
    CategoryDef("shopping-markets", "Shopping & Markets", "Local markets and independent shops.", "shopping-bag", 9),
    CategoryDef("outdoors", "Outdoors", "Parks, gardens, and open-air spaces.", "trees", 10),
    CategoryDef("adventure", "Adventure", "Tours and activity-based experiences.", "compass", 11),
    CategoryDef("photography", "Photography", "Photography spots and services.", "camera", 12),
    CategoryDef("family", "Family", "Family- and kid-friendly experiences.", "users", 13),
    CategoryDef("nightlife", "Nightlife", "Bars, breweries, and evening venues.", "moon", 14),
    CategoryDef("music", "Music", "Live music venues and performance spaces.", "music", 15),
    CategoryDef("community", "Community", "Community spaces, libraries, and gathering places.", "heart-handshake", 16),
    CategoryDef("hidden-gems", "Hidden Gems", "Lesser-known local finds.", "gem", 17),
    CategoryDef("wellness", "Wellness", "Spas, yoga, and wellness studios.", "sparkles", 18),
    CategoryDef("entertainment", "Entertainment", "Cinemas and entertainment venues.", "clapperboard", 19),
    CategoryDef("local-experiences", "Local Experiences", "Guided tours and locally hosted experiences.", "map", 20),
]

CATEGORY_SLUGS = {c.slug for c in CATEGORIES}

# Overture `categories.primary` -> LocaLens category slug.
# Only categories worth surfacing as a discoverable "experience" are
# included. A category may map to at most one slug.
OVERTURE_CATEGORY_MAP: dict[str, str] = {
    # food-drink
    "restaurant": "food-drink",
    "indian_restaurant": "food-drink",
    "fast_food_restaurant": "food-drink",
    "seafood_market": "food-drink",
    # cafes
    "cafe": "cafes",
    "coffee_shop": "cafes",
    "bakery": "cafes",
    "desserts": "cafes",
    # culture-heritage
    "landmark_and_historical_building": "culture-heritage",
    "monument": "culture-heritage",
    "hindu_temple": "culture-heritage",
    "church_cathedral": "culture-heritage",
    # museums
    "museum": "museums",
    "history_museum": "museums",
    "science_museum": "museums",
    "childrens_museum": "museums",
    "textile_museum": "museums",
    "civilization_museum": "museums",
    # art-galleries
    "art_gallery": "art-galleries",
    "art_museum": "art-galleries",
    "modern_art_museum": "art-galleries",
    "contemporary_art_museum": "art-galleries",
    "design_museum": "art-galleries",
    # workshops
    "art_school": "workshops",
    "dance_school": "workshops",
    "music_school": "workshops",
    "bartending_school": "workshops",
    # crafts
    "arts_and_crafts": "crafts",
    "craft_shop": "crafts",
    "bookbinding": "crafts",
    # shopping-markets
    "flea_market": "shopping-markets",
    "farmers_market": "shopping-markets",
    "bookstore": "shopping-markets",
    "health_market": "shopping-markets",
    "department_store": "shopping-markets",
    # outdoors
    "park": "outdoors",
    "beach": "outdoors",
    "botanical_garden": "outdoors",
    "hiking_trail": "outdoors",
    "nursery_and_gardening": "outdoors",
    "beach_resort": "outdoors",
    # adventure
    "amusement_park": "adventure",
    "go_kart_club": "adventure",
    "atv_rentals_and_tours": "adventure",
    "aerial_tours": "adventure",
    "boat_tours": "adventure",
    "boat_charter": "adventure",
    # photography
    "photography_store_and_services": "photography",
    "event_photography": "photography",
    "session_photography": "photography",
    # family
    "zoo": "family",
    "aquarium": "family",
    "kids_recreation_and_party": "family",
    # nightlife
    "bar": "nightlife",
    "dance_club": "nightlife",
    "brewery": "nightlife",
    "winery": "nightlife",
    "beer_garden": "nightlife",
    # music
    "music_venue": "music",
    "music_production": "music",
    "musical_instrument_store": "music",
    "theaters_and_performance_venues": "music",
    "theatre": "music",
    # community
    "religious_organization": "community",
    "library": "community",
    "community_services_non_profits": "community",
    # wellness
    "spas": "wellness",
    "yoga_studio": "wellness",
    "martial_arts_club": "wellness",
    "naturopathic_holistic": "wellness",
    # entertainment
    "cinema": "entertainment",
    "drive_in_theater": "entertainment",
    "sports_and_recreation_venue": "entertainment",
    "arts_and_entertainment": "entertainment",
    # local-experiences
    "tours": "local-experiences",
    "sightseeing_tour_agency": "local-experiences",
    "historical_tours": "local-experiences",
    "bus_tours": "local-experiences",
}
