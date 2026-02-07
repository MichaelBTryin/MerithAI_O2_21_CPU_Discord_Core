"""
Discord Bot Client
Handles Discord commands, events, and integrations
"""

import discord
from discord.ext import commands
import discord.app_commands
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MerithBot(commands.Cog):
    """Main bot commands and event handlers"""

    def __init__(
        self,
        bot: commands.Bot,
        config: dict,
        llm_client,
        stt_engine,
        tts_engine,
        voice_handler
    ):
        """Initialize bot cog

        Args:
            bot: Discord bot instance
            config: Configuration dict
            llm_client: LLM client
            stt_engine: STT engine
            tts_engine: TTS engine
            voice_handler: Voice handler
        """
        self.bot = bot
        self.config = config
        self.llm_client = llm_client
        self.stt_engine = stt_engine
        self.tts_engine = tts_engine
        self.voice_handler = voice_handler

        self.discord_config = config.get('discord', {})
        # Use strict whitelist (fallback to old allowed_channels for compatibility)
        self.whitelist_channels = self.discord_config.get('whitelist_channels', self.discord_config.get('allowed_channels', []))
        self.log_channel_id = self.discord_config.get('log_channel_id')
        self.guild_id = self.discord_config.get('guild_id')

        # Track active voice loops
        self.voice_loops: dict = {}
        self.log_channel: Optional[discord.TextChannel] = None

        logger.info(f"✓ Bot cog initialized")
        logger.info(f"  Guild ID: {self.guild_id}")
        logger.info(f"  Whitelist channels: {self.whitelist_channels}")
        logger.info(f"  Whitelist type check: {[f'{c} (type: {type(c).__name__})' for c in self.whitelist_channels]}")
        logger.info(f"  Log channel ID: {self.log_channel_id}")

        # DEBUG: Print message handler check code
        if not self.whitelist_channels:
            logger.warning("⚠️  WHITELIST IS EMPTY! Bot will NOT respond to ANY messages!")
        else:
            logger.info(f"✓ Text chat will respond in {len(self.whitelist_channels)} whitelisted channel(s)")

    @commands.Cog.listener()
    async def on_ready(self):
        """Called when bot connects to Discord"""
        logger.info(f"\n{'='*60}")
        logger.info(f"✓ Bot logged in as {self.bot.user}")
        logger.info(f"{'='*60}\n")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle incoming messages - respond to mentions or replies"""
        # Ignore bot messages
        if message.author.bot:
            return

        # STRICT WHITELIST - only respond in whitelisted channels
        logger.debug(f"Message in channel {message.channel.id} (type: {type(message.channel.id).__name__}). Whitelist: {self.whitelist_channels}")
        if message.channel.id not in self.whitelist_channels:
            logger.debug(f"Channel {message.channel.id} not in whitelist {self.whitelist_channels} - ignoring")
            return

        # Check for bot mentions or replies
        is_mention = self.bot.user in message.mentions
        is_reply = message.reference and await self._is_reply_to_bot(message)

        if not (is_mention or is_reply):
            return

        # Extract and clean message text
        text = message.content
        for mention in message.mentions:
            text = text.replace(mention.mention, '').replace(f"<@{mention.id}>", '')
        text = text.strip()

        if not text:
            return

        # Show typing indicator while processing
        async with message.channel.typing():
            try:
                # Get LLM response
                response = await self.llm_client.generate_response_async(
                    user_message=text,
                    system_prompt=self.llm_client.system_prompt
                )

                # Send response (Discord 2000 char limit)
                if response and not response.startswith("["):
                    for chunk in self._chunk_text(response, 1950):
                        await message.reply(chunk, mention_author=False)
                else:
                    await message.reply("Sorry, I couldn't generate a response.", mention_author=False)

            except Exception as e:
                logger.error(f"Error responding to message: {e}")
                await message.reply("An error occurred.", mention_author=False)

    async def _is_reply_to_bot(self, message: discord.Message) -> bool:
        """Check if message is a reply to the bot"""
        try:
            if not message.reference:
                return False
            replied_to = await message.channel.fetch_message(message.reference.message_id)
            return replied_to.author.id == self.bot.user.id
        except:
            return False

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 1950):
        """Split text into Discord message chunks"""
        for i in range(0, len(text), chunk_size):
            yield text[i:i + chunk_size]

    async def _get_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Get log channel for voice chat logging"""
        if not self.log_channel_id:
            return None
        try:
            return guild.get_channel(self.log_channel_id)
        except Exception as e:
            logger.warning(f"Could not get log channel: {e}")
            return None

    async def log_voice_interaction(self, guild: discord.Guild, user_text: str, bot_response: str):
        """Log voice chat interaction (STT and LLM response)"""
        log_channel = await self._get_log_channel(guild)
        if not log_channel:
            return

        try:
            # Format log message
            log_msg = f"""🎤 **Voice Chat Log**
**User:** {user_text}
**Bot:** {bot_response}"""
            await log_channel.send(log_msg)
            logger.debug(f"Logged voice interaction to {log_channel.name}")
        except Exception as e:
            logger.warning(f"Failed to log voice interaction: {e}")

    async def post_voice_message(self, guild: discord.Guild, audio_file_path: str):
        """Post TTS audio as voice message to log channel"""
        log_channel = await self._get_log_channel(guild)
        if not log_channel or not audio_file_path:
            return

        try:
            import os
            if not os.path.exists(audio_file_path):
                logger.warning(f"Audio file not found for voice message: {audio_file_path}")
                return

            # Send as file attachment (simpler than Discord voice message format)
            with open(audio_file_path, 'rb') as f:
                file = discord.File(f, filename="voice-response.wav")
                await log_channel.send("🔊 **Voice Response:**", file=file)
                logger.debug(f"Posted voice message to {log_channel.name}")
        except Exception as e:
            logger.warning(f"Failed to post voice message: {e}")

    # ==================== VOICE COMMANDS ====================

    async def join_voice(self, interaction: discord.Interaction):
        """Join user's current voice channel

        Usage: /join_mai
        Note: Voice recording requires additional setup. Use text chat instead!
        """
        if not interaction.user.voice:
            await interaction.response.send_message("❌ You must be in a voice channel to use this command")
            return

        try:
            # Join voice channel
            success = await self.voice_handler.join_voice_channel(interaction.user)

            if success:
                await interaction.response.send_message(
                    f"✓ Joined voice channel: {interaction.user.voice.channel.name}\n"
                    f"🎤 Recording from microphone...\n"
                    f"💬 Or text chat: `@Merith hello` to chat\n"
                    f"Type `/leave_mai` to disconnect"
                )

                # Start voice loop if not already running
                guild_id = interaction.guild.id
                if guild_id not in self.voice_loops:
                    logger.info(f"Bot joined voice channel in {interaction.guild.name}")
                    log_channel = await self._get_log_channel(interaction.guild)
                    task = asyncio.create_task(self.voice_handler.full_voice_loop(interaction.guild, log_channel=log_channel))
                    self.voice_loops[guild_id] = task
            else:
                await interaction.response.send_message("❌ Failed to join voice channel")

        except Exception as e:
            logger.error(f"Error joining voice: {e}")
            await interaction.response.send_message(f"❌ Error: {str(e)}")

    async def leave_voice(self, interaction: discord.Interaction):
        """Leave current voice channel

        Usage: /leave_mai
        """
        try:
            # Cancel voice loop if running
            guild_id = interaction.guild.id
            if guild_id in self.voice_loops:
                self.voice_loops[guild_id].cancel()
                del self.voice_loops[guild_id]
                logger.info(f"Stopped voice loop for {interaction.guild.name}")

            # Leave voice channel
            success = await self.voice_handler.leave_voice_channel(interaction.guild)

            if success:
                await interaction.response.send_message("✓ Left voice channel")
            else:
                await interaction.response.send_message("❌ Not currently in a voice channel")

        except Exception as e:
            logger.error(f"Error leaving voice: {e}")
            await interaction.response.send_message(f"❌ Error: {str(e)}")

    @commands.command(name='status')
    async def status_command(self, ctx: commands.Context):
        """Show bot status and configuration

        Usage: /status
        """
        try:
            # Get status info
            voice_status = await self.voice_handler.get_voice_channel_status(ctx.guild)
            stt_info = self.stt_engine.get_engine_info()
            tts_info = self.tts_engine.get_engine_info()

            # Build status message
            status_msg = f"""
```
=== Merith AI Bot Status ===

Discord:
  Guild: {ctx.guild.name}
  Voice Connected: {voice_status['connected']}

LLM:
  Model: {self.llm_client.model_name}
  API: {self.llm_client.api_url}

Speech-to-Text:
  Engine: {stt_info['engine']}
  Language: {stt_info['language']}
  Status: {'✓ Ready' if stt_info['initialized'] else '✗ Not initialized'}

Text-to-Speech:
  Engine: {tts_info['engine']}
  Speed: {tts_info['speed']}
  Status: {'✓ Ready' if tts_info['initialized'] else '✗ Not initialized'}

Voice Chat:
  Enabled: {voice_status['enabled']}
```
            """

            await ctx.send(status_msg)

        except Exception as e:
            logger.error(f"Error getting status: {e}")
            await ctx.send(f"❌ Error: {str(e)}")

    @commands.command(name='help')
    async def show_help(self, ctx: commands.Context):
        """Show available commands

        Usage: /help
        """
        help_msg = """
```
=== Merith AI Bot Commands ===

Text Chat (READY):
  @Merith <message>    - Chat with the bot
  Reply to bot message - Continue conversation

Voice Commands (BETA):
  /join_mai   - Bot joins your voice channel
  /leave_mai  - Bot leaves voice channel
  /status     - Show bot status and info

General:
  /help      - Show this message

Examples:
  @Merith Hello, how are you?
  /join_mai
  /status

Note: Voice recording not yet implemented.
Use text chat by mentioning the bot!
```
        """
        await ctx.send(help_msg)


