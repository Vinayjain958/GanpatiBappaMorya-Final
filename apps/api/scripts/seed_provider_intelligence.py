import argparse
import asyncio
from datetime import datetime, timedelta, UTC
import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import AsyncSessionLocal
from src.models.experience import Experience
from src.models.provider import Provider
from src.models.provider_synthetic_demand import ProviderSyntheticDemandSnapshot


async def seed_synthetic_data(provider_id: str, reset: bool = False):
    async with AsyncSessionLocal() as session:
        provider = await session.get(Provider, provider_id)
        if not provider:
            print(f"Provider {provider_id} not found.")
            return

        if reset:
            stmt = select(ProviderSyntheticDemandSnapshot).where(ProviderSyntheticDemandSnapshot.provider_id == provider_id)
            result = await session.execute(stmt)
            for row in result.scalars().all():
                await session.delete(row)
            await session.commit()
            print("Reset complete.")

        exp_stmt = select(Experience).where(Experience.provider_id == provider_id)
        experiences = list((await session.execute(exp_stmt)).scalars().all())

        now = datetime.now(UTC)
        
        for i in range(12):  # 12 weeks of data
            start = now - timedelta(days=(i+1)*7)
            end = now - timedelta(days=i*7)
            
            for exp in experiences:
                views = random.randint(100, 500)
                saves = int(views * random.uniform(0.1, 0.3))
                completions = int(views * random.uniform(0.4, 0.8))
                booking_requests = int(views * random.uniform(0.05, 0.15))
                accepted = int(booking_requests * random.uniform(0.7, 1.0))
                ratings_count = int(views * random.uniform(0.02, 0.1))
                avg_rating = random.uniform(3.5, 5.0) if ratings_count > 0 else None
                
                snapshot = ProviderSyntheticDemandSnapshot(
                    provider_id=provider_id,
                    experience_id=exp.id,
                    period_start=start,
                    period_end=end,
                    views=views,
                    saves=saves,
                    completions=completions,
                    booking_requests=booking_requests,
                    accepted_bookings=accepted,
                    ratings_count=ratings_count,
                    average_rating=avg_rating,
                    is_synthetic=True
                )
                session.add(snapshot)
                
        await session.commit()
        print(f"Seeded 12 weeks of synthetic data for provider {provider_id}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-id", required=True)
    parser.add_argument("--reset-synthetic", action="store_true")
    args = parser.parse_args()
    
    asyncio.run(seed_synthetic_data(args.provider_id, args.reset_synthetic))
