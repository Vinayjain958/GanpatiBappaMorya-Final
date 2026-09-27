# tests/

Cross-app integration tests for LocaLens.

**Current tests**: None (Phase 0 — not yet created)

**Planned test types**:

| Type | Tool | Phase | Scope |
|---|---|---|---|
| API unit tests | pytest | 1 | Individual endpoints and services |
| API integration tests | pytest + HTTPX | 2+ | Full request-response cycles |
| Frontend unit tests | Vitest + Testing Library | 1 | React components |
| End-to-end tests | Playwright | 12 | Full user flows across both apps |
| Feasibility engine tests | pytest | 6 | All constraint types; edge cases |
| Ranking tests | pytest | 7 | Profile-based ranking correctness |

Note: Unit tests for individual apps live in their own `tests/` directories
(`apps/api/tests/`, `apps/web/src/__tests__/`).
This directory is for tests that span both apps.
