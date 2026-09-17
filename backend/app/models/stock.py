from sqlalchemy import Column, Integer, String, Float, DateTime, Text, BigInteger, Index, Boolean
from sqlalchemy.sql import func
from app.database import Base


class Stock(Base):
    __tablename__ = "stocks"
    id = Column(Integer, primary_key=True)
    code = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(50))
    market = Column(String(10))  # sh/sz/bj
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class MarketSnapshot(Base):
    """全市场快照 - 每60s写入"""
    __tablename__ = "market_snapshot"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(String(10), nullable=False, index=True)
    snapshot_at = Column(DateTime, nullable=False, index=True)
    source_at = Column(DateTime)  # upstream timestamp; null for unverifiable legacy rows
    code = Column(String(10), nullable=False)
    name = Column(String(50))
    price = Column(Float)
    pct_chg = Column(Float)
    amount = Column(BigInteger)  # 成交额(元)
    volume = Column(BigInteger)  # 成交量(手)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    pre_close = Column(Float)
    turnover = Column(Float)  # 换手率
    volume_ratio = Column(Float)  # 量比
    amplitude = Column(Float)  # 振幅
    circulating_cap = Column(BigInteger)  # 流通市值
    total_cap = Column(BigInteger)  # 总市值

    __table_args__ = (
        Index("idx_snap_date_code", "trade_date", "code"),
        Index("idx_snap_time", "snapshot_at"),
    )


