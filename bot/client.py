from datetime import datetime, timezone
from typing import Any

import discord
from discord.ext import commands

from bot.commands import register_commands
from bot.events import register_event_handlers
from config.settings import Settings
from services.firestore import FirestoreService
from services.primary_judge import PrimaryJudgeService
from services.secondary_judge import SecondaryJudgeService


class CommunityBot(commands.Bot):
    def __init__(
        self,
        settings: Settings,
        firestore: FirestoreService,
        primary_judge: PrimaryJudgeService,
        secondary_judge: SecondaryJudgeService,
    ) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(command_prefix="!", intents=intents)
        self.settings = settings
        self.firestore = firestore
        self.primary_judge = primary_judge
        self.secondary_judge = secondary_judge
        self.runtime: dict[str, Any] = {
            "started_at": datetime.now(timezone.utc),
            "day_key": datetime.now(timezone.utc).date().isoformat(),
            "messages_seen": 0,
            "interventions_today": 0,
            "primary_needs_intervention_count": 0,
            "last_message_at": None,
            "last_action_at": None,
            "channel_activity": {},
            "channel_history": {},
            "member_stats": {},
            "bot_recent_actions": [],
        }

    async def setup_hook(self) -> None:
        register_event_handlers(self)
        register_commands(self)

        if self.settings.discord_guild_id is not None:
            guild = discord.Object(id=self.settings.discord_guild_id)
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} command(s) to guild {guild.id}")
            return

        synced = await self.tree.sync()
        print(f"Synced {len(synced)} global command(s)")
