# noticon_discordbot

Discord community bot for the Notion learning community "Nochicon".

## Phase 1 (implemented)
- Bot startup with `discord.py`
- Message receive logging (`on_message`)
- Firestore message save (enabled only when configured)
- Slash command `/bot-status`

## Phase 2 (implemented)
- Gemini primary judge client (`services/gemini.py`)
- Primary decision service with JSON parsing (`services/primary_judge.py`)
- Decision logging to Firestore (`community_bot/data/decision_logs/{message_id}`)
- Automatic primary judgment on every non-bot message

## Phase 3 (minimum implemented)
- Claude secondary judge client (`services/claude.py`)
- Secondary decision service (`services/secondary_judge.py`)
- Trigger secondary judge only when primary judge says intervention needed
- Execute actions: `reply` / `react_only` / `silent`
- Save bot action logs (`community_bot/data/bot_actions/{action_id}`)

## Phase 4 (minimum implemented)
- Member profile service (`services/member_profile.py`)
- Realtime profile updates on every message
- Firestore member profile save (`community_bot/data/members/{user_id}`)

## Phase 5 MVP (implemented)
- Welcome message on `on_member_join` (`services/welcome.py`)
- Scheduled topic posting (`services/topic_generator.py`, `services/scheduler.py`)
- Weekly inactive outreach dry-run (`services/outreach.py`, `services/scheduler.py`)
- Admin commands: `/bot-pause` and `/bot-resume`
- Firestore paths unified under `community_bot/data/...`

## Setup
1. Install Python 3.11.
2. Create virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Create `.env` from `.env.example` and fill required values.
4. In Discord Developer Portal:
   - Enable `MESSAGE CONTENT INTENT`
   - Enable `SERVER MEMBERS INTENT`
5. Run:
   ```bash
   python main.py
   ```

## Notes
- If `GOOGLE_CLOUD_PROJECT` or Google credentials are missing, Firestore is disabled automatically.
- If `GEMINI_API_KEY` is missing, primary judgment runs with safe fallback rules.
- If `ANTHROPIC_API_KEY` is missing, secondary judgment falls back to `silent`.
- Set `DISCORD_GUILD_ID` during development so slash commands sync quickly.
- `WELCOME_CHANNEL_ID` and `TOPIC_CHANNEL_ID` are required to enable Phase 5 welcome/topic features.
- Inactive outreach starts as dry-run by default (`INACTIVE_DM_DRY_RUN=true`).
- `/bot-pause` disables active bot actions until `/bot-resume` is executed.
