"""catalog lookup indexes

Additive indexes for the columns Discover, provider dashboards, and radius
searches filter on. No data changes.

Revision ID: f3b1c2d4e5a6
Revises: 9d3a7c4e1b20
Create Date: 2026-09-27

"""

from typing import Sequence, Union

from alembic import op


revision: str = "f3b1c2d4e5a6"
down_revision: Union[str, Sequence[str], None] = "9d3a7c4e1b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_experiences_provider_id", "experiences", ["provider_id"])
    op.create_index("ix_experiences_category_id", "experiences", ["category_id"])
    op.create_index("ix_experiences_status", "experiences", ["status"])
    op.create_index("ix_locations_latitude_longitude", "locations", ["latitude", "longitude"])


def downgrade() -> None:
    op.drop_index("ix_locations_latitude_longitude", table_name="locations")
    op.drop_index("ix_experiences_status", table_name="experiences")
    op.drop_index("ix_experiences_category_id", table_name="experiences")
    op.drop_index("ix_experiences_provider_id", table_name="experiences")
