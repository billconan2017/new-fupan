from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from sqlalchemy.engine import URL
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
        return self._database_url("postgresql+asyncpg").render_as_string(hide_password=False)

    @property
    def pg_url_sync(self) -> str:
        return self._database_url("postgresql+psycopg2").render_as_string(hide_password=False)

    def _database_url(self, driver):
        if self.pg_host.startswith("/"):
            return URL.create(driver, username=self.pg_user, database=self.pg_database, query={"host": self.pg_host, "port": str(self.pg_port)})
        return URL.create(driver, username=self.pg_user, password=self.pg_password,
                          host=self.pg_host, port=self.pg_port, database=self.pg_database)

    # Optional legacy SQLite warehouse; used only for explicit read-only history.
    legacy_market_db: str = ""

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
    liangmai_snapshot_cooldown: int = Field(default=60, ge=60)
    liangmai_timeout: float = Field(default=10, gt=0)
    liangmai_total_timeout: float = Field(default=25, gt=0)
    liangmai_max_attempts: int = Field(default=3, ge=1, le=5)
    liangmai_cache_max_entries: int = Field(default=256, ge=1)
    scheduler_enabled: bool = True

    # ── 数据源熔断 ──
    circuit_breaker_threshold: int = 3        # 连续失败N次触发熔断
    circuit_breaker_reset_hour: int = 0       # 凌晨几点自动恢复 (0=0点)

    # ── 慢查询日志 ──
    slow_query_threshold: float = 1.0         # 秒

    # 服务端口
    host: str = "0.0.0.0"
    port: int = 9009

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
