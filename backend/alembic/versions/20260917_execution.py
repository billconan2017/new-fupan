"""Immutable prospective confirmation events, separate from EOD reconstructions."""
from alembic import op
revision='20260917_execution'
down_revision='20260917_paper'
branch_labels=None
depends_on=None
def upgrade():
 op.execute('''CREATE TABLE wb_paper_events (
 id BIGSERIAL PRIMARY KEY, signal_id BIGINT NOT NULL REFERENCES wb_paper_signals(id),
 kind TEXT NOT NULL, payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(signal_id,kind))''')
def downgrade():op.drop_table('wb_paper_events')
