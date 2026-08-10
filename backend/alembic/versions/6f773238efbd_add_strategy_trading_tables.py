"""add_strategy_trading_tables

Revision ID: 6f773238efbd
Revises: b66a9843ecc3
Create Date: 2026-07-08 00:06:01.250110

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '6f773238efbd'
down_revision: Union[str, Sequence[str], None] = 'b66a9843ecc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── stock_basic: 全市场个股基础信息 ──
    op.create_table('stock_basic',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(10), nullable=False),
        sa.Column('name', sa.String(50)),
        sa.Column('market', sa.String(10)),
        sa.Column('industry', sa.String(50)),
        sa.Column('concept', sa.String(200)),
        sa.Column('total_cap', sa.BigInteger()),
        sa.Column('circulating_cap', sa.BigInteger()),
        sa.Column('list_date', sa.String(10)),
        sa.Column('delist_date', sa.String(10)),
        sa.Column('is_st', sa.Boolean(), default=False),
        sa.Column('status', sa.String(10), default='active'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_sb_code', 'stock_basic', ['code'], unique=True)
    op.create_index('ix_stock_basic_code', 'stock_basic', ['code'], unique=True)

    # ── sector_tree: 同花顺行业板块树 ──
    op.create_table('sector_tree',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('sector_code', sa.String(20), nullable=False),
        sa.Column('sector_name', sa.String(50)),
        sa.Column('parent_code', sa.String(20)),
        sa.Column('level', sa.Integer(), default=1),
        sa.Column('stock_count', sa.Integer()),
        sa.Column('source', sa.String(20)),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sector_tree_sector_code', 'sector_tree', ['sector_code'], unique=True)
    op.create_index('idx_st_parent', 'sector_tree', ['parent_code'])

    # ── strategy_record: 选股策略历史回测 ──
    op.create_table('strategy_record',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('strategy_name', sa.String(50), nullable=False),
        sa.Column('trade_date', sa.String(10), nullable=False),
        sa.Column('filters_json', sa.Text()),
        sa.Column('result_json', sa.Text()),
        sa.Column('result_count', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_strategy_record_trade_date', 'strategy_record', ['trade_date'])
    op.create_index('idx_sr_date', 'strategy_record', ['trade_date'])
    op.create_index('idx_sr_name_date', 'strategy_record', ['strategy_name', 'trade_date'])

    # ── account_info: 实盘多账户配置 ──
    op.create_table('account_info',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('account_name', sa.String(50), nullable=False),
        sa.Column('broker', sa.String(50)),
        sa.Column('account_type', sa.String(20), default='stock'),
        sa.Column('api_key', sa.String(200)),
        sa.Column('api_secret', sa.String(200)),
        sa.Column('initial_capital', sa.BigInteger()),
        sa.Column('status', sa.String(10), default='active'),
        sa.Column('remark', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_name'),
    )

    # ── position_record: 持仓同步记录 ──
    op.create_table('position_record',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('trade_date', sa.String(10), nullable=False),
        sa.Column('code', sa.String(10), nullable=False),
        sa.Column('name', sa.String(50)),
        sa.Column('quantity', sa.Integer()),
        sa.Column('available_qty', sa.Integer()),
        sa.Column('cost_price', sa.Float()),
        sa.Column('current_price', sa.Float()),
        sa.Column('market_value', sa.BigInteger()),
        sa.Column('profit', sa.BigInteger()),
        sa.Column('profit_pct', sa.Float()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_position_record_account_id', 'position_record', ['account_id'])
    op.create_index('ix_position_record_trade_date', 'position_record', ['trade_date'])
    op.create_index('idx_pr_date_code', 'position_record', ['trade_date', 'code'])
    op.create_index('idx_pr_account_date', 'position_record', ['account_id', 'trade_date'])

    # ── order_record: 委托单/成交单流水 ──
    op.create_table('order_record',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('trade_date', sa.String(10), nullable=False),
        sa.Column('order_time', sa.DateTime()),
        sa.Column('code', sa.String(10), nullable=False),
        sa.Column('name', sa.String(50)),
        sa.Column('direction', sa.String(10)),
        sa.Column('order_type', sa.String(20)),
        sa.Column('price', sa.Float()),
        sa.Column('quantity', sa.Integer()),
        sa.Column('filled_qty', sa.Integer(), default=0),
        sa.Column('filled_price', sa.Float()),
        sa.Column('filled_amount', sa.BigInteger()),
        sa.Column('status', sa.String(20)),
        sa.Column('order_id', sa.String(50)),
        sa.Column('trigger_price', sa.Float()),
        sa.Column('trigger_type', sa.String(20)),
        sa.Column('remark', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_order_record_account_id', 'order_record', ['account_id'])
    op.create_index('ix_order_record_trade_date', 'order_record', ['trade_date'])
    op.create_index('idx_or_date', 'order_record', ['trade_date'])
    op.create_index('idx_or_account_date', 'order_record', ['account_id', 'trade_date'])

    # ── risk_blacklist: 个股风控黑名单 ──
    op.create_table('risk_blacklist',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(10), nullable=False),
        sa.Column('name', sa.String(50)),
        sa.Column('reason', sa.Text()),
        sa.Column('added_date', sa.String(10)),
        sa.Column('removed_date', sa.String(10)),
        sa.Column('status', sa.String(10), default='active'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_risk_blacklist_code', 'risk_blacklist', ['code'], unique=True)


def downgrade() -> None:
    op.drop_table('risk_blacklist')
    op.drop_table('order_record')
    op.drop_table('position_record')
    op.drop_table('account_info')
    op.drop_table('strategy_record')
    op.drop_table('sector_tree')
    op.drop_table('stock_basic')