class DailyKline(Base):
    """日K线"""
    __tablename__ = "daily_kline"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False)
    trade_date = Column(String(10), nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(BigInteger)
    amount = Column(BigInteger)
    pct_chg = Column(Float)
    turnover = Column(Float)

    __table_args__ = (
        Index("idx_kline_code_date", "code", "trade_date", unique=True),
    )


class LimitUpPool(Base):
    """涨停池"""
    __tablename__ = "limit_up_pool"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(String(10), nullable=False, index=True)
    code = Column(String(10), nullable=False)
    name = Column(String(50))
    price = Column(Float)
    pct_chg = Column(Float)
    amount = Column(BigInteger)
    circulating_cap = Column(BigInteger)
    total_cap = Column(BigInteger)
    turnover = Column(Float)
    first_seal_time = Column(String(20))  # 首次封板时间
    last_seal_time = Column(String(20))  # 最后封板时间
    seal_amount = Column(BigInteger)  # 封板资金
    consecutive = Column(Integer)  # 连板数
    broken_count = Column(Integer)  # 炸板次数
    industry = Column(String(50))  # 所属行业

    __table_args__ = (
        Index("idx_lu_date_code", "trade_date", "code", unique=True),
    )


class LimitDownPool(Base):
    """跌停池"""
    __tablename__ = "limit_down_pool"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(String(10), nullable=False, index=True)
    code = Column(String(10), nullable=False)
    name = Column(String(50))
    price = Column(Float)
    pct_chg = Column(Float)
    amount = Column(BigInteger)
    circulating_cap = Column(BigInteger)
    turnover = Column(Float)
    pe = Column(Float)
    consecutive = Column(Integer)  # 连续跌停次数
    seal_amount = Column(BigInteger)
    board_amount = Column(BigInteger)  # 板上成交额
    broken_count = Column(Integer)

    __table_args__ = (
        Index("idx_ld_date_code", "trade_date", "code", unique=True),
    )


class StrongPool(Base):
    """强势股池"""
    __tablename__ = "strong_pool"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(String(10), nullable=False, index=True)
    code = Column(String(10), nullable=False)
    name = Column(String(50))
    price = Column(Float)
    pct_chg = Column(Float)
    amount = Column(BigInteger)
    turnover = Column(Float)
    volume_ratio = Column(Float)
    amplitude = Column(Float)
    industry = Column(String(50))

    __table_args__ = (
        Index("idx_sp_date_code", "trade_date", "code", unique=True),
    )


class BrokenBoardPool(Base):
    """炸板池"""
    __tablename__ = "broken_board_pool"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(String(10), nullable=False, index=True)
    code = Column(String(10), nullable=False)
    name = Column(String(50))
    price = Column(Float)
    pct_chg = Column(Float)
    amount = Column(BigInteger)
    turnover = Column(Float)
    broken_count = Column(Integer)
    industry = Column(String(50))

    __table_args__ = (
        Index("idx_bb_date_code", "trade_date", "code", unique=True),
    )


class DragonTiger(Base):
    """龙虎榜"""
    __tablename__ = "dragon_tiger"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(String(10), nullable=False, index=True)
    code = Column(String(10), nullable=False)
    name = Column(String(50))
    close = Column(Float)
    pct_chg = Column(Float)
    reason = Column(Text)
    buy_amount = Column(BigInteger)
    sell_amount = Column(BigInteger)
    net_amount = Column(BigInteger)

    __table_args__ = (
        Index("idx_dt_date_code", "trade_date", "code"),
    )


class EmotionCycle(Base):
    """情绪周期"""
    __tablename__ = "emotion_cycle"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(String(10), nullable=False, unique=True)
    limit_up_count = Column(Integer)
    limit_down_count = Column(Integer)
    broken_board_count = Column(Integer)
    seal_rate = Column(Float)  # 封板率
    emotion_score = Column(Float)  # 情绪分
    cycle_phase = Column(String(20))  # 冰点/修复/升温/高潮/退潮
    raw_data = Column(Text)  # 原始JSON
    created_at = Column(DateTime, server_default=func.now())


class AuctionStock(Base):
    """竞价数据 - 个股"""
    __tablename__ = "auction_stock"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(String(10), nullable=False, index=True)
    code = Column(String(10), nullable=False)
    name = Column(String(50))
    open_price = Column(Float)
    pre_close = Column(Float)
    pct_chg = Column(Float)
    amount = Column(BigInteger)  # 竞价成交额
    volume = Column(BigInteger)
    bid_ask_ratio = Column(Float)  # 委比

    __table_args__ = (
        Index("idx_auction_date_code", "trade_date", "code", unique=True),
    )


class CapitalFlow(Base):
    """资金流向"""
    __tablename__ = "capital_flow"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(String(10), nullable=False, index=True)
    code = Column(String(10), nullable=False)
    name = Column(String(50))
    main_net = Column(BigInteger)  # 主力净流入
    super_large_net = Column(BigInteger)  # 超大单净流入
    large_net = Column(BigInteger)  # 大单净流入
    medium_net = Column(BigInteger)  # 中单净流入
    small_net = Column(BigInteger)  # 小单净流入
    main_pct = Column(Float)  # 主力净流入占比

    __table_args__ = (
        Index("idx_cf_date_code", "trade_date", "code", unique=True),
    )


class RiskAlarm(Base):
    """风险预警"""
    __tablename__ = "risk_alarms"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(String(10), nullable=False, index=True)
    code = Column(String(10))
    name = Column(String(50))
    alarm_type = Column(String(50))  # unlock/risk/serious
    description = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class ReviewReport(Base):
    """盘后复盘报告"""
    __tablename__ = "review_reports"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(String(10), nullable=False, unique=True, index=True)
    market_overview = Column(Text)       # JSON: 涨跌家数、成交额等
    emotion_summary = Column(Text)       # JSON: 情绪分/阶段/趋势
    limit_up_analysis = Column(Text)     # JSON: 涨停分析
    limit_down_analysis = Column(Text)   # JSON: 跌停分析
    broken_board_analysis = Column(Text) # JSON: 炸板分析
    dragon_tiger_summary = Column(Text)  # JSON: 龙虎榜摘要
    capital_summary = Column(Text)       # JSON: 资金流向摘要
    strong_stocks = Column(Text)         # JSON: 强势股摘要
    risk_alarms = Column(Text)           # JSON: 风险预警
    overall_score = Column(Float)        # 综合评分 0-100
    overall_comment = Column(Text)       # 综合评语
    raw_data = Column(Text)              # JSON: 完整原始数据
    created_at = Column(DateTime, server_default=func.now())


# ══════════════════════════════════════════════════════════════
# Phase 2 新增表：选股策略 + 实盘交易 + 基础底库
# ══════════════════════════════════════════════════════════════


class StockBasic(Base):
    """全市场个股基础信息底库"""
    __tablename__ = "stock_basic"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, unique=True, index=True)
    name = Column(String(50))
    market = Column(String(10))          # sh/sz/bj
    industry = Column(String(50))        # 所属行业
    concept = Column(String(200))        # 所属概念(逗号分隔)
    total_cap = Column(BigInteger)       # 总市值
    circulating_cap = Column(BigInteger) # 流通市值
    list_date = Column(String(10))       # 上市日期
    delist_date = Column(String(10))     # 退市日期
    is_st = Column(Boolean, default=False)
    status = Column(String(10), default="active")  # active/delisted/paused
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_sb_code", "code", unique=True),
    )


