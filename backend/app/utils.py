"""交易日判断 + 通用工具

使用 chinesecalendar 判断法定节假日、A股休市日。
"""
import logging
from datetime import date, datetime
from typing import Optional

log = logging.getLogger("utils")

# chinesecalendar 导入（容错）
try:
    from chinese_calendar import is_workday, is_holiday
    _HAS_CHINESE_CAL = True
except ImportError:
    _HAS_CHINESE_CAL = False
    log.warning("chinesecalendar 未安装，节假日判断降级为周末跳过")


def is_trading_day(d: date = None) -> bool:
    """判断是否为A股交易日

    规则：
    1. 周六日 → False
    2. chinesecalendar 可用时：非工作日 → False
    3. 兜底：仅跳过周末
    """
    d = d or date.today()
    if d.weekday() >= 5:
        return False
    if _HAS_CHINESE_CAL:
        return is_workday(d)
    return True


def get_today_str() -> str:
    return date.today().isoformat()


def parse_trade_date(trade_date: Optional[str]) -> str:
    """解析交易日期参数，默认今天"""
    if trade_date:
        return trade_date
    return get_today_str()


def is_dragon_tiger_available(trade_date: str = None) -> tuple[bool, str]:
    """检查龙虎榜数据是否可查询

    龙虎榜由交易所在每日收盘后公布（通常15:30后）。
    交易日15:30前查询返回提示。
    """
    td = parse_trade_date(trade_date)
    today = date.today()

    # 历史日期可以查
    if td < today.isoformat():
        return True, ""

    # 当天需要15:30后
    now = datetime.now()
    if td == today.isoformat():
        if now.hour < 15 or (now.hour == 15 and now.minute < 30):
            return False, "龙虎榜单每日收盘后交易所公布，盘前盘中无数据（15:30后更新）"

    return True, ""


def safe_float(val, default=0.0) -> float:
    """安全浮点数转换"""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0) -> int:
    """安全整数转换"""
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default
