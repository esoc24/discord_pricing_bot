import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import json
import sqlite3
import os
from datetime import datetime
import logging
from typing import Optional, Dict, List
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
def load_env_file():
    """Load .env file if it exists (simple implementation without python-dotenv)"""
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip().strip('"').strip("'")
                    os.environ[key.strip()] = value

load_env_file()

# Bot configuration from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
GGDEALS_API_KEY = os.getenv("GGDEALS_API_KEY")

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent for commands
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

class GamePriceMonitor:
    def __init__(self):
        self.session = None
        self.db_path = "game_watchlist.db"
        # Cache for recent price checks to avoid excessive API calls
        self.price_cache = {}
        self.cache_duration = 300  # 5 minutes cache
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for persistent watchlist storage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                user_id INTEGER,
                steam_app_id TEXT,
                game_title TEXT,
                channel_id INTEGER,
                target_price REAL,
                region TEXT DEFAULT 'us',
                added_at TEXT,
                PRIMARY KEY (user_id, steam_app_id)
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")

    async def get_session(self):
        """Get or create aiohttp session - no auth headers needed, key is in URL params"""
        if self.session is None or self.session.closed:
            headers = {
                'User-Agent': 'Discord-Price-Bot/1.0',
                'Accept': 'application/json'
            }
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session
    
    async def test_api_connection(self):
        """Test API connection with the correct gg.deals v1 endpoint"""
        session = await self.get_session()
        
        # Test with Counter-Strike 2 (Steam App ID: 730)
        test_url = f"https://api.gg.deals/v1/prices/by-steam-app-id/?ids=730&key={GGDEALS_API_KEY}"
        
        try:
            async with session.get(test_url) as response:
                logger.info(f"Testing endpoint: {test_url}")
                logger.info(f"Status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        logger.info("✅ gg.deals API connection successful")
                        logger.info(f"Sample response: {json.dumps(data, indent=2)[:300]}...")
                        return True
                    else:
                        logger.error(f"❌ API returned success=false: {data}")
                        return False
                else:
                    response_text = await response.text()
                    logger.error(f"❌ API error {response.status}: {response_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error testing API: {e}")
            return False
    
    async def get_game_prices(self, steam_app_ids: List[str], region: str = "us", use_cache: bool = True) -> Dict:
        """Get current prices for Steam games by App IDs"""
        # Create cache key from the list of IDs
        ids_str = ",".join(sorted(steam_app_ids))
        cache_key = f"prices_{ids_str}_{region}"
        current_time = datetime.now().timestamp()
        
        if use_cache and cache_key in self.price_cache:
            cached_data, timestamp = self.price_cache[cache_key]
            if current_time - timestamp < self.cache_duration:
                return cached_data
        
        session = await self.get_session()
        
        try:
            # Use the correct gg.deals API v1 endpoint
            url = f"https://api.gg.deals/v1/prices/by-steam-app-id/"
            params = {
                'ids': ','.join(steam_app_ids),
                'key': GGDEALS_API_KEY,
                'region': region
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        # Cache the result
                        self.price_cache[cache_key] = (data, current_time)
                        return data
                    else:
                        logger.error(f"API returned success=false: {data}")
                        return {}
                else:
                    response_text = await response.text()
                    logger.error(f"Price API error {response.status}: {response_text}")
                    return {}
                    
        except Exception as e:
            logger.error(f"Error getting prices: {e}")
            return {}
    
    async def search_steam_games(self, query: str) -> List[Dict]:
        """Search for Steam games - this might need to be implemented differently"""
        # Note: gg.deals API appears to work with Steam App IDs
        # You might need to use Steam's API or maintain a local database of games
        # For now, we'll provide a placeholder that returns common games
        
        common_games = [
            {"name": "Counter-Strike 2", "appid": "730"},
            {"name": "Dota 2", "appid": "570"},
            {"name": "Team Fortress 2", "appid": "440"},
            {"name": "Half-Life 2", "appid": "220"},
            {"name": "Portal 2", "appid": "620"},
            {"name": "Left 4 Dead 2", "appid": "550"},
            {"name": "Garry's Mod", "appid": "4000"},
            {"name": "Terraria", "appid": "105600"},
            {"name": "Stardew Valley", "appid": "413150"},
            {"name": "The Witcher 3", "appid": "292030"}
        ]
        
        # Simple text matching
        query_lower = query.lower()
        matches = [game for game in common_games if query_lower in game["name"].lower()]
        
        return matches[:5]  # Return top 5 matches
    
    def add_to_watchlist(self, user_id: int, steam_app_id: str, game_title: str,
                        channel_id: int, target_price: Optional[float] = None, region: str = "us"):
        """Add a game to user's watchlist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO watchlist
            (user_id, steam_app_id, game_title, channel_id, target_price, region, added_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, steam_app_id, game_title, channel_id, target_price, region, datetime.now().isoformat()))

        conn.commit()
        conn.close()

    def remove_from_watchlist(self, user_id: int, steam_app_id: str) -> bool:
        """Remove a game from user's watchlist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('DELETE FROM watchlist WHERE user_id = ? AND steam_app_id = ?',
                      (user_id, steam_app_id))

        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()

        return deleted

    def get_watchlist(self, user_id: int) -> Dict:
        """Get user's watchlist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT steam_app_id, game_title, channel_id, target_price, region, added_at
            FROM watchlist WHERE user_id = ?
        ''', (user_id,))

        watchlist = {}
        for row in cursor.fetchall():
            steam_app_id, game_title, channel_id, target_price, region, added_at = row
            watchlist[steam_app_id] = {
                'game_title': game_title,
                'channel_id': channel_id,
                'target_price': target_price,
                'region': region,
                'added_at': added_at
            }

        conn.close()
        return watchlist

    def get_all_watched_games(self) -> Dict[str, List[Dict]]:
        """Get all watched games organized by steam_app_id"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT user_id, steam_app_id, game_title, channel_id, target_price, region FROM watchlist')

        watched_games = {}
        for row in cursor.fetchall():
            user_id, steam_app_id, game_title, channel_id, target_price, region = row

            if steam_app_id not in watched_games:
                watched_games[steam_app_id] = []

            watched_games[steam_app_id].append({
                'user_id': user_id,
                'game_title': game_title,
                'channel_id': channel_id,
                'target_price': target_price,
                'region': region
            })

        conn.close()
        return watched_games

# Initialize the monitor
monitor = GamePriceMonitor()

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Bot ID: {bot.user.id}')
    logger.info(f'Connected to {len(bot.guilds)} server(s)')

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

    # Test API connection
    logger.info("🔍 Testing gg.deals API connection...")
    api_works = await monitor.test_api_connection()

    if api_works:
        logger.info("✅ gg.deals API connection successful")
    else:
        logger.error("❌ Could not establish connection to gg.deals API")
        logger.error("Please check your API key and internet connection")

    price_check_task.start()  # Start the price monitoring task

@bot.event
async def on_message(message):
    # Don't respond to ourselves
    if message.author == bot.user:
        return

    # Debug logging to see if bot receives messages
    logger.info(f"Message received from {message.author}: {message.content}")

    # This is required to process commands
    await bot.process_commands(message)

@bot.tree.command(name="apitest", description="Test the gg.deals API connection (admin only)")
async def api_test_command(interaction: discord.Interaction):
    """Test the gg.deals API connection (admin use)"""
    if interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🔍 Testing API connection...")

        working_endpoint = await monitor.test_api_connection()

        if working_endpoint:
            await interaction.followup.send(f"✅ API connection successful!")
        else:
            await interaction.followup.send("❌ API connection failed. Check bot logs for details.")
    else:
        await interaction.response.send_message("❌ This command requires administrator permissions.", ephemeral=True)

@bot.tree.command(name="search", description="Search for games (using common Steam games database)")
@app_commands.describe(query="The game name to search for")
async def search_games_command(interaction: discord.Interaction, query: str):
    """Search for games (using common Steam games database)"""
    games = await monitor.search_steam_games(query)

    if not games:
        await interaction.response.send_message(
            f"No games found for '{query}'. Try searching for popular games like 'Counter-Strike', 'Dota', 'Portal', etc."
        )
        return

    embed = discord.Embed(title=f"Search Results for '{query}'", color=0x00ff00)
    embed.set_footer(text="Note: Search uses common Steam games. Use Steam App ID for precise results.")

    for i, game in enumerate(games, 1):
        name = game.get('name', 'Unknown')
        appid = game.get('appid', 'unknown')

        embed.add_field(
            name=f"{i}. {name}",
            value=f"Steam App ID: `{appid}`",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="prices", description="Get current prices for a Steam game by App ID")
@app_commands.describe(
    steam_app_id="The Steam App ID of the game",
    region="Region code (e.g., 'us', 'eu', 'uk')"
)
async def get_prices_command(interaction: discord.Interaction, steam_app_id: str, region: str = "us"):
    """Get current prices for a Steam game by App ID"""
    await interaction.response.defer()

    price_data = await monitor.get_game_prices([steam_app_id], region)

    if not price_data or not price_data.get("success"):
        await interaction.followup.send(f"No price data found for Steam App ID: `{steam_app_id}`")
        return

    game_data = price_data.get("data", {}).get(steam_app_id)
    if not game_data:
        await interaction.followup.send(f"No game data found for Steam App ID: `{steam_app_id}`")
        return

    # Get game title and prices
    game_title = game_data.get("title", f"Steam Game {steam_app_id}")
    prices = game_data.get("prices", {})
    currency = prices.get("currency", "USD")

    embed = discord.Embed(
        title=f"{game_title}",
        description=f"Steam App ID: `{steam_app_id}`",
        color=0x0099ff
    )

    # Current Retail Price
    current_retail = prices.get("currentRetail")
    if current_retail:
        embed.add_field(
            name="Current Retail Price",
            value=f"{current_retail} {currency}",
            inline=True
        )
    else:
        embed.add_field(
            name="Current Retail Price",
            value="Not available",
            inline=True
        )

    # Current Keyshops Price
    current_keyshops = prices.get("currentKeyshops")
    if current_keyshops:
        embed.add_field(
            name="Current Keyshops Price",
            value=f"{current_keyshops} {currency}",
            inline=True
        )
    else:
        embed.add_field(
            name="Current Keyshops Price",
            value="Not available",
            inline=True
        )

    # Add a blank field for better formatting
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    # Historical Low (Retail)
    historical_low_retail = prices.get("historicalLowRetail")
    if historical_low_retail:
        embed.add_field(
            name="Historical Low (Retail)",
            value=f"{historical_low_retail} {currency}",
            inline=True
        )

    # Historical Low (Keyshops)
    historical_low_keyshops = prices.get("historicalLowKeyshops")
    if historical_low_keyshops:
        embed.add_field(
            name="Historical Low (Keyshops)",
            value=f"{historical_low_keyshops} {currency}",
            inline=True
        )

    # Add URL to gg.deals page
    game_url = game_data.get("url")
    if game_url:
        embed.add_field(
            name="View All Deals",
            value=f"[gg.deals page]({game_url})",
            inline=False
        )

    embed.set_footer(text=f"Region: {region.upper()} | Currency: {currency}")

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="watch", description="Add a game to your watchlist using Steam App ID")
@app_commands.describe(
    steam_app_id="The Steam App ID of the game",
    target_price="Optional target price for alerts",
    region="Region code (e.g., 'us', 'eu', 'uk')",
    game_name="Optional custom name for the game"
)
async def add_to_watchlist_command(
    interaction: discord.Interaction,
    steam_app_id: str,
    target_price: float = None,
    region: str = "us",
    game_name: str = None
):
    """Add a game to your watchlist using Steam App ID"""
    await interaction.response.defer()

    # Test if we can get price data for this App ID
    price_data = await monitor.get_game_prices([steam_app_id], region)

    if not price_data or not price_data.get("success"):
        await interaction.followup.send(
            f"Cannot find price data for Steam App ID: `{steam_app_id}`. Please verify the App ID is correct."
        )
        return

    game_data = price_data.get("data", {}).get(steam_app_id)
    if not game_data:
        await interaction.followup.send(f"No game data found for Steam App ID: `{steam_app_id}`.")
        return

    # Use game title from API or provided name
    game_title = game_name if game_name else game_data.get("title", f"Steam Game {steam_app_id}")

    # Add to watchlist
    monitor.add_to_watchlist(interaction.user.id, steam_app_id, game_title, interaction.channel.id, target_price, region)

    target_text = f" (target: {target_price} {game_data.get('prices', {}).get('currency', 'USD')})" if target_price else ""
    await interaction.followup.send(f"Added **{game_title}** (App ID: {steam_app_id}) to your watchlist{target_text}!")

