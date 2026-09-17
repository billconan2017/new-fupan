"""Preserve upstream quote timestamps separately from collection timestamps."""
from alembic import op
revision = '20260917_evidence'
down_revision = '20260917_pipeline'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE market_snapshot ADD COLUMN IF NOT EXISTS source_at TIMESTAMP WITHOUT TIME ZONE')


def downgrade():
    pass  # Preserve evidence on rollback.
