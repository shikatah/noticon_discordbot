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
    )