@bot.tree.command(name="unwatch", description="Remove a game from your watchlist")
@app_commands.describe(steam_app_id="The Steam App ID of the game to remove")
async def remove_from_watchlist_command(interaction: discord.Interaction, steam_app_id: str):
    """Remove a game from your watchlist"""
    removed = monitor.remove_from_watchlist(interaction.user.id, steam_app_id)

    if removed:
        await interaction.response.send_message(f"Game with App ID `{steam_app_id}` removed from your watchlist!")
    else:
        await interaction.response.send_message(f"App ID `{steam_app_id}` not found in your watchlist.")

@bot.tree.command(name="watchlist", description="Show your current watchlist")
@app_commands.describe(region="Region code for price display (e.g., 'us', 'eu', 'uk')")
async def show_watchlist_command(interaction: discord.Interaction, region: str = "us"):
    """Show your current watchlist"""
    await interaction.response.defer()

    watchlist = monitor.get_watchlist(interaction.user.id)

    if not watchlist:
        await interaction.followup.send(
            "Your watchlist is empty. Use `/watch <steam_app_id> [target_price] [region] [game_name]` to add games!"
        )
        return

    embed = discord.Embed(title="Your Watchlist", color=0xff9900)

    # Get all Steam App IDs from watchlist
    steam_app_ids = list(watchlist.keys())

    # Get current prices for all watched games in one API call
    price_data = await monitor.get_game_prices(steam_app_ids, region)

    for steam_app_id, game_info in watchlist.items():
        game_title = game_info['game_title']
        target_price = game_info['target_price']

        # Get current price data from API response
        current_price_text = "No current price data"

        if price_data.get("success") and price_data.get("data", {}).get(steam_app_id):
            game_data = price_data["data"][steam_app_id]
            prices = game_data.get("prices", {})
            currency = prices.get("currency", "USD")

            # Use the lower of retail or keyshop prices for current best
            current_retail = prices.get("currentRetail")
            current_keyshops = prices.get("currentKeyshops")

            best_price = None
            price_type = ""

            if current_retail and current_keyshops:
                if float(current_retail) <= float(current_keyshops):
                    best_price = current_retail
                    price_type = " (Retail)"
                else:
                    best_price = current_keyshops
                    price_type = " (Keyshop)"
            elif current_retail:
                best_price = current_retail
                price_type = " (Retail)"
            elif current_keyshops:
                best_price = current_keyshops
                price_type = " (Keyshop)"

            if best_price:
                current_price_text = f"Current best: {best_price} {currency}{price_type}"

        field_value = f"Steam App ID: `{steam_app_id}`\n{current_price_text}"
        if target_price:
            field_value += f"\nTarget: {target_price}"

        embed.add_field(
            name=game_title,
            value=field_value,
            inline=False
        )

    embed.set_footer(text=f"Region: {region.upper()}")
    await interaction.followup.send(embed=embed)

