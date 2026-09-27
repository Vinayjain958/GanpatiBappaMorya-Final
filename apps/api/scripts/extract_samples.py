import asyncio
from src.core.db import async_session_factory
from src.repositories.experience_repository import ExperienceRepository, ExperienceFilters
from src.repositories.review_repository import ReviewRepository

async def get_5_samples():
    async with async_session_factory() as session:
        repo = ExperienceRepository(session)
        review_repo = ReviewRepository(session)
        exps = await repo.search(ExperienceFilters(), cap=1000)
        
        nightlife = next(e for e in exps if e.category and e.category.slug == 'nightlife')
        museum = next(e for e in exps if e.category and e.category.slug == 'museums')
        seed = next(e for e in exps if e.source_type == 'synthetic')
        overture = next(e for e in exps if e.source_type == 'overture_places' and e.category and e.category.slug == 'cafes')
        catalog = next(e for e in exps if e.source_type == 'manual_catalog_2026')
        
        days_map = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for idx, exp in enumerate([nightlife, museum, seed, overture, catalog], 1):
            reviews, total = await review_repo.list_for_experience(exp.id, limit=100)
            pos_revs = [r for r in reviews if r.rating_value >= 4][:2]
            crit_revs = [r for r in reviews if r.rating_value <= 3][:1]
            if not crit_revs:
                crit_revs = [reviews[-1]]
            
            cat_slug = exp.category.slug if exp.category else 'unknown'
            print(f'=== SAMPLE {idx}: {exp.title} ===')
            print(f'Category: {cat_slug}')
            print(f'Source Type: {exp.source_type}')
            print(f'Rating: {exp.rating} | Review Count: {exp.review_count}')
            print('Schedule:')
            for h in sorted(exp.opening_hours, key=lambda x: x.day_of_week):
                d_str = days_map[h.day_of_week]
                status = 'Closed' if h.is_closed else f'{h.open_time} - {h.close_time}'
                print(f'  {d_str}: {status} (synthetic={h.is_synthetic})')
            print('Sample Availability Slots (next 3):')
            for s in exp.availability_slots[:3]:
                print(f'  {s.starts_at.isoformat()} to {s.ends_at.isoformat()} (capacity: {s.capacity}, available: {s.available_slots}, synthetic={s.is_synthetic})')
            print('Top 2 Positive Reviews:')
            for r in pos_revs:
                print(f'  [{r.rating_value} stars] "{r.title}" by {r.author_display_name}: {r.body[:90]}...')
            print('Critical/Constructive Review:')
            for r in crit_revs:
                print(f'  [{r.rating_value} stars] "{r.title}" by {r.author_display_name}: {r.body[:90]}...')
            print()

asyncio.run(get_5_samples())
