"""Independent evidence and frozen observation plans for the new workbench."""
from alembic import op
revision='20260917_workbench'
down_revision='20260917_evidence'
branch_labels=None
depends_on=None

def upgrade():
    op.execute('''CREATE TABLE wb_evidence (api TEXT NOT NULL, trade_date VARCHAR(10) NOT NULL,
        status TEXT NOT NULL, payload JSONB, row_count INTEGER NOT NULL DEFAULT 0,
        message TEXT, fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(api,trade_date))''')
    op.execute('''CREATE TABLE wb_plans (id BIGSERIAL PRIMARY KEY, trade_date VARCHAR(10) NOT NULL,
        code VARCHAR(6) NOT NULL, name TEXT, mode TEXT NOT NULL, phase TEXT NOT NULL,
        note TEXT, evidence JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(trade_date,code,mode,phase))''')
    op.execute('''CREATE TABLE wb_jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL, stage TEXT NOT NULL,
        trade_date VARCHAR(10) NOT NULL, progress INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL,
        results JSONB NOT NULL DEFAULT '[]', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), finished_at TIMESTAMPTZ)''')

def downgrade():
    pass
