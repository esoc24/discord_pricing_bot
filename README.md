# Discord Game Price Monitor Bot

A Discord bot for monitoring Steam game prices using the [gg.deals API](https://gg.deals/api/). Get instant price information, create watchlists, and receive automated alerts when games reach your target price.

## Features

- **Slash Commands** - Modern Discord slash command interface
- **Price Monitoring** - Track current retail and keyshop prices for any Steam game
- **Watchlists** - Set target prices and get notified when games go on sale
- **Steam Wishlist Import** - Instantly import your entire Steam wishlist with one command
- **Persistent Storage** - SQLite database keeps your watchlists safe across restarts
- **Background Alerts** - Automated price checking every 30 minutes
- **Price Caching** - 5-minute cache reduces API calls and improves performance
- **Multi-Region Support** - Check prices in different regions (US, EU, UK, etc.)
- **Historical Data** - View historical low prices for games

## Commands

| Command | Description |
|---------|-------------|
| `/search <query>` | Search for games by name |
| `/prices <steam_app_id> [region]` | Get current prices for a Steam game |
| `/watch <steam_app_id> [target_price] [region]` | Add a game to your watchlist |
| `/unwatch <steam_app_id>` | Remove a game from your watchlist |
| `/watchlist [region]` | View all games on your watchlist |
| `/import-wishlist <steam_id> [target_price] [region]` | Import your Steam wishlist to watchlist |
| `/apitest` | Test API connection (admin only) |

## Installation

### Prerequisites

- Python 3.8 or higher
- Discord Bot Token ([Get one here](https://discord.com/developers/applications))
- gg.deals API Key ([Get one here](https://gg.deals/api/))

### Setup

1. **Clone the repository**
   ```bash
   git clone git@github.com:esoc24/discord_pricing_bot.git
   cd discord_pricing_bot
   ```

2. **Install dependencies**
   ```bash
   pip3 install discord.py aiohttp
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your credentials:
   ```env
   BOT_TOKEN=your_discord_bot_token_here
   GGDEALS_API_KEY=your_ggdeals_api_key_here
   ```

4. **Run the bot**
   ```bash
   python3 bot.py
   ```

### Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Navigate to the **Bot** section
4. Enable **Message Content Intent**
5. Copy your bot token and add it to `.env`
6. Invite the bot to your server with the following permissions:
   - Send Messages
   - Embed Links
   - Use Slash Commands

## Configuration

The bot uses environment variables for configuration. See `.env.example` for all available options.

**Required:**
- `BOT_TOKEN` - Your Discord bot token
- `GGDEALS_API_KEY` - Your gg.deals API key

**Optional:**
- Database file location (default: `game_watchlist.db`)
- Cache duration (default: 5 minutes)
- Price check interval (default: 30 minutes)

## Usage Examples

### Check a game's current price
```
/prices 730
```
Shows current retail and keyshop prices for Counter-Strike 2 (Steam App ID: 730)

### Add a game to your watchlist
```
/watch 292030 9.99
```
Adds The Witcher 3 to your watchlist with a target price of $9.99

### View your watchlist
```
/watchlist
```
Displays all games you're watching with current prices

### Search for games
```
/search Portal
```
Searches for games matching "Portal" (limited to common games)

### Import your Steam wishlist
```
/import-wishlist 76561197960287930 9.99
```
Imports all games from your Steam wishlist with a $9.99 target price. Your Steam profile must be public.

**Finding your Steam ID:**
- Go to your Steam profile URL
- Your Steam ID is the number after `/profiles/` or your custom URL name after `/id/`
- Example: `https://steamcommunity.com/profiles/76561197960287930` → Steam ID is `76561197960287930`
- Example: `https://steamcommunity.com/id/username` → Steam ID is `username`

## Project Structure

```
discord-bot-pricing/
├── bot.py              # Main bot file (slash commands, database, API)
├── CLAUDE.md           # Detailed technical documentation
├── .env.example        # Environment variable template
├── .gitignore          # Git ignore rules
└── game_watchlist.db   # SQLite database (auto-created)
```

## Database Schema

The bot uses SQLite with a single `watchlist` table:

```sql
CREATE TABLE watchlist (
    user_id INTEGER,
    steam_app_id TEXT,
    game_title TEXT,
    channel_id INTEGER,
    target_price REAL,
    region TEXT DEFAULT 'us',
    added_at TEXT,
    PRIMARY KEY (user_id, steam_app_id)
);
```

## Development

### Running in Development Mode

```bash
# Check syntax
python3 -m py_compile bot.py

# View database contents
sqlite3 game_watchlist.db "SELECT * FROM watchlist;"

# Clear all watches
sqlite3 game_watchlist.db "DELETE FROM watchlist;"
```

### Architecture

The bot is built as a single-file application (`bot.py`) with:
- **Discord.py** - Modern slash command framework
- **aiohttp** - Async HTTP client for API requests
- **SQLite3** - Persistent data storage
- **gg.deals API v1** - Game pricing data

For detailed architecture documentation, see [CLAUDE.md](CLAUDE.md).

## Known Limitations

1. **Game Search** - Currently uses a hardcoded list of popular games. Real Steam API search is planned.
2. **Single Region Monitoring** - Background alerts only check US region (per-user regions coming soon)
3. **No Rate Limiting** - Could hit API limits with many concurrent users
4. **No Notification Throttling** - May send multiple alerts if prices fluctuate

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).

## Acknowledgments

- [gg.deals](https://gg.deals/) for providing the game pricing API
- [discord.py](https://github.com/Rapptz/discord.py) for the Discord API wrapper

## Support

For bugs and feature requests, please [open an issue](https://github.com/esoc24/discord_pricing_bot/issues).

---

**Note:** This bot requires valid API credentials and proper Discord bot setup. Never commit your `.env` file or share your credentials publicly.
