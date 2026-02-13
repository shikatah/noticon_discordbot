import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import discord

from models.message import MessageRecord

logger = logging.getLogger(__name__)


def _infer_channel_type(channel_name: str) -> str:
    lowered = channel_name.lower()
    if "question" in lowered or "質問" in channel_name:
        return "question"
    if "share" in lowered or "共有" in channel_name:
        return "share"
    if "intro" in lowered or "自己紹介" in channel_name:
        return "intro"
    if "announce" in lowered or "告知" in channel_name:
        return "announce"
    return "chat"


def _is_quiet_hours(now: datetime, quiet_start: int, quiet_end: int) -> bool:
    hour = now.hour
    if quiet_start == quiet_end:
        return True
    if quiet_start < quiet_end:
        return quiet_start <= hour < quiet_end
    return hour >= quiet_start or hour < quiet_end


def _recent_channel_activity_count(bot: discord.Client, channel_id: str, now: datetime) -> int:
    activity = bot.runtime.setdefault("channel_activity", {})
    timestamps = activity.setdefault(channel_id, [])

    now_ts = now.timestamp()
    one_hour_ago = now_ts - 3600
    timestamps.append(now_ts)
    while timestamps and timestamps[0] < one_hour_ago:
        timestamps.pop(0)
    return len(timestamps)


def _maybe_reset_daily_counters(bot: discord.Client, now: datetime) -> None:
    today_key = now.astimezone().date().isoformat()
    if bot.runtime.get("day_key") == today_key:
        return
    bot.runtime["day_key"] = today_key
    bot.runtime["interventions_today"] = 0
    bot.runtime["primary_needs_intervention_count"] = 0


def _append_channel_history(
    bot: discord.Client,
    channel_id: str,
    author_name: str,
    content: str,
    created_at: datetime,
) -> None:
    history_map = bot.runtime.setdefault("channel_history", {})
    history = history_map.setdefault(channel_id, [])
    history.append(
        {
            "author": author_name,
            "content": content,
            "timestamp": created_at.isoformat(),
        }
    )
    if len(history) > 20:
        del history[:-20]


def _update_member_stats(
    bot: discord.Client,
    member_id: str,
    channel_name: str,
    now: datetime,
    content: str,
) -> dict[str, object]:
    stats_map = bot.runtime.setdefault("member_stats", {})
    stats = stats_map.setdefault(
        member_id,
        {
            "total_posts": 0,
            "active_channels": {},
            "active_hours": {},
            "total_post_length": 0,
            "last_active_at": None,
        },
    )
    stats["total_posts"] = int(stats["total_posts"]) + 1
    channel_counts = stats["active_channels"]
    channel_counts[channel_name] = int(channel_counts.get(channel_name, 0)) + 1
    hour_key = str(now.astimezone().hour)
    hour_counts = stats["active_hours"]
    hour_counts[hour_key] = int(hour_counts.get(hour_key, 0)) + 1
    stats["total_post_length"] = int(stats["total_post_length"]) + len(content)
    stats["last_active_at"] = now.isoformat()
    return stats


def _make_author_profile(message: discord.Message, stats: dict[str, object]) -> dict[str, object]:
    joined_at = getattr(message.author, "joined_at", None)
    if isinstance(joined_at, datetime):
        joined_at_text = joined_at.isoformat()
    else:
        joined_at_text = None

    roles = getattr(message.author, "roles", [])
    role_names: list[str] = []
    for role in roles:
        role_name = getattr(role, "name", None)
        if isinstance(role_name, str) and role_name != "@everyone":
            role_names.append(role_name)

    total_posts = int(stats.get("total_posts", 0))
    total_post_length = int(stats.get("total_post_length", 0))
    avg_post_length = (total_post_length / total_posts) if total_posts else 0

    return {
        "discord_id": str(message.author.id),
        "display_name": getattr(message.author, "display_name", message.author.name),
        "joined_at": joined_at_text,
        "roles": role_names,
        "stats": {
            "total_posts": total_posts,
            "active_channels": stats.get("active_channels", {}),
            "active_hours": stats.get("active_hours", {}),
            "avg_post_length": round(avg_post_length, 2),
            "last_active_at": stats.get("last_active_at"),
        },
    }


