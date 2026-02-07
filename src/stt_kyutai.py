"""
Speech-to-Text Module
Primary: Kyutai STT (when available)
Fallback: Whisper tiny.en (CPU-optimized via faster-whisper)
"""

import logging
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)


class STTEngine:
    """Speech-to-Text engine with fallback support"""

    def __init__(self, config: dict):
        """Initialize STT engine

        Args:
            config: Configuration dict
        """
        self.config = config.get('stt', {})
        self.engine = self.config.get('engine', 'kyutai')
        self.fallback_engine = self.config.get('fallback_engine', 'whisper')
        self.language = self.config.get('language', 'en')

        self.stt = None
        self._initialize_stt()

    def _initialize_stt(self):
        """Initialize speech-to-text engine"""
        # Skip Kyutai (not available yet) - go straight to Whisper
        if self._try_init_whisper():
            return

        logger.error("✗ No STT engine could be initialized")
        logger.error("  Install faster-whisper")

    def _try_init_kyutai(self) -> bool:
        """Try to initialize Kyutai STT

        Returns:
            True if successful
        """
        try:
            # Placeholder for Kyutai STT integration
            # When Kyutai releases their package, it will be imported here
            logger.info("ℹ Kyutai STT not yet available")
            logger.info("  Kyutai will be released soon at https://kyutai.org/stt")
            return False

        except ImportError:
            logger.debug("Kyutai STT not installed")
            return False
        except Exception as e:
            logger.warning(f"Failed to initialize Kyutai STT: {e}")
            return False

    def _try_init_whisper(self) -> bool:
        """Try to initialize Whisper (via faster-whisper)

        Returns:
            True if successful
        """
        try:
            from faster_whisper import WhisperModel

            model_name = self.config.get('whisper_model', 'tiny.en')

            # Use CPU and int8 quantization for speed
            self.stt = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",  # 2-3x faster with int8 quantization
                num_workers=1
            )

            logger.info(f"✓ Whisper STT initialized ({model_name})")
            logger.info(f"  Using CPU with int8 quantization")
            self.engine = 'whisper'
            return True

        except ImportError:
            logger.error("faster-whisper not installed")
            logger.error("  Install with: pip install faster-whisper")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Whisper: {e}")
            return False

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe audio to text

        Args:
            audio_data: Audio samples as numpy array
            sample_rate: Sample rate of audio (default 16000)

        Returns:
            Transcribed text
        """
        if self.stt is None:
            logger.error("STT engine not initialized")
            return "[STT not available]"

        try:
            if self.engine == 'whisper':
                return self._transcribe_whisper(audio_data, sample_rate)
            elif self.engine == 'kyutai':
                return self._transcribe_kyutai(audio_data, sample_rate)
            else:
                return "[Unknown STT engine]"

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return "[Transcription failed]"

    def _transcribe_whisper(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe using Whisper

        Args:
            audio_data: Audio samples
            sample_rate: Sample rate

        Returns:
            Transcribed text
        """
        try:
            # Normalize audio to [-1, 1]
            if audio_data.dtype == np.int16:
                audio_data = audio_data.astype(np.float32) / 32768.0
            elif audio_data.max() > 1.0:
                audio_data = audio_data / (2 ** 15)

            # Resample to 16kHz if needed
            if sample_rate != 16000:
                import librosa
                audio_data = librosa.resample(audio_data, orig_sr=sample_rate, target_sr=16000)

            # Convert to float32 wav format that faster-whisper expects
            audio_data = audio_data.astype(np.float32)

            # Transcribe
            segments, info = self.stt.transcribe(
                audio_data,
                language=self.language if self.language != 'auto' else None,
                beam_size=5,
                best_of=5
            )

            # Combine segments into single text
            text = " ".join(segment.text for segment in segments).strip()

            if text:
                logger.debug(f"Transcribed: '{text}'")
            else:
                logger.debug("No speech detected")

            return text if text else "[No speech detected]"

        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return "[Transcription error]"

    def _transcribe_kyutai(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe using Kyutai (placeholder)

        Args:
            audio_data: Audio samples
            sample_rate: Sample rate

        Returns:
            Transcribed text
        """
        logger.warning("Kyutai STT not yet implemented")
        return "[Kyutai STT not available]"

    def get_engine_info(self) -> dict:
        """Get information about current engine

        Returns:
            Dictionary with engine info
        """
        return {
            "engine": self.engine,
            "fallback": self.fallback_engine,
            "language": self.language,
            "initialized": self.stt is not None
        }
