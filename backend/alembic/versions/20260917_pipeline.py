"""Add missing pipeline tables and nullable columns; preserves existing data."""
from alembic import op
revision = '20260917_pipeline'
down_revision = '6f773238efbd'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE TABLE IF NOT EXISTS stock_daily_kline (\n\tid BIGSERIAL NOT NULL, \n\tcode VARCHAR(10), \n\ttrade_date VARCHAR(10), \n\topen FLOAT, \n\thigh FLOAT, \n\tlow FLOAT, \n\tclose FLOAT, \n\tvolume FLOAT, \n\tamount FLOAT, \n\tpct_chg FLOAT, \n\tsource VARCHAR(20), \n\tupdated_at TIMESTAMP WITHOUT TIME ZONE, \n\tPRIMARY KEY (id), \n\tUNIQUE (code, trade_date)\n)')
    op.execute('CREATE TABLE IF NOT EXISTS stock_minute_kline (\n\tid BIGSERIAL NOT NULL, \n\tcode VARCHAR(10), \n\ttrade_date VARCHAR(10), \n\ttime VARCHAR(32), \n\tperiod INTEGER, \n\topen FLOAT, \n\thigh FLOAT, \n\tlow FLOAT, \n\tclose FLOAT, \n\tvolume FLOAT, \n\tamount FLOAT, \n\tavg FLOAT, \n\tsource VARCHAR(20), \n\tupdated_at TIMESTAMP WITHOUT TIME ZONE, \n\tPRIMARY KEY (id), \n\tUNIQUE (code, trade_date, time, period)\n)')
    op.execute('CREATE TABLE IF NOT EXISTS sector_flow (\n\tid BIGSERIAL NOT NULL, \n\ttrade_date VARCHAR(10), \n\tsector_code VARCHAR(80), \n\tsector_name VARCHAR(120), \n\tmain_net BIGINT, \n\tretail_net BIGINT, \n\ttotal_net BIGINT, \n\tchange_pct FLOAT, \n\tleader_pct FLOAT, \n\trise_count INTEGER, \n\tfall_count INTEGER, \n\tleader_code VARCHAR(10), \n\tleader_name VARCHAR(60), \n\tPRIMARY KEY (id), \n\tUNIQUE (trade_date, sector_code)\n)')
    op.execute('CREATE TABLE IF NOT EXISTS auction_sector (\n\tid BIGSERIAL NOT NULL, \n\ttrade_date VARCHAR(10), \n\tsector_code VARCHAR(80), \n\tsector_name VARCHAR(120), \n\tpct_chg FLOAT, \n\tamount BIGINT, \n\trise_count INTEGER, \n\tfall_count INTEGER, \n\tPRIMARY KEY (id), \n\tUNIQUE (trade_date, sector_code)\n)')
    op.execute('CREATE TABLE IF NOT EXISTS auction_tail (\n\tid BIGSERIAL NOT NULL, \n\ttrade_date VARCHAR(10), \n\tcode VARCHAR(10), \n\tname VARCHAR(60), \n\ttail_type VARCHAR(20), \n\tvalue FLOAT, \n\trank INTEGER, \n\tPRIMARY KEY (id)\n)')
    op.execute('CREATE TABLE IF NOT EXISTS auction_yizi (\n\tid BIGSERIAL NOT NULL, \n\ttrade_date VARCHAR(10), \n\tcode VARCHAR(10), \n\tname VARCHAR(60), \n\tpct_chg FLOAT, \n\tamount BIGINT, \n\tPRIMARY KEY (id), \n\tUNIQUE (trade_date, code)\n)')
    op.execute('CREATE TABLE IF NOT EXISTS dragon_tiger_seats (\n\tid BIGSERIAL NOT NULL, \n\ttrade_date VARCHAR(10), \n\tcode VARCHAR(10), \n\tseat_name VARCHAR(200), \n\tseat_type VARCHAR(20), \n\tamount BIGINT, \n\trank INTEGER, \n\tPRIMARY KEY (id)\n)')
    op.execute('CREATE TABLE IF NOT EXISTS youzi_info (\n\tid BIGSERIAL NOT NULL, \n\tyouzi_id VARCHAR(100), \n\tyouzi_name VARCHAR(100), \n\tyouzi_type VARCHAR(50), \n\tupdated_at TIMESTAMP WITHOUT TIME ZONE, \n\tPRIMARY KEY (id), \n\tUNIQUE (youzi_id)\n)')
    op.execute('CREATE TABLE IF NOT EXISTS youzi_trades (\n\tid BIGSERIAL NOT NULL, \n\ttrade_date VARCHAR(10), \n\tyouzi_id VARCHAR(100), \n\tyouzi_name VARCHAR(100), \n\tcode VARCHAR(10), \n\tname VARCHAR(60), \n\tdirection VARCHAR(20), \n\tamount BIGINT, \n\tPRIMARY KEY (id)\n)')
    op.execute('CREATE TABLE IF NOT EXISTS review_reports (\n\tid BIGSERIAL NOT NULL, \n\ttrade_date VARCHAR(10) NOT NULL, \n\tmarket_overview TEXT, \n\temotion_summary TEXT, \n\tlimit_up_analysis TEXT, \n\tlimit_down_analysis TEXT, \n\tbroken_board_analysis TEXT, \n\tdragon_tiger_summary TEXT, \n\tcapital_summary TEXT, \n\tstrong_stocks TEXT, \n\trisk_alarms TEXT, \n\toverall_score FLOAT, \n\toverall_comment TEXT, \n\traw_data TEXT, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(), \n\tPRIMARY KEY (id)\n)')
    op.execute('ALTER TABLE limit_up_pool ADD COLUMN IF NOT EXISTS limit_type VARCHAR(40)')
    op.execute('ALTER TABLE limit_up_pool ADD COLUMN IF NOT EXISTS limit_reason TEXT')
    op.execute('ALTER TABLE limit_up_pool ADD COLUMN IF NOT EXISTS flow_net BIGINT')
    op.execute('ALTER TABLE broken_board_pool ADD COLUMN IF NOT EXISTS break_time VARCHAR(32)')
    op.execute('ALTER TABLE strong_pool ADD COLUMN IF NOT EXISTS continuous_days INTEGER')
    op.execute('ALTER TABLE emotion_cycle ADD COLUMN IF NOT EXISTS rise_count INTEGER')
    op.execute('ALTER TABLE emotion_cycle ADD COLUMN IF NOT EXISTS fall_count INTEGER')
    op.execute('ALTER TABLE emotion_cycle ADD COLUMN IF NOT EXISTS height_board INTEGER')
    op.execute('ALTER TABLE emotion_cycle ADD COLUMN IF NOT EXISTS continue_count INTEGER')
    op.execute('ALTER TABLE emotion_cycle ADD COLUMN IF NOT EXISTS broken_count INTEGER')
    op.execute('ALTER TABLE emotion_cycle ADD COLUMN IF NOT EXISTS avg_change_pct FLOAT')
    op.execute('ALTER TABLE emotion_cycle ADD COLUMN IF NOT EXISTS turnover_avg FLOAT')


def downgrade():
    # Tables may predate this migration on existing deployments. Preserve data.
    pass
