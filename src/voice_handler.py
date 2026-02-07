"""
Voice Handler for Discord Voice Channels
Records from Discord voice channel users using discord-ext-voice-recv
"""

import discord
import asyncio
import logging
import numpy as np
from typing import Optional, Dict
import io
import wave
from pathlib import Path
import time
import traceback
import tempfile

# Import voice receiving
try:
    import discord.ext.voice_recv as voice_recv
    VOICE_RECV_AVAILABLE = True
except ImportError:
    VOICE_RECV_AVAILABLE = False
    logger.error("discord-ext-voice-recv not installed!")
    logger.error("Install: pip install discord-ext-voice-recv")

logger = logging.getLogger(__name__)


# AudioSink for capturing Discord voice
class AudioSink(voice_recv.AudioSink):
    """Custom audio sink to collect voice data from Discord users"""

    def __init__(self):
        super().__init__()
        self.audio_data = {}
        self.last_packet_time = time.time()

    def write(self, user, data):
        """Receive audio packet from Discord user"""
        try:
            # user is the Discord member object
            # data is voice_recv.VoiceData with .pcm attribute
            user_id = user.id if hasattr(user, 'id') else user

            if user_id not in self.audio_data:
                self.audio_data[user_id] = io.BytesIO()

            self.audio_data[user_id].write(data.pcm)
            self.last_packet_time = time.time()
        except Exception as e:
            logger.error(f"Error writing audio: {e}")
            import traceback
            traceback.print_exc()

    def cleanup(self):
        """Cleanup audio buffers"""
        for buffer in self.audio_data.values():
            buffer.close()
        self.audio_data.clear()

    def get_audio_data(self, user_id: Optional[int] = None) -> Optional[np.ndarray]:
        """Get collected audio as numpy array"""
        try:
            if user_id and user_id in self.audio_data:
                audio_bytes = self.audio_data[user_id].getvalue()
            else:
                if not self.audio_data:
                    return None
                audio_bytes = list(self.audio_data.values())[0].getvalue()

            if not audio_bytes:
                return None

            # Discord sends 16-bit PCM at 48kHz
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            return audio_array
        except Exception as e:
            logger.error(f"Error getting audio data: {e}")
            import traceback
            traceback.print_exc()
            return None


