"""Durable standalone timer execution ledger."""
from alembic import op
revision='20260917_autocollect'
down_revision='20260917_workbench'
branch_labels=None
depends_on=None

def upgrade():
    op.execute('''CREATE TABLE wb_schedule_runs (slot TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES wb_jobs(id),
      stage TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 1,created_at TIMESTAMPTZ NOT NULL DEFAULT now())''')

def downgrade():
    op.drop_table('wb_schedule_runs')
