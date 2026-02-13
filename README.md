# noticon_discordbot

Discord community bot for the Notion learning community "Nochicon".

## Phase 1 (implemented)
- Bot startup with `discord.py`
- Message receive logging (`on_message`)
- Firestore message save (enabled only when configured)
- Slash command `/bot-status`

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
- Set `DISCORD_GUILD_ID` during development so slash commands sync quickly.
