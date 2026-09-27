# LocaLens — Product Contract

> **HackCelestial 3.0 · PS-6 — Local & Experiences — Intelligent Local Discovery & Experience Platform**

---

## 1. Product Purpose

LocaLens is an AI-powered local experience discovery and matching platform.

It helps travelers discover, evaluate, and plan local experiences using natural language and voice — accounting for who they are, where they are, what they want, how much time they have, their budget, their group, and real-world constraints.

It simultaneously gives local experience providers a profile, visibility, traveler matching, and demand intelligence.

---

## 2. Target Users

### Traveler

Any person exploring a location who wants personalized, feasible, context-aware experience recommendations — not a generic search result list.

Sub-profiles:

- Solo traveler
- Friends group
- Couple
- Family with children
- Business traveler with free time
- Local explorer (resident discovering own city)

### Local Provider

Any person or small business that offers a local experience:

- Street food vendor / restaurant / café
- Cultural venue (gallery, heritage site, museum)
- Tour guide / walking tour operator
- Workshop / craft studio
- Outdoor activity operator
- Local events organizer

---

## 3. Traveler Experience

### What the traveler can do:

1. Describe what they want in plain language or by voice
2. Share their location (current or planned)
3. Specify time, budget, group size, preferences, accessibility needs
4. Receive a personalized, feasible experience recommendation or mini-itinerary
5. Ask follow-up questions conversationally
6. Trigger dynamic replanning when conditions change
7. Save, rate, and review experiences
8. Receive increasingly personalized recommendations over time

### What the traveler should feel:

> *"This understands what I actually want."*
> *"It checked whether this is actually possible for me."*
> *"It adapted when my plans changed."*

---

## 4. Provider Experience

### What the provider can do:

1. Create a provider profile
2. List experiences with full details (description, category, pricing, availability, capacity, location, accessibility, media)
3. See how many travelers viewed, saved, or booked their experience
4. See demand trends (e.g., which traveler types are most interested)
5. Receive qualified traveler matches
6. Gain operational insights to improve their offering

### What the provider should feel:

> *"Travelers who find me here are actually a good fit."*
> *"I understand what demand looks like."*
> *"I can improve my offering based on real intelligence."*

---

## 5. Primary Problem Being Solved

**Generic search is not discovery.**

Existing tools present undifferentiated lists of POIs or restaurants. They do not:

- Understand the traveler's full context
- Check whether an experience is actually feasible given constraints
- Personalize ranking to this specific traveler's profile
- Compose multiple compatible experiences into a coherent plan
- Adapt when real-world conditions change
- Connect travelers meaningfully with providers

---

## 6. Core Differentiator

> **LocaLens moves from search to understanding.**

| Dimension | Generic Platforms | LocaLens |
|---|---|---|
| Input | Keywords / categories | Natural language / voice |
| Understanding | None | Full traveler context extraction |
| Feasibility | None | Deterministic constraint engine |
| Personalization | Generic rating sort | ML-ranked by traveler affinity |
| Composition | User does it manually | AI composes compatible plans |
| Adaptation | User redoes search | Dynamic replanning engine |
| Provider side | Listing directory | Two-sided marketplace with intelligence |
| Voice | Not core | Core interaction modality |

---

## 7. Major Capabilities

Status labels: `IMPLEMENTED` | `PARTIAL` | `PLANNED` | `NOT IMPLEMENTED`

