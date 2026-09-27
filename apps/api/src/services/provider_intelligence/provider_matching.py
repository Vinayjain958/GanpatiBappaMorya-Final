import math
from datetime import datetime, UTC

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.models.affinity import TravelerAffinity
from src.models.experience import Experience
from src.models.interaction import TravelerInteraction
from src.models.preference import TravelerPreference
from src.models.provider_notification import ProviderNotification
from src.schemas.provider_intelligence import ProviderMatchSummary

SIGNAL_WEIGHTS = {
    "IMPRESSION": 0.00,
    "VIEW": 0.05,
    "SAVE": 0.60,
    "COMPLETE": 0.70,
    "RATING_HIGH": 0.65,
    "BOOKING_REQUEST": 0.80,
    "SKIP": -0.20,
    "UNSAVE": -0.25,
}

class ProviderTravelerMatchService:
    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings

    async def get_recent_matches(self, provider_id: str, limit: int = 10) -> list[ProviderMatchSummary]:
        stmt = (
            select(ProviderNotification)
            .where(
                ProviderNotification.provider_id == provider_id,
                ProviderNotification.type == "BEHAVIORAL_MATCH"
            )
            .order_by(ProviderNotification.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        notifications = result.scalars().all()
        
        matches = []
        for notif in notifications:
            matches.append(ProviderMatchSummary(
                match_id=notif.id,
                score=notif.match_score or 0.0,
                model_version=self.settings.provider_match_model_version,
                qualified=True,
                segment_summary=notif.segment_summary or [],
                matched_experience_ids=[notif.experience_id] if notif.experience_id else [],
                evidence_codes=["RECENT_SAVE"] if notif.match_score else [], # simplistic fallback
                created_at=notif.created_at,
                is_synthetic=notif.is_synthetic,
            ))
        return matches

    async def compute_match(
        self, provider_id: str, traveler_id: str, provider_category_slugs: list[str],
        experiences: list[Experience],
        trigger_interaction: TravelerInteraction | None = None
    ) -> tuple[float, bool, list[str]]:
        """Returns (score, qualified, evidence_codes)."""
        # Feature 1: behavioral_interest
        stmt = select(TravelerInteraction).where(
            TravelerInteraction.traveler_id == traveler_id,
            TravelerInteraction.experience_id.in_([e.id for e in experiences])
        ).order_by(TravelerInteraction.created_at.desc())
        
        result = await self.session.execute(stmt)
        interactions = result.scalars().all()

        behavioral_score = 0.0
        now = datetime.now(UTC)
        has_qualifying_trigger = False
        evidence_codes = set()

        for interaction in interactions:
            ts = interaction.occurred_at or interaction.created_at
            days_ago = (now - ts).total_seconds() / 86400.0
            if days_ago < 0: days_ago = 0
            decay = math.exp(-math.log(2) / 14 * days_ago)
            
            ev_type = interaction.event_type
            if ev_type == "RATING":
                if interaction.rating and interaction.rating >= 4:
                    ev_type = "RATING_HIGH"
                else:
                    continue
            
            weight = SIGNAL_WEIGHTS.get(ev_type, 0.0)
            behavioral_score += weight * decay
            
            if ev_type in ("SAVE", "COMPLETE", "RATING_HIGH", "BOOKING_REQUEST"):
                has_qualifying_trigger = True
                if ev_type == "SAVE": evidence_codes.add("RECENT_SAVE")
                elif ev_type == "BOOKING_REQUEST": evidence_codes.add("BOOKING_REQUEST")

        if behavioral_score > 1.0: behavioral_score = 1.0
        elif behavioral_score < 0.0: behavioral_score = 0.0
        
        if len(interactions) > 2:
            evidence_codes.add("REPEATED_RECENT_INTERACTION")

        # Feature 2: category_alignment
        aff_stmt = select(TravelerAffinity).where(
            TravelerAffinity.traveler_id == traveler_id,
            TravelerAffinity.dimension_type == "category",
            TravelerAffinity.dimension_key.in_(provider_category_slugs)
        )
        aff_result = await self.session.execute(aff_stmt)
        affinities = aff_result.scalars().all()
        
        cat_score = 0.0
        if affinities:
            cat_score = sum(a.score for a in affinities) / len(provider_category_slugs)
            if cat_score > 0.5:
                evidence_codes.add("CATEGORY_ALIGNMENT")
        
        if cat_score > 1.0: cat_score = 1.0

        # Preference fits
        pref_stmt = select(TravelerPreference).where(TravelerPreference.traveler_id == traveler_id)
        pref = (await self.session.execute(pref_stmt)).scalar_one_or_none()

        pref_fit = 0.0
        budget_fit = 0.0
        duration_fit = 0.0
        recency_fit = 0.0

        if pref:
            # Preference fit (category overlaps)
            if pref.preferred_category_slugs:
                overlaps = set(pref.preferred_category_slugs).intersection(provider_category_slugs)
                if overlaps:
                    pref_fit = len(overlaps) / max(len(pref.preferred_category_slugs), 1)
                    evidence_codes.add("PREFERENCE_ALIGNMENT")

            # Budget fit
            provider_budgets = {e.price_band for e in experiences}
            if pref.budget_sensitivity in provider_budgets:
                budget_fit = 1.0
                evidence_codes.add("BUDGET_ALIGNMENT")

            # Duration fit
            dur = pref.preferred_duration_minutes
            dur_band = "< 60 min" if dur < 60 else ("1-3 hrs" if dur <= 180 else "3+ hrs")
            provider_dur_bands = set()
            for e in experiences:
                m = e.duration_minutes
                provider_dur_bands.add("< 60 min" if m < 60 else ("1-3 hrs" if m <= 180 else "3+ hrs"))
            
            if dur_band in provider_dur_bands:
                duration_fit = 1.0
                evidence_codes.add("DURATION_ALIGNMENT")

        if interactions:
            most_recent_ts = interactions[0].occurred_at or interactions[0].created_at
            days_ago = (now - most_recent_ts).total_seconds() / 86400.0
            if days_ago < 0: days_ago = 0
            recency_fit = math.exp(-math.log(2) / 14 * days_ago)

        total_score = (
            behavioral_score * self.settings.provider_match_weight_behavioral +
            cat_score * self.settings.provider_match_weight_category +
            pref_fit * self.settings.provider_match_weight_preference +
            budget_fit * self.settings.provider_match_weight_budget +
            duration_fit * self.settings.provider_match_weight_duration +
            recency_fit * self.settings.provider_match_weight_recency
        )

        qualified = total_score >= self.settings.provider_match_notification_threshold and has_qualifying_trigger

        return total_score, qualified, list(evidence_codes)
