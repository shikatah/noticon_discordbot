import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _parse_int(name: str, default: int | None = None) -> int | None:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc


def _parse_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean (true/false).")


@dataclass(slots=True)
class Settings:
    discord_token: str
    discord_guild_id: int | None
    google_cloud_project: str | None
    gemini_api_key: str | None
    anthropic_api_key: str | None
    bot_daily_topic_limit: int
    bot_daily_intervention_limit: int
    bot_quiet_hours_start: int
    bot_quiet_hours_end: int
    welcome_channel_id: int | None
    topic_channel_id: int | None
    bot_enabled_default: bool
    bot_timezone: str
    topic_weekdays: str
    topic_hour: int
    topic_minute: int
    inactive_threshold_days: int
    inactive_check_weekday: str
    inactive_check_hour: int
    inactive_dm_dry_run: bool


def get_settings() -> Settings:
    load_dotenv()

    discord_token = os.getenv("DISCORD_TOKEN", "").strip()
    if not discord_token:
        raise ValueError("DISCORD_TOKEN is required.")

    return Settings(
        discord_token=discord_token,
        discord_guild_id=_parse_int("DISCORD_GUILD_ID"),
        google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        bot_daily_topic_limit=_parse_int("BOT_DAILY_TOPIC_LIMIT", 3) or 3,
        bot_daily_intervention_limit=(
            _parse_int("BOT_DAILY_INTERVENTION_LIMIT", 20) or 20
        ),
        bot_quiet_hours_start=_parse_int("BOT_QUIET_HOURS_START", 23) or 23,
        bot_quiet_hours_end=_parse_int("BOT_QUIET_HOURS_END", 7) or 7,
        welcome_channel_id=_parse_int("WELCOME_CHANNEL_ID"),
        topic_channel_id=_parse_int("TOPIC_CHANNEL_ID"),
        bot_enabled_default=_parse_bool("BOT_ENABLED_DEFAULT", True),
        bot_timezone=os.getenv("BOT_TIMEZONE", "Asia/Tokyo"),
        topic_weekdays=os.getenv("TOPIC_WEEKDAYS", "MON,TUE,WED,THU,FRI"),
        topic_hour=_parse_int("TOPIC_HOUR", 9) or 9,
        topic_minute=_parse_int("TOPIC_MINUTE", 0) or 0,
        inactive_threshold_days=_parse_int("INACTIVE_THRESHOLD_DAYS", 14) or 14,
        inactive_check_weekday=os.getenv("INACTIVE_CHECK_WEEKDAY", "MON"),
        inactive_check_hour=_parse_int("INACTIVE_CHECK_HOUR", 10) or 10,
        inactive_dm_dry_run=_parse_bool("INACTIVE_DM_DRY_RUN", True),
    )
