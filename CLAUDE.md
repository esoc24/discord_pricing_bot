# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Discord bot for monitoring Steam game prices using the gg.deals API. Users can search games, check prices, create watchlists with target prices, and receive automated price alerts. Built with discord.py and SQLite for data persistence.

## Running the Bot

### Initial Setup

1. Install required packages:
```bash
pip3 install -r requirements.txt
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env and add your credentials
```

3. Run the bot:
```bash
python3 bot.py
```

### Dependencies

Required Python packages:
- `discord.py` (>=2.0) - Discord API wrapper with slash commands support
- `aiohttp` - Async HTTP client for API requests
- `sqlite3` - Built-in Python module for database

### Configuration

The bot uses environment variables for credentials (loaded from `.env` file or system environment).

**Required environment variables:**
- `BOT_TOKEN` - Discord bot token from [Discord Developer Portal](https://discord.com/developers/applications)
- `GGDEALS_API_KEY` - API key from [gg.deals API](https://gg.deals/api/)

**Setting up credentials:**

1. Copy the example file: `cp .env.example .env`
2. Edit `.env` and replace placeholder values with your actual credentials
3. The `.env` file is gitignored to prevent accidental commits

**Alternative:** Set environment variables directly:
```bash
export BOT_TOKEN="your_token_here"
export GGDEALS_API_KEY="your_api_key_here"
python3 bot.py
```

**Discord Bot Requirements:**
- Message Content Intent (must be enabled in Discord Developer Portal)
- Send Messages permission
- Embed Links permission
- Use Slash Commands permission

## Architecture

### Single-File Design

All functionality is contained in `bot.py` (~685 lines):
- Environment variable loading (`.env` file support)
- Discord slash command handlers
- gg.deals API integration
- SQLite database operations
- Background price monitoring task
- Price caching system

**Environment Loading** (lines 18-32)

The bot includes a simple `.env` file parser that loads environment variables at startup:
- No external dependencies required (no python-dotenv needed)
- Automatically loads `.env` file from the same directory as `bot.py`
- Supports comments (lines starting with `#`)
- Removes quotes from values
- Environment variables take precedence if already set

### Core Components

**GamePriceMonitor Class** (lines 25-239)

Manages all price tracking and data persistence:
- `_init_database()`: Creates SQLite schema on startup
- `get_game_prices()`: Fetches prices from gg.deals API with 5-minute cache
- `add_to_watchlist()`: Persists game watches to database
- `get_all_watched_games()`: Retrieves all active watches for background monitoring

**Database Schema**

SQLite database (`game_watchlist.db`) with single table:
```sql
watchlist (
    user_id INTEGER,
    steam_app_id TEXT,
    game_title TEXT,
    channel_id INTEGER,
    target_price REAL,
    region TEXT DEFAULT 'us',
    added_at TEXT,
    PRIMARY KEY (user_id, steam_app_id)
)
```

Data persists across bot restarts. Uses `INSERT OR REPLACE` for upserts.

**API Integration**

Uses gg.deals API v1:
- Endpoint: `https://api.gg.deals/v1/prices/by-steam-app-id/`
- Authentication: API key in URL params (`?key=...`)
- Supports batch requests (multiple Steam App IDs)
- Regional pricing via `region` parameter
- Returns retail prices, keyshop prices, and historical lows

Price cache: 5-minute in-memory cache (`self.price_cache`) to reduce API calls.

**Slash Commands**

All commands use Discord's slash command system (`@bot.tree.command`):
- `/search <query>` - Search hardcoded game list (not real search)
- `/prices <steam_app_id> [region]` - Get current and historical prices
- `/watch <steam_app_id> [target_price] [region] [game_name]` - Add to watchlist
- `/unwatch <steam_app_id>` - Remove from watchlist
- `/watchlist [region]` - Show all watched games with current prices
- `/import-wishlist <steam_id> [target_price] [region]` - Import Steam wishlist
- `/apitest` - Test API connection (admin only)

Commands sync automatically on bot startup via `bot.tree.sync()`.

**Background Price Monitoring** (lines 533-636)

`price_check_task` runs every 30 minutes:
1. Fetches all watched games from database
2. Batch requests prices for all games
3. Compares current price vs target price
4. Sends Discord embed notification when price <= target
5. Mentions user in channel where watch was created

Price comparison logic: Uses lower of retail/keyshop as "best price".

### Game Search Limitation

`search_steam_games()` does NOT use a real API. It matches against a hardcoded list of 10 popular Steam games. To implement real search:
- Integrate Steam Web API
- Use third-party game database
- Maintain local SQLite game catalog

### Steam Wishlist Import

`fetch_steam_wishlist()` method (lines 180-222) fetches a user's Steam wishlist:
- Uses Steam Store endpoint: `https://store.steampowered.com/wishlist/profiles/{steam_id}/wishlistdata/`
- Supports both numeric Steam IDs (64-bit) and custom URL names
- Tries both `/profiles/{id}/` and `/id/{id}/` URL formats
- Requires the Steam profile to be public
- Returns JSON with app IDs and game names

The `/import-wishlist` command:
- Fetches all games from Steam wishlist
- Bulk imports to bot watchlist with optional target price
- Shows import summary with success/skip counts
- All imported games are added to the database with same region and target price

### Data Flow Example

1. User runs `/watch 730 19.99` (Counter-Strike 2, $19.99 target)
2. Bot validates Steam App ID via gg.deals API
3. Record inserted into database with user_id, channel_id, target
4. Every 30 minutes, background task queries database
5. Batch API request fetches current prices
6. If price <= $19.99, bot sends alert to original channel

## Development Commands

**Syntax Check**
```bash
python3 -m py_compile bot.py
```

**Test Environment Variables**
```bash
# Verify .env file is loading correctly
python3 -c "from bot import BOT_TOKEN, GGDEALS_API_KEY; print('BOT_TOKEN:', 'SET' if BOT_TOKEN else 'NOT SET'); print('GGDEALS_API_KEY:', 'SET' if GGDEALS_API_KEY else 'NOT SET')"
```

**Database Inspection**
```bash
sqlite3 game_watchlist.db "SELECT * FROM watchlist;"
```

**Clear All Watches**
```bash
sqlite3 game_watchlist.db "DELETE FROM watchlist;"
```

## Key Implementation Details

**Slash Command Patterns**

Commands using `defer()` (long-running operations):
- `/prices` - API request before response
- `/watch` - API validation before insert
- `/watchlist` - Batch API request for all games

Commands with immediate response:
- `/search` - Instant hardcoded lookup
- `/unwatch` - Fast database delete

**Error Handling**

Global error handler at `@bot.tree.error` catches all slash command errors. Sends ephemeral error messages to users.

**Session Management**

aiohttp session (`monitor.session`) is reused across requests and cleaned up on disconnect.

**Price Comparison Logic**

Bot always uses the minimum of retail and keyshop prices for alerts and display. This is hardcoded in multiple places (watchlist display, background alerts).

## Known Limitations

1. **No real game search**: Only 10 hardcoded games searchable
2. **No rate limiting**: Could hit API limits with many users
3. **Single region monitoring**: Background task only checks "us" region
4. **No notification throttling**: Could spam users if price fluctuates
5. **No database migrations**: Schema changes require manual ALTER TABLE

## Future Improvements

- Implement real Steam game search API
- Add per-user region preferences
- Rate limit API requests
- Add database migration system
- Implement notification cooldown period
- Add /help command with embed showing all commands
- Support multiple price alert thresholds per game
- Add optional python-dotenv dependency for better .env handling
