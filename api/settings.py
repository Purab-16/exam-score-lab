"""API settings, read from environment variables.

Every hardening feature has its own switch, so a feature that misbehaves can be turned off
without a code change. Defaults are the safe choice.

| Variable                  | Default                                       | Meaning                                  |
|---------------------------|-----------------------------------------------|------------------------------------------|
| API_ENV                   | development                                   | `production` turns off /docs and /redoc  |
| API_CORS_ORIGINS          | http://localhost:3000,http://127.0.0.1:3000   | Browser origins allowed to call the API  |
| SECURITY_HEADERS_ENABLED  | true                                          | nosniff, frame, referrer, CSP headers    |
| GZIP_ENABLED              | true                                          | Compress larger responses                |
| CACHE_HEADERS_ENABLED     | true                                          | ETag and Cache-Control on static data    |
| BODY_LIMIT_ENABLED        | true                                          | Reject oversized request bodies (413)    |
| MAX_UPLOAD_MB             | 5                                             | Largest CSV upload                       |
| RATE_LIMIT_ENABLED        | true                                          | Per-client request limits (429)          |
| RATE_LIMIT_PREDICT        | 60/minute                                     | POST /predict                            |
| RATE_LIMIT_WHAT_IF        | 120/minute                                    | POST /what-if                            |
| RATE_LIMIT_BATCH          | 6/minute                                      | POST /predict/batch                      |
| RATE_LIMIT_DEFAULT        | 120/minute                                    | Every other route except /health         |
| EXPLAINER                 | auto                                          | `auto`: exact formula for linear models, |
|                           |                                               | SHAP for others. `shap`: always SHAP     |
"""
import os
import re
from dataclasses import dataclass
from typing import Mapping, Optional

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}
_UNITS = {"second": 1.0, "minute": 60.0, "hour": 3600.0}

DEFAULT_CORS_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def parse_rate(text: str) -> tuple:
    """'60/minute' -> (60, 60.0): at most 60 requests per 60 seconds."""
    match = re.fullmatch(r"\s*(\d+)\s*/\s*(second|minute|hour)\s*", str(text).lower())
    if not match or int(match.group(1)) < 1:
        raise ValueError(f"Invalid rate limit {text!r}. Use a form like '60/minute' (second, minute or hour).")
    return int(match.group(1)), _UNITS[match.group(2)]


def _flag(env: Mapping, name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"{name} must be true or false, got {raw!r}")


@dataclass(frozen=True)
class Settings:
    api_env: str = "development"
    cors_origins: tuple = DEFAULT_CORS_ORIGINS
    security_headers: bool = True
    gzip: bool = True
    cache_headers: bool = True
    body_limit: bool = True
    rate_limit: bool = True
    rate_limit_predict: str = "60/minute"
    rate_limit_what_if: str = "120/minute"
    rate_limit_batch: str = "6/minute"
    rate_limit_default: str = "120/minute"
    explainer: str = "auto"
    max_upload_bytes: int = 5 * 1024 * 1024
    # Every JSON endpoint takes a few hundred bytes. 64 KB is generous.
    max_json_body_bytes: int = 64 * 1024

    def __post_init__(self):
        if self.api_env not in ("development", "production"):
            raise ValueError(f"API_ENV must be 'development' or 'production', got {self.api_env!r}")
        if self.explainer not in ("auto", "shap"):
            raise ValueError(f"EXPLAINER must be 'auto' or 'shap', got {self.explainer!r}")
        self.rate_rules()  # fail at startup, not on the first request

    @property
    def docs_enabled(self) -> bool:
        return self.api_env != "production"

    def rate_rules(self) -> dict:
        """Route rules as {(method, path): (limit, window_seconds)}, plus the default under key None."""
        return {
            ("POST", "/predict"): parse_rate(self.rate_limit_predict),
            ("POST", "/what-if"): parse_rate(self.rate_limit_what_if),
            ("POST", "/predict/batch"): parse_rate(self.rate_limit_batch),
            None: parse_rate(self.rate_limit_default),
        }

    @classmethod
    def from_env(cls, env: Optional[Mapping] = None) -> "Settings":
        env = os.environ if env is None else env
        defaults = cls()
        origins = env.get("API_CORS_ORIGINS")
        upload_mb = env.get("MAX_UPLOAD_MB")
        return cls(
            api_env=(env.get("API_ENV") or defaults.api_env).strip().lower(),
            cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()) if origins else DEFAULT_CORS_ORIGINS,
            security_headers=_flag(env, "SECURITY_HEADERS_ENABLED", defaults.security_headers),
            gzip=_flag(env, "GZIP_ENABLED", defaults.gzip),
            cache_headers=_flag(env, "CACHE_HEADERS_ENABLED", defaults.cache_headers),
            body_limit=_flag(env, "BODY_LIMIT_ENABLED", defaults.body_limit),
            rate_limit=_flag(env, "RATE_LIMIT_ENABLED", defaults.rate_limit),
            rate_limit_predict=env.get("RATE_LIMIT_PREDICT") or defaults.rate_limit_predict,
            rate_limit_what_if=env.get("RATE_LIMIT_WHAT_IF") or defaults.rate_limit_what_if,
            rate_limit_batch=env.get("RATE_LIMIT_BATCH") or defaults.rate_limit_batch,
            rate_limit_default=env.get("RATE_LIMIT_DEFAULT") or defaults.rate_limit_default,
            explainer=(env.get("EXPLAINER") or defaults.explainer).strip().lower(),
            max_upload_bytes=int(float(upload_mb) * 1024 * 1024) if upload_mb else defaults.max_upload_bytes,
        )