def _append_recent_bot_action(
    bot: discord.Client,
    intervention_type: str,
    channel_id: str,
    target_message_id: str,
    timestamp: datetime,
) -> None:
    recent_actions = bot.runtime.setdefault("bot_recent_actions", [])
    recent_actions.append(
        {
            "intervention_type": intervention_type,
            "channel_id": channel_id,
            "target_message_id": target_message_id,
            "timestamp": timestamp.isoformat(),
        }
    )
    if len(recent_actions) > 20:
        del recent_actions[:-20]


def _can_intervene(bot: discord.Client, in_quiet_hours: bool) -> tuple[bool, str]:
    if in_quiet_hours:
        return False, "quiet_hours"
    if int(bot.runtime.get("interventions_today", 0)) >= bot.settings.bot_daily_intervention_limit:
        return False, "daily_limit_reached"
    return True, "ok"


async def _execute_secondary_action(
    message: discord.Message,
    intervention_type: str,
    content: str,
    mention_users: list[str],
    reaction_emoji: str | None,
) -> tuple[str, str | None]:
    if intervention_type == "silent":
        return "silent", None

    if intervention_type == "react_only":
        emoji = reaction_emoji or "👀"
        await message.add_reaction(emoji)
        return "react_only", emoji

    body = content.strip()
    if not body:
        return "silent", None
    if mention_users:
        mentions = " ".join(f"<@{uid}>" for uid in mention_users)
        body = f"{mentions}\n{body}"

    sent = await message.reply(body, mention_author=False)
    return intervention_type, str(sent.id)


async def _resolve_text_channel(bot: discord.Client, channel_id: int) -> discord.TextChannel | None:
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception:
            logger.exception("Failed to resolve text channel: %s", channel_id)
            return None
    if isinstance(channel, discord.TextChannel):
        return channel
    logger.warning("Configured channel is not a text channel: %s", channel_id)
    return None


