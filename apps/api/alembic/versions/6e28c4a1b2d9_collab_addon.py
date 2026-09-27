"""add isolated collaborative planning entities

Revision ID: 6e28c4a1b2d9
Revises: c1b489a12e34
Create Date: 2026-09-26

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6e28c4a1b2d9"
down_revision: Union[str, Sequence[str], None] = "c1b489a12e34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "collab_groups",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("owner_user_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("destination", sa.String(120), nullable=True),
        sa.Column("itinerary_date", sa.Date(), nullable=True),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("origin_latitude", sa.Float(), nullable=True),
        sa.Column("origin_longitude", sa.Float(), nullable=True),
        sa.Column("travel_mode", sa.String(20), nullable=False, server_default="walking"),
        sa.Column("invite_code", sa.String(48), nullable=False),
        sa.Column("objectives", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invite_code", name="uq_collab_groups_invite_code"),
    )
    op.create_index("ix_collab_groups_owner_user_id", "collab_groups", ["owner_user_id"])

    op.create_table(
        "collab_members",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("group_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["group_id"], ["collab_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "user_id", name="uq_collab_member_group_user"),
    )
    op.create_index("ix_collab_members_group_id", "collab_members", ["group_id"])
    op.create_index("ix_collab_members_user_id", "collab_members", ["user_id"])

    op.create_table(
        "collab_member_preferences",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("member_id", sa.String(36), nullable=False),
        sa.Column("soft_preferences", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("hard_constraints", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *_timestamps(),
        sa.ForeignKeyConstraint(["member_id"], ["collab_members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_id", name="uq_collab_member_preferences_member"),
    )
    op.create_index("ix_collab_member_preferences_member_id", "collab_member_preferences", ["member_id"])

    op.create_table(
        "collab_wishlist_items",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("group_id", sa.String(36), nullable=False),
        sa.Column("experience_id", sa.String(36), nullable=False),
        sa.Column("added_by_member_id", sa.String(36), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["group_id"], ["collab_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["experience_id"], ["experiences.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by_member_id"], ["collab_members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "experience_id", name="uq_collab_wishlist_group_experience"),
    )
    op.create_index("ix_collab_wishlist_items_group_id", "collab_wishlist_items", ["group_id"])
    op.create_index("ix_collab_wishlist_items_experience_id", "collab_wishlist_items", ["experience_id"])

    op.create_table(
        "collab_wishlist_reactions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("wishlist_item_id", sa.String(36), nullable=False),
        sa.Column("member_id", sa.String(36), nullable=False),
        sa.Column("reaction", sa.String(16), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["wishlist_item_id"], ["collab_wishlist_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["collab_members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wishlist_item_id", "member_id", name="uq_collab_reaction_item_member"),
    )
    op.create_index("ix_collab_wishlist_reactions_wishlist_item_id", "collab_wishlist_reactions", ["wishlist_item_id"])
    op.create_index("ix_collab_wishlist_reactions_member_id", "collab_wishlist_reactions", ["member_id"])

    op.create_table(
        "collab_decisions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("group_id", sa.String(36), nullable=False),
        sa.Column("created_by_member_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["group_id"], ["collab_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_member_id"], ["collab_members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collab_decisions_group_id", "collab_decisions", ["group_id"])

    op.create_table(
        "collab_decision_options",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("decision_id", sa.String(36), nullable=False),
        sa.Column("experience_id", sa.String(36), nullable=True),
        sa.Column("label", sa.String(200), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["decision_id"], ["collab_decisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["experience_id"], ["experiences.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collab_decision_options_decision_id", "collab_decision_options", ["decision_id"])
    op.create_index("ix_collab_decision_options_experience_id", "collab_decision_options", ["experience_id"])

    op.create_table(
        "collab_votes",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("decision_id", sa.String(36), nullable=False),
        sa.Column("option_id", sa.String(36), nullable=False),
        sa.Column("member_id", sa.String(36), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["decision_id"], ["collab_decisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["option_id"], ["collab_decision_options.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["collab_members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("decision_id", "member_id", name="uq_collab_vote_decision_member"),
    )
    op.create_index("ix_collab_votes_decision_id", "collab_votes", ["decision_id"])
    op.create_index("ix_collab_votes_member_id", "collab_votes", ["member_id"])

    op.create_table(
        "collab_itineraries",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("group_id", sa.String(36), nullable=False),
        sa.Column("created_by_member_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["group_id"], ["collab_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_member_id"], ["collab_members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", name="uq_collab_itinerary_group"),
    )
    op.create_index("ix_collab_itineraries_group_id", "collab_itineraries", ["group_id"])

    op.create_table(
        "collab_itinerary_items",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("itinerary_id", sa.String(36), nullable=False),
        sa.Column("experience_id", sa.String(36), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["itinerary_id"], ["collab_itineraries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["experience_id"], ["experiences.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("itinerary_id", "sequence_order", name="uq_collab_itinerary_item_order"),
    )
    op.create_index("ix_collab_itinerary_items_itinerary_id", "collab_itinerary_items", ["itinerary_id"])
    op.create_index("ix_collab_itinerary_items_experience_id", "collab_itinerary_items", ["experience_id"])

    op.create_table(
        "collab_itinerary_approvals",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("itinerary_id", sa.String(36), nullable=False),
        sa.Column("member_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="PENDING"),
        sa.Column("note", sa.String(500), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["itinerary_id"], ["collab_itineraries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["collab_members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("itinerary_id", "member_id", name="uq_collab_itinerary_approval_member"),
    )
    op.create_index("ix_collab_itinerary_approvals_itinerary_id", "collab_itinerary_approvals", ["itinerary_id"])
    op.create_index("ix_collab_itinerary_approvals_member_id", "collab_itinerary_approvals", ["member_id"])

    op.create_table(
        "collab_itinerary_trips",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("collab_itinerary_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("itinerary_id", sa.String(36), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["collab_itinerary_id"], ["collab_itineraries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["itinerary_id"], ["itineraries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collab_itinerary_id", "user_id", name="uq_collab_itinerary_trip_user"),
    )
    op.create_index("ix_collab_itinerary_trips_collab_itinerary_id", "collab_itinerary_trips", ["collab_itinerary_id"])
    op.create_index("ix_collab_itinerary_trips_user_id", "collab_itinerary_trips", ["user_id"])
    op.create_index("ix_collab_itinerary_trips_itinerary_id", "collab_itinerary_trips", ["itinerary_id"])


def downgrade() -> None:
    op.drop_table("collab_itinerary_trips")
    op.drop_table("collab_itinerary_approvals")
    op.drop_table("collab_itinerary_items")
    op.drop_table("collab_itineraries")
    op.drop_table("collab_votes")
    op.drop_table("collab_decision_options")
    op.drop_table("collab_decisions")
    op.drop_table("collab_wishlist_reactions")
    op.drop_table("collab_wishlist_items")
    op.drop_table("collab_member_preferences")
    op.drop_table("collab_members")
    op.drop_table("collab_groups")
