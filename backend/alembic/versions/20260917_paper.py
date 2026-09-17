from alembic import op
revision='20260917_paper'
down_revision='20260917_archive'
branch_labels=None
depends_on=None
def upgrade():
 op.execute('CREATE TABLE wb_paper_batches (trade_date TEXT NOT NULL,phase TEXT NOT NULL,payload JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),PRIMARY KEY(trade_date,phase))')
 op.execute('CREATE TABLE wb_paper_signals (id BIGSERIAL PRIMARY KEY,trade_date TEXT NOT NULL,strategy TEXT NOT NULL,code TEXT NOT NULL,name TEXT NOT NULL,evidence JSONB NOT NULL,result JSONB,evaluated_at TIMESTAMPTZ,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),UNIQUE(trade_date,strategy,code))')
def downgrade():
 op.drop_table('wb_paper_signals');op.drop_table('wb_paper_batches')