class SectorTree(Base):
    """同花顺行业板块树"""
    __tablename__ = "sector_tree"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sector_code = Column(String(20), nullable=False, unique=True, index=True)
    sector_name = Column(String(50))
    parent_code = Column(String(20))     # 父级板块代码 (NULL=顶级)
    level = Column(Integer, default=1)   # 层级 1/2/3
    stock_count = Column(Integer)        # 成分股数量
    source = Column(String(20))          # 881/884/885/886
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_st_parent", "parent_code"),
    )


class StrategyRecord(Base):
    """选股策略历史回测记录"""
    __tablename__ = "strategy_record"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    strategy_name = Column(String(50), nullable=False)
    trade_date = Column(String(10), nullable=False, index=True)
    filters_json = Column(Text)          # JSON: 筛选条件
    result_json = Column(Text)           # JSON: 选股结果列表
    result_count = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_sr_date", "trade_date"),
        Index("idx_sr_name_date", "strategy_name", "trade_date"),
    )


class AccountInfo(Base):
    """实盘多账户配置表"""
    __tablename__ = "account_info"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_name = Column(String(50), nullable=False, unique=True)
    broker = Column(String(50))          # 券商名称
    account_type = Column(String(20), default="stock")  # stock/credit
    api_key = Column(String(200))        # API密钥(加密存储)
    api_secret = Column(String(200))
    initial_capital = Column(BigInteger)  # 初始资金
    status = Column(String(10), default="active")  # active/disabled
    remark = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PositionRecord(Base):
    """持仓同步记录表"""
    __tablename__ = "position_record"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    trade_date = Column(String(10), nullable=False, index=True)
    code = Column(String(10), nullable=False)
    name = Column(String(50))
    quantity = Column(Integer)           # 持仓数量
    available_qty = Column(Integer)      # 可用数量
    cost_price = Column(Float)           # 成本价
    current_price = Column(Float)        # 当前价
    market_value = Column(BigInteger)    # 市值
    profit = Column(BigInteger)          # 浮动盈亏
    profit_pct = Column(Float)           # 盈亏比例
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_pr_date_code", "trade_date", "code"),
        Index("idx_pr_account_date", "account_id", "trade_date"),
    )


class OrderRecord(Base):
    """委托单/成交单流水表"""
    __tablename__ = "order_record"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    trade_date = Column(String(10), nullable=False, index=True)
    order_time = Column(DateTime)        # 委托时间
    code = Column(String(10), nullable=False)
    name = Column(String(50))
    direction = Column(String(10))       # buy/sell
    order_type = Column(String(20))      # limit/market/conditional
    price = Column(Float)                # 委托价格
    quantity = Column(Integer)           # 委托数量
    filled_qty = Column(Integer, default=0)   # 成交数量
    filled_price = Column(Float)         # 成交均价
    filled_amount = Column(BigInteger)   # 成交金额
    status = Column(String(20))          # pending/filled/partial/cancelled/rejected
    order_id = Column(String(50))        # 券商委托编号
    trigger_price = Column(Float)        # 条件单触发价
    trigger_type = Column(String(20))    # price_above/price_below/pct_above/pct_below
    remark = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_or_date", "trade_date"),
        Index("idx_or_account_date", "account_id", "trade_date"),
    )


class RiskBlacklist(Base):
    """个股风控黑名单表"""
    __tablename__ = "risk_blacklist"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, unique=True, index=True)
    name = Column(String(50))
    reason = Column(Text)                # 加入原因
    added_date = Column(String(10))
    removed_date = Column(String(10))    # 移除日期(NULL=仍在黑名单)
    status = Column(String(10), default="active")  # active/removed
    created_at = Column(DateTime, server_default=func.now())