def register_event_handlers(bot: discord.Client) -> None:
    @bot.event
    async def on_ready() -> None:
        if bot.user is None:
            return
        logger.info("Logged in as %s (%s)", bot.user, bot.user.id)

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot:
            return

        now = datetime.now(timezone.utc)
        _maybe_reset_daily_counters(bot, now)

        bot.runtime["messages_seen"] = int(bot.runtime["messages_seen"]) + 1
        bot.runtime["last_message_at"] = now

        record = MessageRecord.from_discord(message)
        await bot.firestore.save_message(record)

        channel_name = getattr(message.channel, "name", "unknown")
        channel_id = str(message.channel.id)
        channel_type = _infer_channel_type(channel_name)

        joined_at = getattr(message.author, "joined_at", None)
        author_is_new = False
        if isinstance(joined_at, datetime):
            if joined_at.tzinfo is None:
                joined_at = joined_at.replace(tzinfo=timezone.utc)
            author_is_new = (now - joined_at) <= timedelta(days=7)

        author_stats = _update_member_stats(
            bot=bot,
            member_id=str(message.author.id),
            channel_name=channel_name,
            now=now,
            content=message.content,
        )
        _append_channel_history(
            bot=bot,
            channel_id=channel_id,
            author_name=getattr(message.author, "display_name", message.author.name),
            content=message.content,
            created_at=record.timestamp,
        )
        channel_history = bot.runtime.get("channel_history", {}).get(channel_id, [])
        recent_posts = [
            str(item.get("content", ""))
            for item in channel_history
            if item.get("author")
            == getattr(message.author, "display_name", message.author.name)
        ][-10:]

        profile_payload = bot.member_profile.build_realtime_profile(
            message=message,
            stats=author_stats,
            recent_posts=recent_posts,
            now=now,
        )
        await bot.firestore.save_member_profile(str(message.author.id), profile_payload)
        bot.runtime["member_profiles_updated"] = int(bot.runtime["member_profiles_updated"]) + 1

        if not bot.runtime.get("bot_enabled", True):
            logger.info("Bot is paused. Skipping active intervention pipeline.")
            return

        recent_activity = _recent_channel_activity_count(bot, channel_id, now)
        in_quiet_hours = _is_quiet_hours(
            now.astimezone(),
            bot.settings.bot_quiet_hours_start,
            bot.settings.bot_quiet_hours_end,
        )

        primary_input = {
            "message_content": message.content,
            "channel_type": channel_type,
            "hours_since_post": 0.0,
            "has_reply": False,
            "has_reaction": len(message.reactions) > 0,
            "is_bot_mentioned": bool(bot.user and bot.user in message.mentions),
            "author_is_new": author_is_new,
            "recent_channel_activity": recent_activity,
            "in_quiet_hours": in_quiet_hours,
        }

        decision = await bot.primary_judge.judge(primary_input)
        await bot.firestore.save_primary_decision(record.message_id, primary_input, decision)
        if decision.needs_intervention:
            bot.runtime["primary_needs_intervention_count"] = int(
                bot.runtime["primary_needs_intervention_count"]
            ) + 1

            can_intervene, skip_reason = _can_intervene(bot, in_quiet_hours)
            secondary_result = None
            action_outcome = "skipped"
            action_ref: str | None = None
            action_reason = skip_reason

            if can_intervene:
                channel_context = channel_history
                author_profile = _make_author_profile(message, author_stats)
                author_profile["interests"] = profile_payload.get("interests", {})
                author_profile["context"] = profile_payload.get("context", {})
                secondary_input = {
                    "message_content": message.content,
                    "channel_context": channel_context,
                    "channel_type": channel_type,
                    "author_profile": author_profile,
                    "time_context": {
                        "now": now.astimezone().isoformat(),
                        "weekday": now.astimezone().strftime("%A"),
                        "hour": now.astimezone().hour,
                    },
                    "bot_recent_actions": bot.runtime.get("bot_recent_actions", []),
                }
                secondary_result = await bot.secondary_judge.judge(secondary_input)

                try:
                    action_outcome, action_ref = await _execute_secondary_action(
                        message=message,
                        intervention_type=secondary_result.intervention_type,
                        content=secondary_result.content,
                        mention_users=secondary_result.mention_users,
                        reaction_emoji=secondary_result.reaction_emoji,
                    )
                    action_reason = secondary_result.reasoning
                    if action_outcome != "silent":
                        bot.runtime["interventions_today"] = int(
                            bot.runtime["interventions_today"]
                        ) + 1
                        bot.runtime["last_action_at"] = now
                        _append_recent_bot_action(
                            bot=bot,
                            intervention_type=secondary_result.intervention_type,
                            channel_id=channel_id,
                            target_message_id=record.message_id,
                            timestamp=now,
                        )
                        await bot.firestore.update_message_bot_action(
                            message_id=record.message_id,
                            action_type=secondary_result.intervention_type,
                            action_at=now,
                        )
                except Exception:
                    logger.exception("Failed to execute secondary action.")
                    action_outcome = "failed"
                    action_reason = "action_execution_failed"

            action_id = f"{record.message_id}-{uuid4().hex[:8]}"
            if secondary_result is None:
                secondary_payload: dict[str, object] = {
                    "intervention_type": "silent",
                    "tone": "warm",
                    "content": "",
                    "mention_users": [],
                    "reaction_emoji": None,
                    "confidence": 0.0,
                    "reasoning": f"skipped:{skip_reason}",
                    "model": "skip-rule",
                }
            else:
                secondary_payload = secondary_result.to_dict()

            await bot.firestore.save_bot_action(
                action_id=action_id,
                payload={
                    "type": secondary_payload.get("intervention_type"),
                    "channel_id": channel_id,
                    "target_message_id": record.message_id,
                    "content": secondary_payload.get("content", ""),
                    "reasoning": action_reason,
                    "confidence": secondary_payload.get("confidence", 0.0),
                    "timestamp": now,
                    "model": secondary_payload.get("model"),
                    "primary_decision": decision.to_dict(),
                    "secondary_decision": secondary_payload,
                    "outcome": {
                        "status": action_outcome,
                        "action_ref": action_ref,
                    },
                },
            )

        logger.info(
            "[#%s] %s: %s",
            channel_name,
            getattr(message.author, "display_name", message.author.name),
            message.content[:80],
        )
        logger.info(
            "PrimaryJudge => needs_intervention=%s priority=%s reason=%s",
            decision.needs_intervention,
            decision.priority,
            decision.reason,
        )
        if decision.needs_intervention:
            logger.info(
                "Intervention runtime count: %s/%s",
                bot.runtime.get("interventions_today", 0),
                bot.settings.bot_daily_intervention_limit,
            )

    @bot.event
    async def on_member_join(member: discord.Member) -> None:
        logger.info("Member joined: %s (%s)", member.display_name, member.id)
        now = datetime.now(timezone.utc)

        if not bot.runtime.get("bot_enabled", True):
            await bot.firestore.save_bot_action(
                action_id=f"welcome-skipped-{uuid4().hex[:8]}",
                payload={
                    "type": "welcome",
                    "channel_id": "",
                    "target_message_id": None,
                    "content": "",
                    "reasoning": "bot_paused",
                    "confidence": 0.0,
                    "timestamp": now,
                    "model": "skip-rule",
                    "outcome": {
                        "status": "skipped",
                        "action_ref": str(member.id),
                    },
                },
            )
            return

        welcome_channel_id = bot.settings.welcome_channel_id
        if welcome_channel_id is None:
            await bot.firestore.save_bot_action(
                action_id=f"welcome-skipped-{uuid4().hex[:8]}",
                payload={
                    "type": "welcome",
                    "channel_id": "",
                    "target_message_id": None,
                    "content": "",
                    "reasoning": "welcome_channel_not_configured",
                    "confidence": 0.0,
                    "timestamp": now,
                    "model": "skip-rule",
                    "outcome": {
                        "status": "skipped",
                        "action_ref": str(member.id),
                    },
                },
            )
            return

        channel = await _resolve_text_channel(bot, welcome_channel_id)
        if channel is None:
            await bot.firestore.save_bot_action(
                action_id=f"welcome-failed-{uuid4().hex[:8]}",
                payload={
                    "type": "welcome",
                    "channel_id": str(welcome_channel_id),
                    "target_message_id": None,
                    "content": "",
                    "reasoning": "welcome_channel_resolve_failed",
                    "confidence": 0.0,
                    "timestamp": now,
                    "model": "system",
                    "outcome": {
                        "status": "failed",
                        "action_ref": str(member.id),
                    },
                },
            )
            return

        try:
            welcome_text = await bot.welcome.generate_message(
                member_name=member.display_name,
                now_utc=now,
            )
            send_text = f"{member.mention}\n{welcome_text}"
            sent = await channel.send(send_text)
            await bot.firestore.save_bot_action(
                action_id=f"welcome-{uuid4().hex[:8]}",
                payload={
                    "type": "welcome",
                    "channel_id": str(welcome_channel_id),
                    "target_message_id": str(sent.id),
                    "content": send_text,
                    "reasoning": "member_joined",
                    "confidence": 1.0,
                    "timestamp": now,
                    "model": "welcome-service",
                    "outcome": {
                        "status": "posted",
                        "action_ref": str(sent.id),
                    },
                },
            )
            bot.runtime["last_action_at"] = now
        except Exception:
            logger.exception("Failed to post welcome message.")
            await bot.firestore.save_bot_action(
                action_id=f"welcome-failed-{uuid4().hex[:8]}",
                payload={
                    "type": "welcome",
                    "channel_id": str(welcome_channel_id),
                    "target_message_id": None,
                    "content": "",
                    "reasoning": "welcome_send_failed",
                    "confidence": 0.0,
                    "timestamp": now,
                    "model": "welcome-service",
                    "outcome": {
                        "status": "failed",
                        "action_ref": str(member.id),
                    },
                },
            )
