from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 应用
    app_name: str = "NewFupan"
    app_version: str = "2.0.0"
    debug: bool = False

    # PostgreSQL
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_user: str = "bill"
    pg_password: str = ""
    pg_database: str = "new_fupan"

    @property
    def pg_url(self) -> str:
        return f"postgresql+asyncpg://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_database}"

    @property
    def pg_url_sync(self) -> str:
        return f"postgresql://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_database}"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # 量脉
    liangmai_gateway: str = "https://liangmai.pro/api/gateway"
    liangmai_token: str = ""
    liangmai_safe_rate: int = 120
    liangmai_peak_rate: int = 180
    liangmai_snapshot_cooldown: int = 60

    # ── 数据源熔断 ──
    circuit_breaker_threshold: int = 3        # 连续失败N次触发熔断
    circuit_breaker_reset_hour: int = 0       # 凌晨几点自动恢复 (0=0点)

    # ── 慢查询日志 ──
    slow_query_threshold: float = 1.0         # 秒

    # 服务端口
    host: str = "0.0.0.0"
    port: int = 9009

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
