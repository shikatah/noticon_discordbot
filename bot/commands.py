from datetime import datetime, timezone

import discord
from discord import app_commands


def _format_timestamp(value: object) -> str:
    if not isinstance(value, datetime):
        return "N/A"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def register_commands(bot: discord.Client) -> None:
    async def bot_status(interaction: discord.Interaction) -> None:
        started_at = bot.runtime.get("started_at")
        uptime_seconds = 0
        if isinstance(started_at, datetime):
            uptime_seconds = int(
                (datetime.now(timezone.utc) - started_at).total_seconds()
            )

        firestore_state = "enabled" if bot.firestore.enabled else "disabled"
        primary_judge_state = "enabled" if bot.primary_judge.gemini.enabled else "fallback"

        lines = [
            "Bot status",
            f"- Firestore: {firestore_state}",
            f"- Primary judge (Gemini): {primary_judge_state}",
            f"- Messages seen: {bot.runtime.get('messages_seen', 0)}",
            (
                "- Primary flagged: "
                f"{bot.runtime.get('primary_needs_intervention_count', 0)}"
            ),
            f"- Interventions today: {bot.runtime.get('interventions_today', 0)}",
            f"- Last message at: {_format_timestamp(bot.runtime.get('last_message_at'))}",
            f"- Last action at: {_format_timestamp(bot.runtime.get('last_action_at'))}",
            f"- Uptime: {uptime_seconds}s",
        ]

        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    command = app_commands.Command(
        name="bot-status",
        description="Show bot runtime status.",
        callback=bot_status,
    )

    if bot.settings.discord_guild_id is not None:
        bot.tree.add_command(
            command,
            guild=discord.Object(id=bot.settings.discord_guild_id),
        )
        return

    bot.tree.add_command(command)
