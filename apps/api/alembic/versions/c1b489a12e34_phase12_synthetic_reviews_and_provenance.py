"""phase12_synthetic_reviews_and_provenance

Revision ID: c1b489a12e34
Revises: 0572944927a4
Create Date: 2026-09-26 15:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1b489a12e34'
down_revision: Union[str, Sequence[str], None] = '0572944927a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'experience_reviews',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('experience_id', sa.String(length=36), nullable=False),
        sa.Column('rating_value', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('author_display_name', sa.String(length=80), nullable=False),
        sa.Column('language', sa.String(length=10), server_default='en', nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source_type', sa.String(length=40), server_default='synthetic_enrichment', nullable=False),
        sa.Column('source_name', sa.String(length=80), server_default='LocaLens synthetic review generator', nullable=False),
        sa.Column('is_synthetic', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('is_enriched', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('generation_version', sa.String(length=20), server_default='v1', nullable=False),
        sa.Column('synthetic_sequence', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['experience_id'], ['experiences.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('experience_id', 'generation_version', 'synthetic_sequence', name='uq_experience_review_synthetic_seq'),
    )
    op.create_index('ix_experience_reviews_experience_id', 'experience_reviews', ['experience_id'], unique=False)
    op.create_index('ix_experience_reviews_exp_reviewed', 'experience_reviews', ['experience_id', 'reviewed_at'], unique=False)

    with op.batch_alter_table('experience_opening_hours', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_type', sa.String(length=40), server_default='synthetic', nullable=False))
        batch_op.add_column(sa.Column('is_synthetic', sa.Boolean(), server_default=sa.true(), nullable=False))

    with op.batch_alter_table('experience_availability', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_type', sa.String(length=40), server_default='synthetic', nullable=False))
        batch_op.add_column(sa.Column('is_synthetic', sa.Boolean(), server_default=sa.true(), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('experience_availability', schema=None) as batch_op:
        batch_op.drop_column('is_synthetic')
        batch_op.drop_column('source_type')

    with op.batch_alter_table('experience_opening_hours', schema=None) as batch_op:
        batch_op.drop_column('is_synthetic')
        batch_op.drop_column('source_type')

    op.drop_index('ix_experience_reviews_exp_reviewed', table_name='experience_reviews')
    op.drop_index('ix_experience_reviews_experience_id', table_name='experience_reviews')
    op.drop_table('experience_reviews')
