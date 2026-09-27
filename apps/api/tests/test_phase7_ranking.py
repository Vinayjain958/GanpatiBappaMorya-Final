from src.core.config import Settings
from src.schemas.conversation import TravelerContext
from src.schemas.experience import CategorySummary, ExperienceSummary, LocationSummary, ProviderSummary
from src.schemas.feasibility import FeasibilityVerdict
from src.services.discovery_pipeline import PipelineItem
from src.services.ranking import TravelerRankingProfile, WeightedPersonalizedRanker


def test_weighted_personalized_ranker():
    ranker = WeightedPersonalizedRanker()
    settings = Settings()
    
    cat = CategorySummary(id="cat-1", slug="food-drink", name="Food", icon="food")
    loc = LocationSummary(id="loc-1", city="Mumbai", latitude=19.0, longitude=72.8, place_name="Test", address="Test")
    prov = ProviderSummary(id="prov-1", business_name="Prov", verification_status="verified", is_synthetic=False)
    
    exp = ExperienceSummary(
        id="exp-1",
        title="Test",
        short_description="Test",
        category=cat,
        location=loc,
        provider=prov,
        currency="INR",
        price_type="per_person",
        is_price_estimated=False,
        duration_is_estimated=False,
        status="active",
        verification_status="verified",
        is_synthetic=False,
        is_enriched=False,
        price=1000
    )
    
    from datetime import datetime

    item = PipelineItem(
        experience_id="exp-1",
        similarity=0.9,
        verdict=FeasibilityVerdict(
            experience_id="exp-1",
            status="FEASIBLE",
            checked_at=datetime.utcnow()
        ),
        experience=exp
    )
    
    profile = TravelerRankingProfile(
        traveler_id="t-1",
        preference=None,
        affinities={},
        recently_seen_experience_ids=set()
    )
    
    context = TravelerContext(raw_query="")
    
    ranked_items = ranker.rank([item], profile, context, settings)
    
    assert len(ranked_items) == 1
    ranked_item = ranked_items[0]
    
    assert ranked_item.ranking_score > 0
    assert ranked_item.personalized is False
    assert len(ranked_item.match_signals) > 0
