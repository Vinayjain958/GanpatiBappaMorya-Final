"""add traveler-authored itinerary activities

Revision ID: 9d3a7c4e1b20
Revises: 6e28c4a1b2d9
Create Date: 2026-09-26

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9d3a7c4e1b20"
down_revision: Union[str, Sequence[str], None] = "6e28c4a1b2d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("itineraries") as batch_op:
        batch_op.add_column(sa.Column("max_budget", sa.Float(), nullable=True))

    op.create_table(
        "itinerary_custom_activities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("itinerary_id", sa.String(length=36), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=20), server_default="activity", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("location_text", sa.String(length=300), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("planned_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("planned_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["itinerary_id"], ["itineraries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_itinerary_custom_activities_itinerary_id",
        "itinerary_custom_activities",
        ["itinerary_id"],
    )
    op.create_index(
        "ix_custom_activity_itinerary_start",
        "itinerary_custom_activities",
        ["itinerary_id", "planned_start"],
    )


def downgrade() -> None:
    op.drop_index("ix_custom_activity_itinerary_start", table_name="itinerary_custom_activities")
    op.drop_index("ix_itinerary_custom_activities_itinerary_id", table_name="itinerary_custom_activities")
    op.drop_table("itinerary_custom_activities")
    with op.batch_alter_table("itineraries") as batch_op:
        batch_op.drop_column("max_budget")