| Capability | Status |
|---|---|
| Natural language traveler input | `IMPLEMENTED` (Phase 5 — text conversational discovery) |
| Voice interaction via Gemini Live | `IMPLEMENTED` (Phase 5 — real mic capture/playback/tool-calling; WebSocket voice path NOT VERIFIED, needs a real browser mic session, see docs/DECISIONS.md ADR-035) |
| Conversational context maintenance | `IMPLEMENTED` (Phase 5 — bounded recent-history window) |
| Structured intent/context extraction | `IMPLEMENTED` (Phase 5 — `TravelerContext`, understand + retrieve only, not feasibility) |
| Experience catalog (open-data + synthetic, read API) | `IMPLEMENTED` (Phase 4 — full keyword/category/price/duration/radius/sort search) |
| OSM/Nominatim/Overpass/OSRM location layer + MapLibre map | `IMPLEMENTED` (Phase 4 — geocoding, nearby-POI, routing/travel-time, real map rendering) |
| Deterministic feasibility engine | `IMPLEMENTED` (Phase 6 — tri-state FEASIBLE/INFEASIBLE/UNKNOWN verdict, zero LLM calls, 11 constraint checks, verified on SQLite) |
| Semantic retrieval (pgvector) | `PARTIAL` (Phase 6 — SQLite Python cosine similarity + keyword fallback IMPLEMENTED and LIVE VERIFIED; pgvector production path IMPLEMENTED but NOT VERIFIED, no PostgreSQL instance available) |
| Personalized ML ranking | `IMPLEMENTED` (Phase 7 — deterministic weighted ranking; a budget-filter bug was found and fixed this reconciliation, see docs/DECISIONS.md ADR-055) |
| Traveler affinity model | `IMPLEMENTED` (Phase 7) |
| Feedback & learning | `IMPLEMENTED` (Phase 7) |
| AI experience composer | `IMPLEMENTED` (Phase 8 — Gemini narrative LIVE VERIFIED) |
| Itinerary planning | `IMPLEMENTED` (Phase 8) |
| Booking request flow | `IMPLEMENTED` (Phase 8 — request intent only, REQUESTED/ACCEPTED/DECLINED, no payment) |
| Real-time context (weather, traffic, events) | `IMPLEMENTED` (Phase 9 — OpenWeather + Ticketmaster adapters LIVE VERIFIED with real API keys this reconciliation) |
| Opt-in public social context | `PARTIAL` (Task 3 — aggregate area-level Bluesky signals are wired into the itinerary map; live provider access is unavailable in this environment) |
| Itinerary what-if previews | `PARTIAL` (Task 4 — read-only preview and explicit version-checked apply implemented; authenticated itinerary smoke verification pending) |
| Dynamic replanning | `IMPLEMENTED` (Phase 9 — see docs/DECISIONS.md ADR-055 for bugs found and fixed this reconciliation) |
| Provider profiles & listings | `IMPLEMENTED` (Phase 3 — profile + owner-scoped experience/availability CRUD) |
| Provider intelligence & analytics | `PLANNED` (Phase 10) |
| Two-sided marketplace matching | `PLANNED` (Phase 10) |
| Safety & emergency module | `PLANNED` (Phase 11) |
| Authentication & roles | `IMPLEMENTED` (Phase 3) |

---

## Task 4 Simulation Contract

What-if scenarios are traveler-facing previews. Current itinerary data is
ownership-checked and used as the baseline; assumptions remain clearly
hypothetical, while fetched weather, route, and social evidence retains its
actual status. The preview is ephemeral and does not decide feasibility or
safety or mutate the itinerary. Only an explicit traveler action can apply a
still-current preview, through the existing replanning service.

## 8. Non-Goals

The following are explicitly **out of scope** for LocaLens:

- Full online payment processing
- Accommodation booking (hotels, Airbnb)
- Long-haul flight or transport booking
- General social media or user content feed (LocaLens shows only optional, area-level aggregate context; no individual posts or profiles)
- Nationwide or international travel planning (focus: local/hyperlocal)
- Competing with OTAs (Booking.com, MakeMyTrip, etc.)
- Real-time GPS turn-by-turn navigation

---

## 9. Demo Strategy

The hackathon demonstration must make the intelligence immediately obvious.

### Planned Demo Arc

**Setup:**
Traveler: *"I've got 3 hours near Fort. I'm with two friends. We want local food and something cultural, and we don't want to spend more than ₹1500."*

**System demonstrates:**
- Understanding the traveler's full context
- Retrieving candidate experiences from the local catalog
- Eliminating infeasible options (budget exceeded, closed, too far)
- Ranking suitable experiences by personalized score
- Composing a realistic mini-itinerary with time allocation

**Dynamic scenario 1 — time constraint:**
Traveler: *"Actually, we only have 90 minutes now."*

System re-evaluates, removes incompatible items, recomputes timing, produces a new plan.

**Dynamic scenario 2 — experience unavailable:**
System receives: *"Outdoor activity unavailable"*

System removes it, searches alternatives matching preferences, recomposes the plan.

**Important:**
This demo arc must emerge from the general architecture.
It must NOT be implemented as hardcoded special logic.
Seed data for Fort/Kala Ghoda area is acceptable as realistic demonstration data,
but the intelligence must be generalized — it must work for any location and context.
