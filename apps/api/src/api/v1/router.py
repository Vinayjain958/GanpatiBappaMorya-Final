from __future__ import annotations

from fastapi import APIRouter

from src.api.v1 import (
    auth,
    availability,
    bookings,
    categories,
    collab,
    context,
    contributions,
    conversation,
    digital_twin,
    domain_intelligence,
    experiences,
    feasibility,
    feedback,
    health,
    itineraries,
    location,
    media,
    provider_intelligence,
    providers,
    recommendations,
    safety,
    twin,
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(categories.router)
api_v1_router.include_router(providers.router)
api_v1_router.include_router(experiences.router)
api_v1_router.include_router(contributions.router)
api_v1_router.include_router(media.router)
api_v1_router.include_router(availability.router)
api_v1_router.include_router(location.router)
api_v1_router.include_router(conversation.router)
api_v1_router.include_router(feasibility.router)
api_v1_router.include_router(recommendations.router)
api_v1_router.include_router(feedback.router)
api_v1_router.include_router(itineraries.router)
api_v1_router.include_router(bookings.router)
api_v1_router.include_router(context.router)
api_v1_router.include_router(provider_intelligence.router)
api_v1_router.include_router(safety.router)
api_v1_router.include_router(collab.router)
api_v1_router.include_router(twin.router)
api_v1_router.include_router(digital_twin.router)
api_v1_router.include_router(domain_intelligence.router)
