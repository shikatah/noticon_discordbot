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
- Decision logging to Firestore (`community_bot/decision_logs/items/{message_id}`)
- Automatic primary judgment on every non-bot message

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
- Set `DISCORD_GUILD_ID` during development so slash commands sync quickly.