@tasks.loop(minutes=30)
async def price_check_task():
    """Background task to check prices and send notifications"""
    logger.info("Running price check task...")
    
    watched_games = monitor.get_all_watched_games()
    
    if not watched_games:
        return
    
    all_steam_app_ids = list(watched_games.keys())
    
    try:
        price_data = await monitor.get_game_prices(all_steam_app_ids, region="us", use_cache=False)
        
        if not price_data.get("success"):
            logger.error("Failed to get price data during monitoring")
            return
        
        for steam_app_id, watchers in watched_games.items():
            game_data = price_data.get("data", {}).get(steam_app_id)
            
            if not game_data:
                continue
                
            prices = game_data.get("prices", {})
            currency = prices.get("currency", "USD")
            
            current_retail = prices.get("currentRetail")
            current_keyshops = prices.get("currentKeyshops")
            
            best_price = None
            store_type = ""
            
            if current_retail and current_keyshops:
                if float(current_retail) <= float(current_keyshops):
                    best_price = float(current_retail)
                    store_type = "Retail stores"
                else:
                    best_price = float(current_keyshops)
                    store_type = "Key shops"
            elif current_retail:
                best_price = float(current_retail)
                store_type = "Retail stores"
            elif current_keyshops:
                best_price = float(current_keyshops)
                store_type = "Key shops"
            
            if best_price is None:
                continue
            
            for watcher in watchers:
                target_price = watcher['target_price']
                
                if target_price and best_price <= target_price:
                    channel = bot.get_channel(watcher['channel_id'])
                    if channel:
                        user = bot.get_user(watcher['user_id'])
                        embed = discord.Embed(
                            title="🚨 Price Alert!",
                            description=f"**{watcher['game_title']}** has reached your target price!",
                            color=0xff0000
                        )
                        embed.add_field(
                            name="Current Best Price",
                            value=f"{best_price} {currency} ({store_type})",
                            inline=True
                        )
                        embed.add_field(
                            name="Your Target",
                            value=f"{target_price} {currency}",
                            inline=True
                        )
                        embed.add_field(
                            name="Steam App ID",
                            value=f"`{steam_app_id}`",
                            inline=True
                        )
                        
                        game_url = game_data.get("url")
                        if game_url:
                            embed.add_field(
                                name="View Deals",
                                value=f"[gg.deals page]({game_url})",
                                inline=False
                            )
                        
                        try:
                            await channel.send(f"{user.mention}", embed=embed)
                            logger.info(f"Sent price alert for {watcher['game_title']} to {user.name}")
                        except Exception as e:
                            logger.error(f"Failed to send alert: {e}")
        
        logger.info(f"Price check completed for {len(all_steam_app_ids)} games")
        
    except Exception as e:
        logger.error(f"Error during price monitoring: {e}")
            
# Error handling for slash commands
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandInvokeError):
        logger.error(f"Command error: {error}")
        await interaction.response.send_message("An error occurred while processing the command.", ephemeral=True)
    else:
        logger.error(f"Unexpected error: {error}")
        await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)

# Cleanup on shutdown
@bot.event
async def on_disconnect():
    if monitor.session and not monitor.session.closed:
        await monitor.session.close()

if __name__ == "__main__":
    # Validate required configuration
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN environment variable not set")
        logger.error("Please set BOT_TOKEN in your environment or create a .env file")
        exit(1)

    if not GGDEALS_API_KEY:
        logger.error("❌ GGDEALS_API_KEY environment variable not set")
        logger.error("Please set GGDEALS_API_KEY in your environment or create a .env file")
        exit(1)

    logger.info("🚀 Starting Discord Game Price Monitor Bot...")
    bot.run(BOT_TOKEN)