def create_bot(
    config: dict,
    llm_client,
    stt_engine,
    tts_engine,
    voice_handler
) -> commands.Bot:
    """Create and configure Discord bot

    Args:
        config: Configuration dict
        llm_client: LLM client instance
        stt_engine: STT engine instance
        tts_engine: TTS engine instance
        voice_handler: Voice handler instance

    Returns:
        Configured Discord bot
    """
    # Create bot with minimal intents
    intents = discord.Intents.default()
    intents.message_content = True  # Required to read message content
    intents.voice_states = True      # Required for voice state tracking

    bot = commands.Bot(
        command_prefix='/',
        intents=intents,
        help_command=None  # Disable default help to use custom /help command
    )

    # Create cog instance
    cog = MerithBot(bot, config, llm_client, stt_engine, tts_engine, voice_handler)
    bot.merith_cog = cog

    @bot.event
    async def on_ready():
        """Bot ready event"""
        logger.info(f"\n{'='*60}")
        logger.info(f"✓ Bot connected to Discord")
        logger.info(f"  Username: {bot.user}")
        logger.info(f"  ID: {bot.user.id}")
        logger.info(f"{'='*60}\n")

        # Sync app commands (slash commands)
        try:
            synced = await bot.tree.sync()
            logger.info(f"✓ Synced {len(synced)} app command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def setup_hook():
        """Setup hook called before bot starts - add cogs here"""
        await bot.add_cog(cog)
        logger.debug("✓ Added MerithBot cog")

    bot.setup_hook = setup_hook

    @bot.event
    async def on_message(message: discord.Message):
        """Global message handler - ensures cog listeners are called"""
        # Always process commands and dispatch to cogs
        await bot.process_commands(message)

    # Add app commands (slash commands) to the bot's tree
    @bot.tree.command(name='join_mai', description='Bot joins your voice channel')
    async def join_mai(interaction: discord.Interaction):
        """Join user's voice channel"""
        await bot.merith_cog.join_voice(interaction)

    @bot.tree.command(name='leave_mai', description='Bot leaves the voice channel')
    async def leave_mai(interaction: discord.Interaction):
        """Leave voice channel"""
        await bot.merith_cog.leave_voice(interaction)

    return bot
