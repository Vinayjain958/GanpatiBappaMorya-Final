import hashlib
from datetime import datetime, timedelta, UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import Settings
from src.models.booking_request import BookingRequest
from src.models.experience import Experience
from src.models.interaction import TravelerInteraction
from src.models.provider import Provider
from src.models.provider_notification import ProviderNotification
from src.repositories.notification_repository import NotificationRepository
from src.services.provider_intelligence.provider_matching import ProviderTravelerMatchService


class ProviderNotificationService:
    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings
        self.repo = NotificationRepository(session)
        self.matching = ProviderTravelerMatchService(session, settings)

    async def maybe_notify_provider(self, interaction: TravelerInteraction, experience: Experience) -> None:
        if interaction.event_type not in ("SAVE", "COMPLETE", "RATING"):
            return
            
        provider_stmt = select(Provider).where(Provider.id == experience.provider_id)
        provider = (await self.session.execute(provider_stmt)).scalar_one_or_none()
        
        if not provider or provider.source_type != "registered":
            return
            
        exp_stmt = select(Experience).where(Experience.provider_id == provider.id).options(selectinload(Experience.category))
        experiences = list((await self.session.execute(exp_stmt)).scalars().all())
        provider_category_slugs = list(set([e.category_slug for e in experiences]))
        
        score, qualified, evidence_codes = await self.matching.compute_match(
            provider_id=provider.id,
            traveler_id=interaction.traveler_id,
            provider_category_slugs=provider_category_slugs,
            experiences=experiences,
            trigger_interaction=interaction
        )
        
        if not qualified:
            return
            
        raw_key = f"{provider.id}:{interaction.traveler_id}:BEHAVIORAL_MATCH"
        cooldown_key = hashlib.sha256(raw_key.encode()).hexdigest()[:32]
        
        now = datetime.now(UTC)
        since = now - timedelta(days=self.settings.provider_notification_cooldown_days)
        
        existing = await self.repo.get_by_cooldown_key(provider.id, cooldown_key, since)
        if existing:
            return
            
        title = "New traveler match!"
        body = f"A traveler has shown strong interest in your experiences."
        
        segment_summary = []
        if "RECENT_SAVE" in evidence_codes: segment_summary.append("Recently Saved")
        if "CATEGORY_ALIGNMENT" in evidence_codes: segment_summary.append("Category Match")
        if "PREFERENCE_ALIGNMENT" in evidence_codes: segment_summary.append("Preference Match")
        if "BUDGET_ALIGNMENT" in evidence_codes: segment_summary.append("Budget Match")
        if "DURATION_ALIGNMENT" in evidence_codes: segment_summary.append("Duration Match")
        if "REPEATED_RECENT_INTERACTION" in evidence_codes: segment_summary.append("Highly Engaged")
        
        notif = ProviderNotification(
            provider_id=provider.id,
            type="BEHAVIORAL_MATCH",
            title=title,
            body=body,
            experience_id=experience.id,
            match_score=score,
            segment_summary=segment_summary,
            source_event_id=interaction.id,
            source_booking_request_id=None,
            traveler_id=interaction.traveler_id,
            cooldown_key=cooldown_key,
        )
        self.repo.add(notif)


    async def notify_booking_request(self, booking: BookingRequest, experience: Experience, provider: Provider | None = None) -> None:
        if not provider:
            provider_stmt = select(Provider).where(Provider.id == experience.provider_id)
            provider = (await self.session.execute(provider_stmt)).scalar_one_or_none()
            
        if not provider or provider.source_type != "registered":
            return
            
        if booking.status != "REQUESTED":
            return
            
        raw_key = f"{provider.id}:{booking.id}:BOOKING_REQUEST"
        cooldown_key = hashlib.sha256(raw_key.encode()).hexdigest()[:32]
        
        now = datetime.now(UTC)
        since = now - timedelta(days=3650) # practically forever
        
        existing = await self.repo.get_by_cooldown_key(provider.id, cooldown_key, since)
        if existing:
            return
            
        notif = ProviderNotification(
            provider_id=provider.id,
            type="BOOKING_REQUEST",
            title=f"New booking request for {experience.title}",
            body="A traveler has requested to book this experience.",
            experience_id=experience.id,
            match_score=None,
            segment_summary=None,
            source_event_id=None,
            source_booking_request_id=booking.id,
            traveler_id=None,
            cooldown_key=cooldown_key,
        )
        self.repo.add(notif)
