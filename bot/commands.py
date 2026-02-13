from datetime import datetime, timezone

import discord
from discord import app_commands


def _format_timestamp(value: object) -> str:
    if not isinstance(value, datetime):
        return "N/A"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _format_iso_or_na(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return "N/A"
    return value


def _is_admin(interaction: discord.Interaction) -> bool:
    user = interaction.user
    if not isinstance(user, discord.Member):
        return False
    perms = user.guild_permissions
    return perms.administrator or perms.manage_guild


async def _set_bot_enabled(bot: discord.Client, enabled: bool) -> None:
    bot.runtime["bot_enabled"] = enabled
    await bot.firestore.save_config_partial({"bot_enabled": enabled})


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
        secondary_judge_state = (
            "enabled" if bot.secondary_judge.claude.enabled else "fallback"
        )
        bot_enabled = bool(bot.runtime.get("bot_enabled", True))

        lines = [
            "Bot status",
            f"- Bot enabled: {bot_enabled}",
            f"- Firestore: {firestore_state}",
            f"- Primary judge (Gemini): {primary_judge_state}",
            f"- Secondary judge (Claude): {secondary_judge_state}",
            f"- Scheduler running: {bot.runtime.get('scheduler_running', False)}",
            (
                "- Next topic run: "
                f"{_format_iso_or_na(bot.runtime.get('scheduler_next_topic_at'))}"
            ),
            (
                "- Next inactive run: "
                f"{_format_iso_or_na(bot.runtime.get('scheduler_next_inactive_at'))}"
            ),
            f"- Inactive DM dry-run: {bot.settings.inactive_dm_dry_run}",
            f"- Messages seen: {bot.runtime.get('messages_seen', 0)}",
            (
                "- Primary flagged: "
                f"{bot.runtime.get('primary_needs_intervention_count', 0)}"
            ),
            f"- Member profiles updated: {bot.runtime.get('member_profiles_updated', 0)}",
            f"- Interventions today: {bot.runtime.get('interventions_today', 0)}",
            f"- Last message at: {_format_timestamp(bot.runtime.get('last_message_at'))}",
            f"- Last action at: {_format_timestamp(bot.runtime.get('last_action_at'))}",
            f"- Uptime: {uptime_seconds}s",
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    async def bot_pause(interaction: discord.Interaction) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "管理者のみ実行できます。",
                ephemeral=True,
            )
            return
        await _set_bot_enabled(bot, False)
        await interaction.response.send_message("Botを一時停止しました。", ephemeral=True)

    async def bot_resume(interaction: discord.Interaction) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "管理者のみ実行できます。",
                ephemeral=True,
            )
            return
        await _set_bot_enabled(bot, True)
        await interaction.response.send_message("Botを再開しました。", ephemeral=True)

    commands_to_add = [
        app_commands.Command(
            name="bot-status",
            description="Show bot runtime status.",
            callback=bot_status,
        ),
        app_commands.Command(
            name="bot-pause",
            description="Pause bot actions (admin only).",
            callback=bot_pause,
        ),
        app_commands.Command(
            name="bot-resume",
            description="Resume bot actions (admin only).",
            callback=bot_resume,
        ),
    ]

    if bot.settings.discord_guild_id is not None:
        guild = discord.Object(id=bot.settings.discord_guild_id)
        for command in commands_to_add:
            bot.tree.add_command(command, guild=guild)
        return

    for command in commands_to_add:
        bot.tree.add_command(command)
