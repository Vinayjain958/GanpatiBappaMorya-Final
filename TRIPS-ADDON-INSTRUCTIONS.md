Trips add-on overlay

Extract this archive into the repository root, preserving the included paths. It contains the changed source files and the additive custom-activity migration.

Then run the API migration from apps/api with the project's configured database: alembic upgrade head

To populate illustrative opening-hour schedules and availability windows for places missing those records, run from apps/api:
python scripts/seed_demo_opening_hours.py

These schedules and availability windows are labeled as demo data in Trips and are not venue-confirmed. The script preserves existing opening hours and availability and can be rerun safely. Starting-point suggestions match the real catalog as you type; use the address-search action for locations outside the catalog. The current-location control requests browser permission only after it is clicked.

The archive intentionally excludes .env files, local databases, node_modules, virtual environments, and generated build output. It does not seed 200-300 saved itineraries; date-checked suggestions are generated dynamically from catalog data, up to 200 per request.
