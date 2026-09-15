"""Central application settings (env-driven, `ZKTECO_` / standard names)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_FILE_CACHE: dict[str, str] = {}


def _read_cached(path: str) -> str:
    if path not in _FILE_CACHE:
        try:
            with open(path, encoding="utf-8") as fh:
                _FILE_CACHE[path] = fh.read()
        except OSError:
            _FILE_CACHE[path] = ""
    return _FILE_CACHE[path]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "zkteco-adms"
    environment: str = Field(default="development")
    debug: bool = False

    database_url: str = Field(
        default="postgresql+asyncpg://zkteco:zkteco@localhost:5432/zkteco_adms"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- ZKTeco ADMS protocol knobs (mirrors Laravel config/zkteco-adms.php) ---
    zkteco_max_body_size: int = Field(default=10 * 1024 * 1024)
    zkteco_online_threshold: int = Field(default=120)
    zkteco_stale_after: int = Field(default=86400)
    zkteco_max_devices: int = Field(default=1000)
    zkteco_max_commands_per_device: int = Field(default=100)
    zkteco_enable_inspect: bool = Field(default=False)
    zkteco_default_timezone: str = Field(default="UTC")
    # Device USERINFO `Password=` field: never persisted unless explicitly enabled.
    zkteco_persist_device_password: bool = Field(default=False)
    # Legacy attendance-terminal handshake.  ACC/Security PUSH terminals use
    # TransTables instead (see the settings below).
    zkteco_trans_flag: str = Field(default="1111000000")
    # Security PUSH 3.x configuration (used by DeviceType=acc, e.g. SpeedFace
    # access-control panels).  The terminal selects the earlier of this and
    # its own advertised protocol version.
    zkteco_push_protocol_version: str = Field(default="3.1.2")
    zkteco_server_version: str = Field(default="3.1.2")
    zkteco_server_name: str = Field(default="ADMS")
    zkteco_error_delay_s: int = Field(default=60)
    zkteco_request_delay_s: int = Field(default=30)
    zkteco_trans_times: str = Field(default="00:00;14:05")
    zkteco_trans_interval_m: int = Field(default=1)
    zkteco_trans_tables: str = Field(default="User Transaction")
    zkteco_realtime: int = Field(default=1)
    zkteco_push_timeout_s: int = Field(default=10)

    # --- JWT RS256 ---
    jwt_private_key: str = Field(default="")
    jwt_public_key: str = Field(default="")
    jwt_private_key_file: str = Field(default=".jwt_private.pem")
    jwt_public_key_file: str = Field(default=".jwt_public.pem")
    jwt_issuer: str = Field(default="zkteco-adms")
    jwt_audience: str = Field(default="zkteco-adms-api")
    jwt_access_ttl: int = Field(default=900)
    jwt_refresh_ttl: int = Field(default=604800)

    # --- Rate limiting (Redis-enforced, see core/ratelimit.py) ---
    ratelimit_login_max_attempts: int = Field(default=10)
    ratelimit_login_window_s: int = Field(default=60)
    # Account lockout (L-06): failed logins per (username, ip) before 429.
    ratelimit_lockout_threshold: int = Field(default=20)
    ratelimit_lockout_window_s: int = Field(default=900)
    ratelimit_refresh_max_attempts: int = Field(default=30)
    ratelimit_refresh_window_s: int = Field(default=60)
    # ADMS per-device/per-IP throttle (generous: normal polling must pass).
    ratelimit_adms_device_max: int = Field(default=600)
    ratelimit_adms_device_window_s: int = Field(default=60)
    ratelimit_adms_ip_max: int = Field(default=3000)
    ratelimit_adms_ip_window_s: int = Field(default=60)

    # --- Command lifecycle (L-02): TTL + max attempts before auto-fail ---
    zkteco_command_ttl_s: int = Field(default=86400)
    zkteco_command_max_attempts: int = Field(default=10)

    # --- Proxy trust (comma-separated IPs/CIDRs allowed to set X-Forwarded-For) ---
    trusted_proxies_raw: str = Field(default="")

    def trusted_proxies(self) -> list[str]:
        return [p.strip() for p in self.trusted_proxies_raw.split(",") if p.strip()]

    # --- HTTP surface (docs/CORS/headers are deployment-owned, see SECURITY.md) ---
    docs_enabled: bool = Field(default=True)
    frontend_origins_raw: str = Field(default="")
    hsts_enabled: bool = Field(default=False)

    def frontend_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origins_raw.split(",") if o.strip()]

    def load_rsa_keys(self) -> tuple[str, str]:
        """Return (private_pem, public_pem), reading *_FILE fallbacks.

        File contents are cached per path for the process lifetime (L-04:
        previously re-read on every token issue/verify). Key rotation
        requires a process restart — documented in docs/SECURITY.md.
        """
        priv = self.jwt_private_key
        pub = self.jwt_public_key
        if not priv:
            priv = _read_cached(self.jwt_private_key_file)
        if not pub:
            pub = _read_cached(self.jwt_public_key_file)
        return priv, pub


@lru_cache
def get_settings() -> Settings:
    return Settings()
