# apps/web/

Next.js frontend for LocaLens.

**Phase**: 5 — Conversational AI + Gemini Live Voice Agent

## Stack

- Next.js 16 (App Router), React 19, TypeScript (strict)
- Tailwind CSS v4 — centralized design tokens in `app/globals.css`
- MapLibre GL JS v6 — real map rendering (OpenFreeMap tiles, no API key)
- `@google/genai` — Gemini Live browser SDK (real-time voice, ephemeral token only —
  `GEMINI_API_KEY` never reaches this app)
- Vitest + jsdom (dev only) — targeted unit tests for pure logic, see Checks below
- lucide-react icons

## Structure

```
apps/web/
├── app/                 ← Routes (App Router)
│   ├── login/, register/            ← Real auth forms
│   └── provider/experiences/        ← Full CRUD UI (list, new, [id] edit + availability)
├── components/
│   ├── ui/               ← Primitive design-system components
│   ├── layout/            ← Shell, header (role-aware), footer, page container
│   ├── navigation/         ← Nav link, mobile tab bar
│   ├── discovery/           ← Conversational input (real text + voice), LocationBar, filters,
│   │                          category chips
│   ├── experience/            ← Experience card, detail (route preview), AI composer preview
│   ├── voice/                   ← VoiceOrb, VoiceTranscriptPanel, VoiceControlButton
│   ├── trip/                      ← Itinerary timeline, replan banner
│   ├── provider/                    ← Provider listing rows, ExperienceForm (location picker),
│   │                                   AvailabilityManager
│   ├── safety/                        ← Emergency button, safety resource card
│   └── common/                          ← MapSurface (real MapLibre GL JS map), auth card,
│                                           RequireRole guard
├── lib/
│   ├── api/           ← Typed API client (auth-aware), auth.ts, providers.ts,
│   │                     experiencesWrite.ts, categories.ts, experiences.ts, location.ts,
│   │                     conversation.ts (conversations, tool-calls, live-token),
│   │                     feasibility.ts (semantic-search + feasibility/check, Phase 6)
│   ├── auth/            ← tokenStore.ts (in-memory access token), AuthContext.tsx
│   ├── config/         ← Browser-safe env config, map.ts (style URL, default center/zoom)
│   ├── geo/              ← haversine.ts, geojson.ts (FeatureCollection builder)
│   ├── discovery/          ← urlState.ts (discovery state ⇄ URL query params),
│   │                          travelerContextToPatch.ts (AI intent → DiscoveryState, app-owned)
│   ├── feasibility/          ← feasibilityDisplay.ts (pure badge/reason-code/status-summary
│   │                            mapping functions, Phase 6 — no business logic in components)
│   ├── voice/                ← audioCapture.ts, audioPlayback.ts, pcmResample.ts,
│   │                            geminiLiveClient.ts (the entire browser-side Gemini Live bridge)
│   ├── utils/                  ← cn() class merge helper
│   └── constants/                 ← Nav items, category/filter option lists
├── hooks/              ← useMediaQuery, useHealthCheck, useExperienceDiscovery,
│                          useUserLocation, useLocationSearch (all explicit-trigger only),
│                          useVoiceAgent, useTextConversation
├── types/               ← Domain types + api.ts (incl. Phase 6 FeasibilityVerdict/
│                           SemanticSearchRequest/RetrievalMode types), auth.ts, provider-api.ts,
│                           location.ts, discovery.ts, conversation.ts (TravelerContext, etc.)
├── mocks/                ← Presentation-only demo data (landing page + isolated UI testing)
├── public/worklets/       ← pcm-capture-worklet.js (AudioWorklet, mic → 16-bit/16kHz PCM)
└── proxy.ts              ← Optimistic route guard (Next.js 16 Proxy convention)
```

## Authentication at a glance

- The access token lives only in `lib/auth/tokenStore.ts` (a module-level variable) — never
  `localStorage`/`sessionStorage`/IndexedDB, and it's gone on every page reload.
- `lib/auth/AuthContext.tsx`'s `AuthProvider` (wrapping the app in `app/layout.tsx`) bootstraps
  a session on load by calling `/api/v1/auth/refresh`, which relies on the HttpOnly cookie the
  browser already holds — a normal signed-out visit just fails that call silently.
- `lib/api/client.ts` attaches the token as `Authorization: Bearer <token>` and sends
  `credentials: "include"` on every request; a 401 anywhere except login/register/refresh
  triggers exactly one shared refresh-and-retry.
- `proxy.ts` only checks whether a refresh cookie is *present* for `/trip`, `/saved`,
  `/provider*` — it's a UX redirect, not the security boundary (the backend enforces everything
  independently). `components/common/RequireRole.tsx` does the equivalent client-side render
  guard for role-specific pages.

## Local development

```bash
cd apps/web
npm install
npm run dev
```

App runs at `http://localhost:3000`. It expects the API at
`NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`). Use the same hostname
(`localhost` or `127.0.0.1`) consistently between the two when testing manually — cookies are
host-scoped.

## Checks

```bash
npm run lint
npx tsc --noEmit
npm run test    # Vitest — pure logic only (discovery-patch translator, PCM math)
npm run build
```

## Notes

- No business logic lives in components — see `docs/AI_CONTEXT.md` INV-3.
- The Discover page and experience detail page fetch real, database-backed
  data from `GET /api/v1/experiences` (list, with keyword/category/price/
  duration/radius/sort filters) and `/{id}` (detail) via
  `lib/api/experiences.ts`, mapped onto the UI `Experience` type by
  `lib/api/experienceAdapter.ts`. Run the backend (see `apps/api/README.md`)
  for these pages to show data — otherwise they render an `ErrorState`
  with retry, never a silent fake fallback.
- `MapSurface` renders a real MapLibre GL JS map; if map initialization
  fails (e.g. style fetch blocked), it shows a graceful fallback panel and
  the experience list beside it keeps working independently.
- Geolocation (`useUserLocation`) and place search (`useLocationSearch`)
  are explicit-trigger only — never requested automatically on page load —
  and neither is ever sent to any server for storage; see
  `docs/DECISIONS.md` ADR-032.
- Panning/zooming the map never auto-re-queries the API — only an explicit
  "Search this area" click does; see ADR-028.
- The provider dashboard and `/provider/experiences` never fabricate analytics — no views,
  saves, bookings, or conversion numbers are invented (see `docs/AI_CONTEXT.md` INV-8/INV-10).
  `/provider/insights` remains Phase 1 mock data, explicitly labelled `DemoDataBadge`.
- Mock data in `mocks/` is clearly labelled (`isSynthetic: true`) and is
  presentation-only, used for the landing page's illustrative cards and
  isolated UI testing — not wired to any ranking or retrieval logic.
- The microphone control in `ConversationalDiscoveryInput` is a real Gemini Live voice session
  (`useVoiceAgent`) — real mic capture, real playback, real tool-calling. It requires a working
  `GEMINI_API_KEY` on the backend; without one, `POST /auth/live-token` returns 503 and the
  button clearly shows unavailable rather than faking a connection. `GEMINI_API_KEY` itself
  never reaches this app — only a short-lived ephemeral token, held in memory only.
- Text submissions in `ConversationalDiscoveryInput` also run a real conversational turn
  (Gemini extracts `TravelerContext`, the app deterministically translates it into a
  `DiscoveryState` patch via `lib/discovery/travelerContextToPatch.ts` — never the model itself).
  A conversational location mention is never auto-geocoded; it stays informational only.
