"""traveler experience contributions

Adds the "Add a Local Experience" flow's storage:
  - traveler_experience_contributions: audit/provenance record for each
    traveler direct-publish submission. NOT a second catalog — the
    published Experience row remains the canonical, searchable entity;
    this table makes a submission traceable to its contributor and its
    as-submitted values (moderation, takedown, ownership claims).
  - media_objects: the uploaded photos themselves, stored in the database
    because the API host's local disk is wiped on restart.
  - a singleton "LocaLens Community" Provider row (fixed id
    00000000-0000-0000-0000-000000000001) that every traveler-submitted
    Experience is attached to, since Experience.provider_id is NOT NULL and
    travelers are never auto-converted into Provider accounts.

Existing rows are untouched.

Revision ID: a7c4e9d2b1f3
Revises: f3b1c2d4e5a6
Create Date: 2026-09-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a7c4e9d2b1f3"
down_revision: Union[str, Sequence[str], None] = "f3b1c2d4e5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COMMUNITY_PROVIDER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "traveler_experience_contributions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("traveler_id", sa.String(length=36), nullable=False),
        sa.Column("published_experience_id", sa.String(length=36), nullable=True),
        sa.Column("submitted_name", sa.String(length=200), nullable=False),
        sa.Column("submitted_description", sa.Text(), nullable=True),
        sa.Column("submitted_contact_phone", sa.String(length=32), nullable=False),
        sa.Column("submitted_contact_phone_raw", sa.String(length=40), nullable=False),
        sa.Column("submitted_website", sa.String(length=500), nullable=True),
        sa.Column("submitted_category_id", sa.String(length=36), nullable=False),
        sa.Column("submitted_location_id", sa.String(length=36), nullable=True),
        sa.Column("submitted_image_object_key", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="published"),
        sa.Column("validation_status", sa.String(length=20), nullable=False),
        sa.Column("duplicate_check_status", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("duplicate_of_experience_id", sa.String(length=36), nullable=True),
        sa.Column("idempotency_key", sa.String(length=80), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["traveler_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["published_experience_id"], ["experiences.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submitted_category_id"], ["experience_categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["duplicate_of_experience_id"], ["experiences.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("traveler_id", "idempotency_key", name="uq_contribution_traveler_idempotency"),
    )
    op.create_index(
        "ix_traveler_experience_contributions_traveler_id",
        "traveler_experience_contributions", ["traveler_id"], unique=False,
    )
    op.create_index(
        "ix_traveler_experience_contributions_published_experience_id",
        "traveler_experience_contributions", ["published_experience_id"], unique=False,
    )

    op.create_table(
        "media_objects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_objects_object_key", "media_objects", ["object_key"], unique=True)

    # Idempotent: the service layer also creates this row on demand, so it
    # may already exist on a database that ran the app before migrating.
    op.execute(
        sa.text(
            """
            INSERT INTO providers (
                id, business_name, description, provider_type, verification_status,
                source_type, is_synthetic, is_enriched, attribution_required,
                created_at, updated_at
            )
            SELECT
                CAST(:id AS VARCHAR(36)), 'LocaLens Community',
                'Placeholder catalog owner for experiences published directly by '
                || 'travelers via the Add a Local Experience flow. Not a real business.',
                'community', 'unverified', 'system', FALSE, FALSE, FALSE,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            WHERE NOT EXISTS (SELECT 1 FROM providers WHERE id = :id)
            """
        ).bindparams(id=COMMUNITY_PROVIDER_ID)
    )


def downgrade() -> None:
    """Dev-time rollback only: deleting the community provider fails if any
    traveler-submitted Experience still references it."""
    op.drop_index("ix_media_objects_object_key", table_name="media_objects")
    op.drop_table("media_objects")
    op.drop_index(
        "ix_traveler_experience_contributions_published_experience_id",
        table_name="traveler_experience_contributions",
    )
    op.drop_index(
        "ix_traveler_experience_contributions_traveler_id",
        table_name="traveler_experience_contributions",
    )
    op.drop_table("traveler_experience_contributions")
    op.execute(sa.text("DELETE FROM providers WHERE id = :id").bindparams(id=COMMUNITY_PROVIDER_ID))
