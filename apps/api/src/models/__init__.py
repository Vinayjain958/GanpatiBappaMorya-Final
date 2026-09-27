"""SQLAlchemy models. Import every model here so Alembic autogenerate and
Base.metadata.create_all() can discover them via a single import."""

from src.core.db import Base
from src.models.affinity import TravelerAffinity
from src.models.auth_session import AuthSession
from src.models.availability import ExperienceAvailability
from src.models.booking_request import BookingRequest
from src.models.category import ExperienceCategory
from src.models.context_snapshot import ContextSnapshot
from src.models.conversation_message import ConversationMessage
from src.models.conversation_session import ConversationSession
from src.models.embedding import ExperienceEmbedding
from src.models.experience import Experience
from src.models.interaction import TravelerInteraction
from src.models.itinerary import Itinerary
from src.models.itinerary_custom_activity import ItineraryCustomActivity
from src.models.itinerary_item import ItineraryItem
from src.models.itinerary_revision import ItineraryRevision
from src.models.location import Location
from src.models.opening_hour import ExperienceOpeningHour
from src.models.preference import TravelerPreference
from src.models.provider import Provider
from src.models.provider_notification import ProviderNotification
from src.models.provider_synthetic_demand import ProviderSyntheticDemandSnapshot
from src.models.traveler import Traveler
from src.models.user import User
from src.models.review import ExperienceReview
from src.models.safety import EmergencyContact, EmergencyAlert
from src.models.collab import (
    CollabDecision,
    CollabDecisionOption,
    CollabGroup,
    CollabItinerary,
    CollabItineraryApproval,
    CollabItineraryItem,
    CollabItineraryTrip,
    CollabMember,
    CollabMemberPreferences,
    CollabVote,
    CollabWishlistItem,
    CollabWishlistReaction,
)

__all__ = [
    "Base",
    "User",
    "Traveler",
    "Provider",
    "ExperienceCategory",
    "Location",
    "Experience",
    "ExperienceOpeningHour",
    "AuthSession",
    "ExperienceAvailability",
    "ExperienceReview",
    "ConversationSession",
    "ConversationMessage",
    "ExperienceEmbedding",
    "TravelerInteraction",
    "TravelerPreference",
    "TravelerAffinity",
    "Itinerary",
    "ItineraryItem",
    "ItineraryCustomActivity",
    "BookingRequest",
    "ItineraryRevision",
    "ContextSnapshot",
    "ProviderNotification",
    "ProviderSyntheticDemandSnapshot",
    "EmergencyContact",
    "EmergencyAlert",
    "CollabGroup",
    "CollabMember",
    "CollabMemberPreferences",
    "CollabWishlistItem",
    "CollabWishlistReaction",
    "CollabDecision",
    "CollabDecisionOption",
    "CollabVote",
    "CollabItinerary",
    "CollabItineraryItem",
    "CollabItineraryApproval",
    "CollabItineraryTrip",
]
