"""Preserve collection-time evidence for future point-in-time research."""
from alembic import op
revision='20260917_archive'
down_revision='20260917_autocollect'
branch_labels=None
depends_on=None

def upgrade():
    op.execute('''CREATE TABLE wb_evidence_history (id BIGSERIAL PRIMARY KEY,api TEXT NOT NULL,
      trade_date VARCHAR(10) NOT NULL,status TEXT NOT NULL,payload JSONB,row_count INTEGER NOT NULL,
      fetched_at TIMESTAMPTZ NOT NULL DEFAULT now())''')
    op.execute('CREATE INDEX ON wb_evidence_history(trade_date,api,fetched_at)')

def downgrade():
    op.drop_table('wb_evidence_history')
