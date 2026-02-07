"""
Text-to-Speech Module
EMERGENCY FIX: Using edge-tts because Piper is broken
"""

import logging
import tempfile
import os
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class TTSEngine:
    """Text-to-Speech engine using edge-tts (FREE & WORKS)"""

    def __init__(self, config: dict):
        """Initialize TTS engine"""
        self.config = config.get('tts', {})
        self.engine = 'edge-tts'
        self.speed = self.config.get('speed', 1.0)
        self.tts = {'initialized': True}
        logger.info(f"✓ edge-tts TTS initialized (FREE Microsoft TTS)")
        logger.info(f"  Using cloud-based synthesis")

    def warmup(self):
        """Warmup TTS engine"""
        try:
            logger.info("🔥 Warming up TTS engine...")
            test_audio_path = self.synthesize("Hello, this is a test.")

            if test_audio_path:
                logger.info(f"✓ TTS warmup successful!")
                os.remove(test_audio_path)
            else:
                logger.error("✗ TTS warmup FAILED!")

        except Exception as e:
            logger.error(f"✗ TTS warmup failed: {e}")

    def synthesize(self, text: str) -> Optional[str]:
        """Synthesize text to audio using edge-tts"""
        try:
            import asyncio
            import edge_tts
            from pydub import AudioSegment

            logger.info(f"🎤 Synthesizing: '{text[:50]}...' ({len(text)} chars)")

            # Create temp files
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                mp3_path = tmp.name
            wav_path = mp3_path.replace('.mp3', '.wav')

            # Synthesize with edge-tts
            async def do_synthesis():
                communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
                await communicate.save(mp3_path)

            # Run synthesis
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            loop.run_until_complete(do_synthesis())

            # Convert MP3 to WAV for Discord
            audio = AudioSegment.from_mp3(mp3_path)
            audio = audio.set_frame_rate(48000)  # Discord needs 48kHz
            audio.export(wav_path, format="wav")

            # Cleanup MP3
            try:
                os.remove(mp3_path)
            except:
                pass

            # Verify
            if not os.path.exists(wav_path):
                logger.error("Synthesis failed: no output file")
                return None

            size = os.path.getsize(wav_path)
            if size == 0:
                logger.error("Synthesis failed: empty file")
                os.remove(wav_path)
                return None

            logger.info(f"✓ Synthesized: {wav_path} ({size} bytes)")
            return wav_path

        except ImportError as e:
            logger.error(f"Missing library: {e}")
            logger.error("Install: pip install edge-tts pydub")
            return None
        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def synthesize_async(self, text: str) -> Optional[str]:
        """Async wrapper for synthesis"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.synthesize, text)

    def get_engine_info(self) -> dict:
        """Get engine info"""
        return {
            "engine": "edge-tts",
            "voice": "en-US-AriaNeural",
            "speed": self.speed,
            "initialized": True
        }
