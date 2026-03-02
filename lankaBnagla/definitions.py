"""
definitions.py — Dagster code location entry point for LankaBD Scraper
=====================================================================
All jobs and schedules are registered here via Definitions.

Launch the Dagster UI:
    dagster dev -f definitions.py

Or simply from the project root (auto-discovers definitions.py):
    dagster dev
"""

from dagster import Definitions, ScheduleDefinition, load_assets_from_modules, define_asset_job, AssetSelection

# ── Import modules for asset and job discovery ────────────────────────────────
import dataGrid
import announcement
import priceArchive

# ── Asset Discovery ───────────────────────────────────────────────────────────
datagrid_assets = load_assets_from_modules([dataGrid], group_name="datagrid")

# ── Job Definitions ───────────────────────────────────────────────────────────

# Asset-backed job: materializes the datagrid assets
datagrid_asset_job = define_asset_job(name="datagrid_asset_job", selection=AssetSelection.groups("datagrid"))

# Op-backed jobs from other modules (kept as legacy)
announcement_job = announcement.announcement_job
announcement_by_sector_job = announcement.announcement_by_sector_job
price_archive_job = priceArchive.price_archive_job
price_archive_by_sector_job = priceArchive.price_archive_by_sector_job

# ── Schedules (Asia/Dhaka timezone) ───────────────────────────────────────────

datagrid_daily_schedule = ScheduleDefinition(
    name="datagrid_daily",
    job=datagrid_asset_job,
    cron_schedule="0 7 * * *",
    execution_timezone="Asia/Dhaka",
)

announcement_daily_schedule = ScheduleDefinition(
    name="announcement_daily",
    job=announcement_job,
    cron_schedule="0 8 * * *",
    execution_timezone="Asia/Dhaka",
)

price_archive_daily_schedule = ScheduleDefinition(
    name="price_archive_daily",
    job=price_archive_job,
    cron_schedule="0 9 * * *",
    execution_timezone="Asia/Dhaka",
)

# ── Definitions (Root Entry Point) ────────────────────────────────────────────

defs = Definitions(
    assets=[*datagrid_assets],
    jobs=[
        datagrid_asset_job,
        announcement_job,
        announcement_by_sector_job,
        price_archive_job,
        price_archive_by_sector_job,
    ],
    schedules=[
        datagrid_daily_schedule,
        announcement_daily_schedule,
        price_archive_daily_schedule,
    ],
)