class VoiceHandler:
    """Handles voice channel connections and voice chat pipeline"""

    def __init__(self, config: dict, llm_client, stt_engine, tts_engine):
        """Initialize voice handler

        Args:
            config: Configuration dict
            llm_client: LLM client instance
            stt_engine: STT engine instance
            tts_engine: TTS engine instance
        """
        self.config = config
        self.llm_client = llm_client
        self.stt_engine = stt_engine
        self.tts_engine = tts_engine

        self.voice_config = config.get('voice', {})
        self.enabled = self.voice_config.get('enabled', True)
        self.silence_timeout = self.voice_config.get('silence_timeout_seconds', 3.0)
        self.max_recording_duration = self.voice_config.get('max_recording_duration_seconds', 15.0)
        self.vad_enabled = self.voice_config.get('vad_enabled', True)

        # Track active voice connections
        self.voice_clients: Dict[int, discord.VoiceClient] = {}
        self.audio_cache_dir = Path(__file__).parent.parent / 'audio_cache'
        self.audio_cache_dir.mkdir(exist_ok=True)

        if self.enabled:
            logger.info(f"✓ Voice Handler initialized")
            logger.info(f"  Silence timeout: {self.silence_timeout}s")
            logger.info(f"  Max recording duration: {self.max_recording_duration}s")
            logger.info(f"  Note: Voice recording in Discord.py requires additional setup")
            logger.info(f"  For now, use text chat: mention the bot to chat")
        else:
            logger.info("ℹ Voice chat disabled")

    async def join_voice_channel(self, member: discord.Member) -> bool:
        """Join the voice channel of a user

        Args:
            member: Discord member to join

        Returns:
            True if successful
        """
        if not member.voice or not member.voice.channel:
            logger.warning(f"User {member.name} is not in a voice channel")
            return False

        channel = member.voice.channel
        guild_id = channel.guild.id

        try:
            # Disconnect from existing channel if connected
            if guild_id in self.voice_clients:
                await self.voice_clients[guild_id].disconnect()

            # Connect to user's channel
            voice_client = await channel.connect()
            self.voice_clients[guild_id] = voice_client

            logger.info(f"✓ Joined voice channel: {channel.name} ({channel.guild.name})")
            return True

        except Exception as e:
            logger.error(f"Failed to join voice channel: {e}")
            return False

    async def leave_voice_channel(self, guild: discord.Guild) -> bool:
        """Leave voice channel in a guild

        Args:
            guild: Discord guild

        Returns:
            True if successful
        """
        guild_id = guild.id

        try:
            if guild_id in self.voice_clients:
                await self.voice_clients[guild_id].disconnect()
                del self.voice_clients[guild_id]
                logger.info(f"✓ Left voice channel in {guild.name}")
                return True
            else:
                logger.warning(f"Not connected to voice in {guild.name}")
                return False

        except Exception as e:
            logger.error(f"Failed to leave voice channel: {e}")
            return False

    async def record_audio_from_channel(
        self,
        guild: discord.Guild,
        sink: AudioSink,
        duration: float = 3.0
    ) -> Optional[Dict]:
        """Wait for audio from Discord voice channel users

        Args:
            guild: Discord guild
            sink: AudioSink collecting audio
            duration: Silence timeout (seconds)

        Returns:
            Dict with {user_id: audio_array, 'username': str} or None
        """
        guild_id = guild.id
        if guild_id not in self.voice_clients:
            logger.error("Not connected to voice channel")
            return None

        try:
            # Wait for silence (no new audio packets)
            start_wait = time.time()
            last_packet_time = sink.last_packet_time

            while time.time() - last_packet_time < duration:
                await asyncio.sleep(0.1)
                if sink.last_packet_time > last_packet_time:
                    last_packet_time = sink.last_packet_time

                # Timeout after 30s total
                if time.time() - start_wait > 30:
                    return None

            # Get audio data from sink
            if not sink.audio_data:
                return None

            # Get first user's audio and username
            user_id = list(sink.audio_data.keys())[0]
            audio_array = sink.get_audio_data(user_id)

            if audio_array is None:
                return None

            # Get username from voice client
            voice_client = self.voice_clients[guild_id]
            username = "Unknown User"
            try:
                for member in voice_client.channel.members:
                    if member.id == user_id:
                        username = member.name
                        break
            except:
                pass

            # Clear sink for next recording
            sink.cleanup()
            sink.audio_data = {}

            logger.info(f"✓ Recorded audio from {username} ({len(audio_array)/48000:.2f}s)")

            return {
                'audio': audio_array,
                'user_id': user_id,
                'username': username
            }

        except Exception as e:
            logger.error(f"Voice recording error: {e}")
            traceback.print_exc()
            return None

    async def process_voice_message(
        self,
        guild: discord.Guild,
        user_message: str,
        log_channel: Optional[discord.TextChannel] = None
    ) -> bool:
        """Process voice message: LLM response -> TTS -> Play

        Args:
            guild: Discord guild
            user_message: Transcribed user message
            log_channel: Text channel to log voice interactions

        Returns:
            True if successful
        """
        guild_id = guild.id

        if guild_id not in self.voice_clients:
            logger.error("Not connected to a voice channel")
            return False

        voice_client = self.voice_clients[guild_id]

        try:
            logger.debug(f"Processing voice message: {user_message[:50]}...")

            # Get LLM response
            response = await self.llm_client.generate_response_async(
                user_message=user_message,
                voice_mode=True,
                max_tokens=100
            )

            if not response or response.startswith("["):
                logger.warning(f"Invalid LLM response: {response}")
                return False

            logger.info(f"LLM Response: {response}")
            logger.info(f"\n{'='*60}")
            logger.info(f"📝 **VOICE CHAT LOG**")
            logger.info(f"👤 User: {user_message}")
            logger.info(f"🤖 Bot: {response}")
            logger.info(f"{'='*60}\n")

            # Synthesize response to audio (returns file path)
            logger.info("🎵 Synthesizing TTS audio...")
            audio_path = await self.tts_engine.synthesize_async(response)

            if not audio_path:
                logger.warning("TTS synthesis failed")
                return False

            import os
            if not os.path.exists(audio_path):
                logger.warning(f"TTS audio file not found: {audio_path}")
                return False

            try:
                # Create audio source using FFmpeg to resample to 48kHz for Discord
                logger.info("🎧 Creating FFmpeg audio source...")
                audio_source = discord.FFmpegPCMAudio(audio_path, options='-af aresample=48000')

                # Post text response to log channel when audio starts playing
                if log_channel:
                    try:
                        logger.info(f"📤 Posting voice transcript to log channel: #{log_channel.name}")
                        await log_channel.send(f"**Merith (Voice):** {response}")
                        logger.info("✓ Voice transcript posted to Discord")
                    except Exception as e:
                        logger.error(f"[Transcript] Failed to post text to log channel: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    logger.warning("[Transcript] No log_channel configured - skipping transcript post")

                # Play audio in voice channel with callback for cleanup
                logger.info("🔊 Playing TTS audio in Discord voice channel...")
                voice_client.play(audio_source, after=lambda e: self._on_playback_done(e, audio_path))

                # Wait for playback to finish
                timeout = 30  # Max 30 seconds
                waited = 0
                while voice_client.is_playing() and waited < timeout:
                    await asyncio.sleep(0.1)
                    waited += 0.1

                logger.info(f"✓ Voice response played ({waited:.1f}s)")
                return True

            except Exception as playback_err:
                logger.error(f"Playback error: {playback_err}")
                # Clean up on playback error
                try:
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                        logger.debug(f"Cleaned up temp audio: {audio_path}")
                except Exception as cleanup_err:
                    logger.debug(f"Could not clean up {audio_path}: {cleanup_err}")
                raise

        except Exception as e:
            logger.error(f"Voice message processing error: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def full_voice_loop(self, guild: discord.Guild, log_channel: Optional[discord.TextChannel] = None):
        """Main voice chat loop - records, transcribes, responds, and plays

        Args:
            guild: Discord guild
            log_channel: Text channel for logging voice interactions
        """
        guild_id = guild.id
        voice_client = self.voice_clients[guild_id]

        logger.info(f"✓ Voice chat loop started in {guild.name}")
        logger.info("🎤 Listening for Discord users in voice channel...")

        # Create audio sink to capture Discord voice
        sink = AudioSink()

        # Start listening to voice channel
        voice_client.listen(sink)
        logger.info("✓ Discord voice receiving active")

        loop = asyncio.get_event_loop()

        try:
            while guild_id in self.voice_clients:
                try:
                    # Wait for audio from Discord users
                    logger.debug("Waiting for speech from Discord users...")
                    audio_result = await self.record_audio_from_channel(guild, sink)

                    if audio_result is None:
                        logger.debug("No audio recorded, continuing...")
                        await asyncio.sleep(0.5)
                        continue

                    audio_data = audio_result['audio']
                    username = audio_result['username']

                    # Transcribe audio in thread pool (non-blocking)
                    logger.debug(f"Transcribing audio from {username}...")
                    user_message = await loop.run_in_executor(
                        None,
                        lambda: self.stt_engine.transcribe(audio_data, sample_rate=48000)
                    )

                    # Filter out noise/silence transcriptions
                    if not user_message or user_message.startswith("["):
                        logger.debug(f"STT failed or no speech: {user_message}")
                        await asyncio.sleep(0.5)
                        continue

                    # Filter out background noise (dots, silence, etc.)
                    if user_message.replace(".", "").replace(" ", "").strip() == "":
                        logger.debug(f"Ignoring noise/silence: {user_message}")
                        await asyncio.sleep(0.5)
                        continue

                    logger.info(f"{username}: {user_message}")

                    # Post user transcript to Discord log channel with username
                    if log_channel:
                        try:
                            await log_channel.send(f"**{username} (Voice):** {user_message}")
                            logger.info("✓ User transcript posted to Discord")
                        except Exception as e:
                            logger.error(f"Failed to post user transcript: {e}")

                    # Process voice message and get response
                    await self.process_voice_message(guild, user_message, log_channel=log_channel)

                    # Yield control to allow other tasks (like text message handlers) to run
                    await asyncio.sleep(0)

                except asyncio.CancelledError:
                    logger.info(f"Voice loop cancelled in {guild.name}")
                    break
                except Exception as e:
                    logger.error(f"Voice loop error: {e}")
                    import traceback
                    traceback.print_exc()
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Fatal voice loop error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Stop listening and cleanup
            try:
                voice_client.stop_listening()
                sink.cleanup()
                logger.info("✓ Stopped Discord voice receiving")
            except:
                pass
            logger.info(f"Voice loop ended in {guild.name}")

    async def get_voice_channel_status(self, guild: discord.Guild) -> dict:
        """Get status of voice connection

        Args:
            guild: Discord guild

        Returns:
            Status dictionary
        """
        guild_id = guild.id
        connected = guild_id in self.voice_clients

        return {
            "connected": connected,
            "guild": guild.name,
            "enabled": self.enabled,
            "stt_engine": self.stt_engine.get_engine_info(),
            "tts_engine": self.tts_engine.get_engine_info()
        }

    def _on_playback_done(self, error, audio_path):
        """Callback when TTS playback finishes - handles cleanup"""
        if error:
            logger.error(f"❌ FFmpeg playback error: {error}")
            logger.error(f"   Error type: {type(error).__name__}")
            logger.error(f"   Audio path: {audio_path}")
            import os
            if audio_path and os.path.exists(audio_path):
                logger.error(f"   File exists: True, size: {os.path.getsize(audio_path)} bytes")
            else:
                logger.error(f"   File exists: False")
        else:
            logger.info("✓ Audio playback completed successfully")

        # Clean up temp file
        try:
            import os
            if audio_path and os.path.exists(audio_path):
                os.unlink(audio_path)
                logger.debug(f"Cleaned up audio file: {audio_path}")
        except Exception as e:
            logger.error(f"Error cleaning up audio file: {e}")

        logger.info("✓ TTS playback cycle complete")
