"""Synthetic Experience Enrichment Service (Phase 12).

Provides deterministic, reproducible, category-aware synthetic data generation for:
  1. Ratings (1-5 star distributions mathematically aligned with reviews)
  2. Reviews (category-specific vocabulary, varied lengths, realistic constructive critique)
  3. Opening hours (category-aware schedules, overnight support, closed-day handling)
  4. Availability (bookable slots strictly within operating windows)

Adheres strictly to the LocaLens Hard Data-Truth Rule:
  All generated data is explicitly marked with source_type='synthetic_enrichment'
  and is_synthetic=True. Existing authoritative or seed data is strictly preserved.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src.core.category_map import CATEGORY_SLUGS
from src.models.availability import ExperienceAvailability
from src.models.experience import Experience
from src.models.opening_hour import ExperienceOpeningHour
from src.models.review import ExperienceReview

_MUMBAI_TZ = ZoneInfo("Asia/Kolkata")

# ─── Configuration Constants ───────────────────────────────────────────────
LOW_REVIEW_MIN = 6
LOW_REVIEW_MAX = 12
MEDIUM_REVIEW_MIN = 14
MEDIUM_REVIEW_MAX = 28
HIGH_REVIEW_MIN = 32
HIGH_REVIEW_MAX = 65

SYNTHETIC_DATA_ANCHOR = datetime(2026, 9, 26, 12, 0, 0, tzinfo=UTC)
SYNTHETIC_ENRICHMENT_VERSION = "v1"
DEFAULT_GLOBAL_SEED = 20260926
SYNTHETIC_AVAILABILITY_DAYS = 14
FALLBACK_DURATION_MINUTES = 90
FALLBACK_CAPACITY = 15


def get_seeded_rng(
    experience_id: str,
    version: str = SYNTHETIC_ENRICHMENT_VERSION,
    global_seed: int = DEFAULT_GLOBAL_SEED,
) -> random.Random:
    """Derives a deterministic random generator from stable Experience identity."""
    seed_str = f"{experience_id}:{version}:{global_seed}"
    seed_int = int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest(), 16) % (2**32)
    return random.Random(seed_int)


# ─── Category Vocabulary & Narrative Snippets ──────────────────────────────
# Aligned directly with apps/api/src/core/category_map.py CATEGORY_SLUGS.

_REVIEW_TEMPLATES: dict[str, dict[int, list[tuple[str, str]]]] = {
    "food-drink": {
        5: [
            ("Sensational culinary experience", "The flavors were authentic and bold. Every dish arrived piping hot and beautifully plated. Attentive staff and vibrant atmosphere."),
            ("Outstanding meal and warm hospitality", "One of the best dining experiences in the neighborhood. The local specialties were executed with perfection. Generous portions too."),
            ("Exceptional food and great ambience", "A fantastic spot for an evening meal. The spice balance was spot on, and the recommendations from the server were marvelous."),
        ],
        4: [
            ("Delicious food, slight wait for seating", "The food quality is undeniably top tier. Rich gravies and fresh ingredients. Be prepared for a short wait during peak dinner hours."),
            ("Very satisfying local dining", "Loved the regional specialties and the lively setting. Portions are hearty. Service was a tad slow because the place was packed, but well worth it."),
            ("Great taste and reasonable pricing", "Thoroughly enjoyed the menu options. Clean tables and quick billing. Parking nearby can be tricky, so take a cab."),
        ],
        3: [
            ("Decent food but quite crowded", "The flavors were fairly good, though a couple of dishes felt slightly average for the price point. Very noisy during the evening rush."),
            ("Standard dining experience", "Portion sizes were fine and taste was acceptable. Staff seemed rushed. Okay for a quick bite if you are in the area."),
        ],
        2: [
            ("Overcrowded and long delays", "We had to wait over forty minutes for our main order. While the food was warm, the ambience was too chaotic to enjoy properly."),
            ("Did not quite live up to expectations", "The seating was cramped and several popular menu items were already out of stock by 8 PM."),
        ],
        1: [
            ("Disappointing visit", "Long wait times and the staff mix-up delayed our starters. Several dishes were lukewarm by the time they reached our table."),
        ],
    },
    "cafes": {
        5: [
            ("Charming retreat with brilliant brews", "Superb artisan coffee and wonderfully fresh bakes. The calm aesthetic makes it an ideal spot to read or catch up with friends."),
            ("Top-tier coffee and cozy vibe", "The cold brew and cinnamon rolls were fantastic. Extremely polite baristas and soothing background music."),
        ],
        4: [
            ("Great coffee and relaxed seating", "The espresso was pulled nicely and the sandwich was fresh. Seating is a bit limited on weekends, so arrive early."),
            ("Lovely neighbourhood cafe", "Comfortable corners, good Wi-Fi, and delicious herbal teas. Pricing is slightly on the premium side but justified by quality."),
        ],
        3: [
            ("Nice ambience, average snacks", "The coffee was decent, but the pastry was somewhat dry. Good natural lighting and quiet background for remote work."),
        ],
        2: [
            ("Cramped and noisy during afternoon hours", "The music was too loud for conversations, and the table was wobbly. Coffee was drinkable but nothing exceptional."),
        ],
        1: [
            ("Unsatisfactory service pace", "Waited nearly half an hour for two black coffees and a croissant. The space was humid and tables were not cleared promptly."),
        ],
    },
    "museums": {
        5: [
            ("Fascinating exhibits and immaculate curation", "An incredible treasure trove of history. Informative placards, well-lit display cases, and knowledgeable floor guides."),
            ("Deeply enriching cultural visit", "Spent nearly three hours exploring the galleries. The preservation work is top notch and the audio guide is very well produced."),
        ],
        4: [
            ("Well-maintained collection with rich history", "A very rewarding afternoon. The layout flows logically through historical eras. Could use a few more seating benches in the middle wings."),
            ("Informative and calm experience", "Great historical artifacts and concise explanations. The gift shop has thoughtful souvenirs. Worth a visit with family."),
        ],
        3: [
            ("Interesting artifacts, needs modern touch", "The collection itself is valuable, but some lighting fixtures were dim and several descriptive plaques were faded."),
        ],
        2: [
            ("Crowded with limited signage", "Navigating between rooms felt confusing due to lack of arrows. A couple of key galleries were closed for maintenance without prior notice."),
        ],
        1: [
            ("Poor crowd control during peak hours", "Too many visitors packed into narrow hallways, making it almost impossible to view the display cases properly."),
        ],
    },
    "culture-heritage": {
        5: [
            ("Stunning architectural landmark", "A breathtaking glimpse into Mumbai's storied heritage. The stonework and intricate details are mesmerizing. Best visited in the early morning."),
            ("Majestic atmosphere and rich legacy", "Steeped in history and beautifully preserved. Our guide shared captivating stories that brought the monument to life."),
        ],
        4: [
            ("Impressive heritage site", "Remarkable architecture and peaceful courtyard. Informative information boards. Keep in mind there is limited shade during midday sun."),
            ("Memorable cultural exploration", "A very photogenic landmark with timeless charm. Security was efficient. Best explored with comfortable walking shoes."),
        ],
        3: [
            ("Historic but heavily congested", "The structure is magnificent, but the surrounding lanes are extremely crowded and parking is virtually non-existent."),
        ],
        2: [
            ("Needs better visitor facilities", "Historical significance is undeniable, but clean drinking water and restroom facilities were hard to locate nearby."),
        ],
        1: [
            ("Chaotic entry process", "Long queues with unorganized ticketing queues on the day we visited. The monument was partially cordoned off."),
        ],
    },
    "adventure": {
        5: [
            ("Thrilling experience with fantastic guides", "An absolute adrenaline rush! The instructors gave a thorough safety briefing and the gear was in prime condition. Will definitely return."),
            ("Unforgettable fun and excitement", "Super well organized from start to finish. Felt completely safe while enjoying every moment of the activity."),
        ],
        4: [
            ("High energy and very engaging", "Great excitement and supportive team on ground. A bit tiring under the sun, so carry ample hydration. Overall a memorable outing."),
            ("Fun challenge for friends", "Solid safety measures and energetic marshals. The session started about fifteen minutes late, but they made up for it with extra track time."),
        ],
        3: [
            ("Good activity, brief session", "The core activity was enjoyable, though the actual duration felt somewhat shorter than advertised once the briefing ended."),
        ],
        2: [
            ("Lengthy queue between rounds", "We spent more time standing in line waiting our turn than actually doing the activity. Marshals seemed understaffed."),
        ],
        1: [
            ("Safety briefing was rushed", "Staff appeared impatient and safety gear looked noticeably worn out. Did not inspire confidence for beginners."),
        ],
    },
    "outdoors": {
        5: [
            ("Tranquil green sanctuary in the city", "Lush walkways, well-manicured lawns, and lovely old trees. A refreshing breath of fresh air amidst the urban hustle."),
            ("Peaceful open space and fresh breeze", "Perfect for morning strolls or quiet sunset contemplation. Clean pathways and well-maintained flowering beds."),
        ],
        4: [
            ("Pleasant nature walk", "Clean park with ample shade and plenty of birds chirping. Some sections were undergoing gardening, but still a relaxing stop."),
            ("Great spot for an evening unwinding", "Safe and family-friendly environment. Benches are plentiful. Litter bins are placed regularly along the main trail."),
        ],
        3: [
            ("Decent open ground, busy on weekends", "Nice green space, but it fills up very quickly on Sunday evenings with heavy foot traffic."),
        ],
        2: [
            ("Could use better path maintenance", "Several paving stones were loose along the walking track and lighting was relatively dim after dusk."),
        ],
        1: [
            ("Overcrowded and poorly kept", "Certain corners had accumulated litter and maintenance seemed neglected during our visit."),
        ],
    },
    "nightlife": {
        5: [
            ("Electrifying music and crafted cocktails", "The DJ set was phenomenal and the mixologist crafted wonderful signature drinks. Sleek aesthetic and lively crowd."),
            ("Brilliant night out", "Superb sound system, quick bar service despite the weekend rush, and an unforgettable weekend vibe."),
        ],
        4: [
            ("Great playlist and tasty appetizers", "Loved the ambient lighting and cocktail selection. Music volume gets loud past 10 PM, so come earlier if you want to converse."),
            ("Fun energetic evening", "Vibrant crowd and good craft beer selection. Entry process was smooth with reservation. Slightly high cover charge."),
        ],
        3: [
            ("Lively spot, very cramped bar", "Music was upbeat, but ordering at the counter required pushing through multiple rows of people. Average bar snacks."),
        ],
        2: [
            ("Too packed to move comfortably", "The venue clearly exceeded comfortable capacity. Bouncers were curt and getting drinks took over twenty minutes."),
        ],
        1: [
            ("Overbooked and disorganized entry", "Even with our confirmed slot, we were made to wait outside for nearly forty minutes without a clear explanation."),
        ],
    },
    "shopping-markets": {
        5: [
            ("Vibrant bazaar with incredible variety", "A kaleidoscope of colors, textiles, and local handicrafts. Bargaining was friendly and we found unique handcrafted items."),
            ("A shopper's paradise for local finds", "Bustling lanes filled with authentic local goods. Friendly stall owners and genuine bargains if you look around."),
        ],
        4: [
            ("Fascinating shopping walk", "Wide selection of traditional items and street fashion. It gets hot and crowded in the afternoons, so visit during the morning hours."),
            ("Great local bargains", "Found excellent artisanal goods at reasonable prices. Cash is preferred at many small stalls, so keep change handy."),
        ],
        3: [
            ("Extremely crowded alleyways", "Lots of interesting items, but walking through the dense crowd requires patience and cautious bag-watching."),
        ],
        2: [
            ("Overwhelming crowd and aggressive vendors", "Some stall keepers were overly pushy and walking lanes were choked with carts."),
        ],
        1: [
            ("Difficult to navigate and suffocatingly crowded", "Congestion was so severe that browsing was practically impossible. Lack of clear direction."),
        ],
    },
    "entertainment": {
        5: [
            ("Endless fun and well-maintained games", "A fantastic place to spend a couple of hours. High-tech arcade machines, responsive VR, and helpful attendants."),
            ("Superb entertainment experience", "Great energy, clean machines, and easy redemption process for prize tickets. Entertaining for all age groups."),
        ],
        4: [
            ("Enjoyable outing with friends", "Plenty of game choices from classic arcade to modern simulators. Ticket redemption takes a few minutes during peak hours."),
            ("Lots of activity options", "Fun atmosphere and upbeat music. Game card recharging was seamless via the digital kiosks."),
        ],
        3: [
            ("Good games, somewhat pricey per credit", "Kids enjoyed the racing simulators, but the play credits deplete quite quickly. Gets noisy on holidays."),
        ],
        2: [
            ("Several machines were out of order", "At least four of the marquee multiplayer games were sporting maintenance signs during our weekend visit."),
        ],
        1: [
            ("Overcrowded and long token queues", "Long lines at the recharge desk and multiple arcade games experienced coin feeder jams."),
        ],
    },
    "wellness": {
        5: [
            ("Blissful, restorative experience", "Utterly serene environment from the moment you step in. The therapist was exceptionally skilled and the herbal oils were divine."),
            ("Impeccable hygiene and soothing therapy", "Left feeling completely refreshed and de-stressed. Soft acoustic music and herbal infusion served after the session."),
        ],
        4: [
            ("Very relaxing massage therapy", "Clean therapy rooms, polite front desk, and skilled masseur. The steam room was slightly on the hotter side but well maintained."),
            ("Peaceful oasis", "Calming aroma throughout the facility. Timely appointment start and professional treatment. Recommended for a self-care day."),
        ],
        3: [
            ("Decent therapy, front desk was distracted", "The massage itself was competent, but the check-in process took fifteen minutes due to billing system lag."),
        ],
        2: [
            ("Could hear corridor noise during session", "Therapy room was not sufficiently soundproofed, so conversations from the reception kept breaking the tranquility."),
        ],
        1: [
            ("Delayed session start and rushed treatment", "The therapist started fifteen minutes late and ended on the original schedule, cutting the session short."),
        ],
    },
    "generic": {
        5: [
            ("Wonderful local discovery", "Everything about this experience was thoughtfully curated. Knowledgeable host, welcoming atmosphere, and great value for money."),
            ("Highly recommended experience", "Thoroughly enjoyable from start to finish. The attention to detail made this a standout highlight of our week."),
        ],
        4: [
            ("Very pleasant experience", "Well organized and engaging. Staff was courteous and the venue was spotless. Would gladly recommend to visitors."),
            ("Solid outing with great atmosphere", "Informative and memorable. Arrive a few minutes ahead of your slot for smooth check-in."),
        ],
        3: [
            ("Fair experience, matches expectations", "Nothing to complain about, but nothing particularly extraordinary either. Good if you are nearby."),
        ],
        2: [
            ("Average flow and slight delays", "Check-in felt disorganized and the overall activity felt somewhat hurried towards the end."),
        ],
        1: [
            ("Did not match expectations", "The listing description promised more than what was delivered on ground. Could definitely be better organized."),
        ],
    },
}


def _get_templates_for_category(category_slug: str) -> dict[int, list[tuple[str, str]]]:
    """Retrieves vocabulary templates for a category, falling back to generic."""
    if category_slug in _REVIEW_TEMPLATES:
        return _REVIEW_TEMPLATES[category_slug]

    # Semantic grouping for remaining slugs in CATEGORY_SLUGS
    mapping = {
        "street-food": "food-drink",
        "art-galleries": "museums",
        "workshops": "generic",
        "crafts": "shopping-markets",
        "photography": "outdoors",
        "family": "entertainment",
        "music": "nightlife",
        "community": "generic",
        "hidden-gems": "culture-heritage",
        "local-experiences": "generic",
    }
    target = mapping.get(category_slug, "generic")
    return _REVIEW_TEMPLATES.get(target, _REVIEW_TEMPLATES["generic"])


# ─── Popularity & Review Count Logic ───────────────────────────────────────

def compute_review_count(experience: Experience, rng: random.Random) -> int:
    """Computes a deterministic review count using category signals and experience duration."""
    high_volume_categories = {"food-drink", "street-food", "cafes", "museums", "culture-heritage", "entertainment", "nightlife"}
    low_volume_categories = {"workshops", "crafts", "photography", "hidden-gems", "community"}

    slug = experience.category.slug if experience.category else "generic"

    if slug in high_volume_categories or (experience.duration_minutes and experience.duration_minutes >= 120):
        # 60% high, 40% medium
        tier = "high" if rng.random() < 0.60 else "medium"
    elif slug in low_volume_categories or (experience.duration_minutes and experience.duration_minutes <= 30):
        # 70% low, 30% medium
        tier = "low" if rng.random() < 0.70 else "medium"
    else:
        tier = "medium"

    if tier == "high":
        return rng.randint(HIGH_REVIEW_MIN, HIGH_REVIEW_MAX)
    if tier == "low":
        return rng.randint(LOW_REVIEW_MIN, LOW_REVIEW_MAX)
    return rng.randint(MEDIUM_REVIEW_MIN, MEDIUM_REVIEW_MAX)


# ─── Review Generator ──────────────────────────────────────────────────────

def generate_synthetic_reviews(
    experience: Experience,
    rng: random.Random,
    version: str = SYNTHETIC_ENRICHMENT_VERSION,
) -> list[ExperienceReview]:
    """Generates a realistic, varied, deterministic list of ExperienceReview objects."""
    count = compute_review_count(experience, rng)
    category_slug = experience.category.slug if experience.category else "generic"
    templates = _get_templates_for_category(category_slug)

    # Controlled rating probability distribution:
    # 5 stars: ~50%, 4 stars: ~33%, 3 stars: ~11%, 2 stars: ~4%, 1 star: ~2%
    # This guarantees realistic positive bias with genuine criticism present.
    rating_choices = [5, 4, 3, 2, 1]
    rating_weights = [0.50, 0.33, 0.11, 0.04, 0.02]

    reviews: list[ExperienceReview] = []

    # Historical date distribution: spread over past 30 to 700 days
    # Newer experiences (indicated by created_at or lower id hash) get shorter windows
    created_at_utc = (
        experience.created_at.replace(tzinfo=UTC)
        if experience.created_at.tzinfo is None
        else experience.created_at.astimezone(UTC)
    )
    max_days_back = min(700, max(60, int((SYNTHETIC_DATA_ANCHOR - created_at_utc).total_seconds() / 86400)))

    for seq in range(count):
        # Guaranteed representation: ensure first reviews sample varied ratings
        if seq == 0:
            star = 5
        elif seq == 1:
            star = 4
        elif seq == 2 and count >= 10:
            star = 3
        elif seq == 3 and count >= 25:
            star = 2
        elif seq == 4 and count >= 40:
            star = 1
        else:
            star = rng.choices(rating_choices, weights=rating_weights, k=1)[0]

        star_templates = templates.get(star) or templates.get(4) or _REVIEW_TEMPLATES["generic"][4]
        title_base, body_base = star_templates[seq % len(star_templates)]

        # Add natural variation to title and narrative
        prefixes = ["", "Overall: ", "Quick review: ", "Visit recap: "]
        pfx = prefixes[rng.randint(0, len(prefixes) - 1)]
        title = f"{pfx}{title_base}"[:160]

        # Natural timestamp spread
        days_ago = rng.uniform(2, max_days_back)
        hours_ago = rng.uniform(0, 23)
        minutes_ago = rng.uniform(0, 59)
        reviewed_at = SYNTHETIC_DATA_ANCHOR - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)

        author_id = (seq % 80) + 1
        author_name = f"Traveler {author_id:02d}"

        review = ExperienceReview(
            experience_id=experience.id,
            rating_value=star,
            title=title,
            body=body_base,
            author_display_name=author_name,
            language="en",
            reviewed_at=reviewed_at,
            source_type="synthetic_enrichment",
            source_name="LocaLens synthetic review generator",
            is_synthetic=True,
            is_enriched=False,
            generation_version=version,
            synthetic_sequence=seq,
        )
        reviews.append(review)

    return reviews


# ─── Opening Hours Profiles ────────────────────────────────────────────────

@dataclass(frozen=True)
class OpeningHourSchedule:
    day_of_week: int  # 0=Monday .. 6=Sunday
    open_time: str | None  # "HH:MM"
    close_time: str | None  # "HH:MM"
    is_closed: bool


def generate_synthetic_opening_hours(
    experience: Experience, rng: random.Random
) -> list[OpeningHourSchedule]:
    """Generates category-aware weekly opening hours with realistic variation."""
    slug = experience.category.slug if experience.category else "generic"

    # Seeded minor variations (e.g. opens 08:00 vs 08:30)
    variant = rng.randint(0, 2)

    schedules: list[OpeningHourSchedule] = []

    if slug == "cafes":
        open_t = ["07:30", "08:00", "08:30"][variant]
        close_t = ["20:30", "21:00", "22:00"][variant]
        for day in range(7):
            schedules.append(OpeningHourSchedule(day, open_t, close_t, False))

    elif slug in ("food-drink", "street-food"):
        open_t = ["11:00", "11:30", "12:00"][variant]
        close_t = ["22:30", "23:00", "23:30"][variant]
        for day in range(7):
            schedules.append(OpeningHourSchedule(day, open_t, close_t, False))

    elif slug in ("museums", "art-galleries"):
        open_t = ["10:00", "10:30", "10:00"][variant]
        close_t = ["17:00", "17:30", "18:00"][variant]
        # Traditional museum practice: closed on Mondays (day 0)
        schedules.append(OpeningHourSchedule(0, None, None, True))
        for day in range(1, 7):
            schedules.append(OpeningHourSchedule(day, open_t, close_t, False))

    elif slug in ("culture-heritage", "hidden-gems"):
        open_t = ["09:00", "09:30", "09:00"][variant]
        close_t = ["17:30", "18:00", "18:30"][variant]
        for day in range(7):
            schedules.append(OpeningHourSchedule(day, open_t, close_t, False))

    elif slug in ("adventure", "outdoors"):
        open_t = ["06:30", "07:00", "07:30"][variant]
        close_t = ["18:00", "18:30", "19:00"][variant]
        for day in range(7):
            schedules.append(OpeningHourSchedule(day, open_t, close_t, False))

    elif slug == "nightlife":
        # Overnight operating window: e.g. 19:30 to 01:30 next morning
        open_t = ["19:00", "19:30", "20:00"][variant]
        close_t = ["01:30", "02:00", "02:30"][variant]
        for day in range(7):
            schedules.append(OpeningHourSchedule(day, open_t, close_t, False))

    elif slug in ("shopping-markets", "crafts"):
        open_t = ["10:30", "11:00", "11:00"][variant]
        close_t = ["21:00", "21:30", "22:00"][variant]
        for day in range(7):
            schedules.append(OpeningHourSchedule(day, open_t, close_t, False))

    elif slug == "entertainment":
        open_t = ["11:00", "11:30", "12:00"][variant]
        close_t = ["22:00", "22:30", "23:00"][variant]
        for day in range(7):
            schedules.append(OpeningHourSchedule(day, open_t, close_t, False))

    elif slug == "wellness":
        open_t = ["08:30", "09:00", "09:00"][variant]
        close_t = ["20:00", "20:30", "21:00"][variant]
        for day in range(7):
            schedules.append(OpeningHourSchedule(day, open_t, close_t, False))

    elif slug == "workshops":
        open_t = "10:00"
        close_t = "18:00"
        # Closed on Mondays
        schedules.append(OpeningHourSchedule(0, None, None, True))
        for day in range(1, 7):
            schedules.append(OpeningHourSchedule(day, open_t, close_t, False))

    else:  # generic / community / local-experiences / family / music / photography
        open_t = ["09:00", "09:30", "10:00"][variant]
        close_t = ["18:30", "19:00", "19:30"][variant]
        for day in range(7):
            schedules.append(OpeningHourSchedule(day, open_t, close_t, False))

    return schedules


# ─── Availability Slots Generator ──────────────────────────────────────────

def generate_synthetic_availability_slots(
    experience: Experience,
    opening_hours: list[ExperienceOpeningHour],
    rng: random.Random,
    days_forward: int = SYNTHETIC_AVAILABILITY_DAYS,
) -> list[ExperienceAvailability]:
    """Generates future bookable availability slots strictly within opening hours."""
    duration = experience.duration_minutes or FALLBACK_DURATION_MINUTES
    duration = max(30, min(240, duration))  # clamp between 30m and 4h
    capacity = experience.capacity or FALLBACK_CAPACITY
    capacity = max(1, capacity)

    # Index opening hours by day_of_week
    hours_by_day: dict[int, list[ExperienceOpeningHour]] = {}
    for h in opening_hours:
        hours_by_day.setdefault(h.day_of_week, []).append(h)

    slots: list[ExperienceAvailability] = []

    # Start tomorrow in local Mumbai timezone
    today_local = datetime.now(_MUMBAI_TZ).date()

    for day_offset in range(1, days_forward + 1):
        target_date = today_local + timedelta(days=day_offset)
        day_of_week = target_date.weekday()

        day_windows = hours_by_day.get(day_of_week, [])
        if not day_windows or all(w.is_closed for w in day_windows):
            continue  # Closed day -> zero slots

        for window in day_windows:
            if window.is_closed or not window.open_time or not window.close_time:
                continue

            open_h, open_m = map(int, window.open_time.split(":"))
            close_h, close_m = map(int, window.close_time.split(":"))

            is_overnight = (close_h, close_m) < (open_h, open_m)

            window_start_dt = datetime(
                target_date.year, target_date.month, target_date.day,
                open_h, open_m, tzinfo=_MUMBAI_TZ
            )

            if is_overnight:
                # Spans into next calendar day
                next_day = target_date + timedelta(days=1)
                window_end_dt = datetime(
                    next_day.year, next_day.month, next_day.day,
                    close_h, close_m, tzinfo=_MUMBAI_TZ
                )
            else:
                window_end_dt = datetime(
                    target_date.year, target_date.month, target_date.day,
                    close_h, close_m, tzinfo=_MUMBAI_TZ
                )

            total_window_minutes = int((window_end_dt - window_start_dt).total_seconds() / 60)
            if total_window_minutes < duration:
                continue  # Window cannot accommodate experience duration -> zero slots

            # Step interval: e.g. every duration or 60m
            step_minutes = max(duration, 60)

            current_start = window_start_dt
            while current_start + timedelta(minutes=duration) <= window_end_dt:
                slot_start = current_start
                slot_end = current_start + timedelta(minutes=duration)

                # Available slots variation
                available = rng.randint(max(1, capacity // 2), capacity)

                slot = ExperienceAvailability(
                    experience_id=experience.id,
                    starts_at=slot_start.astimezone(UTC),
                    ends_at=slot_end.astimezone(UTC),
                    capacity=capacity,
                    available_slots=available,
                    status="active",
                    source_type="synthetic_enrichment",
                    is_synthetic=True,
                )
                slots.append(slot)

                current_start += timedelta(minutes=step_minutes)

    return slots


# ─── Dataset Report & Quality Metrics Dataclass ────────────────────────────

@dataclass
class EnrichmentReport:
    experiences_inspected: int = 0
    experiences_with_existing_reviews: int = 0
    experiences_enriched_with_reviews: int = 0
    total_synthetic_reviews_added: int = 0
    total_reviews_in_db: int = 0
    average_synthetic_rating: float = 0.0
    rating_distribution: dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0})

    existing_authoritative_hours_preserved: int = 0
    existing_synthetic_hours_preserved: int = 0
    synthetic_hours_added: int = 0
    experiences_missing_hours_after: int = 0

    existing_authoritative_avail_preserved: int = 0
    existing_synthetic_avail_preserved: int = 0
    synthetic_avail_slots_added: int = 0
    experiences_without_avail_after: int = 0
