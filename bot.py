"""
Merith AI Discord Voice Bot
CPU-Optimized for Surface Pro 5
Main entry point
"""

import os
import sys
import json
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv

# Configure logging FIRST before importing other modules
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Import components
from llm_client import LMStudioClient
from stt_kyutai import STTEngine
from tts_kyutai import TTSEngine
from voice_handler import VoiceHandler
from discord_client import create_bot

# Load environment variables
load_dotenv()


def check_lm_studio_running():
    """Check if LM Studio is running on the configured API endpoint"""
    try:
        config = load_config()
        api_url = config.get('llm', {}).get('api_url', 'http://localhost:1234/v1')

        logger.info("Checking if LM Studio is running...")
        response = requests.get(f"{api_url}/models", timeout=5)

        if response.status_code == 200:
            logger.info(f"✓ LM Studio is ready at {api_url}")
            return True
        else:
            logger.error(f"✗ LM Studio returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        api_url = "http://localhost:1234/v1"
        logger.error(f"✗ Cannot connect to LM Studio at {api_url}")
        logger.error("  Make sure LM Studio is running on your machine")
        return False
    except Exception as e:
        logger.error(f"✗ Error checking LM Studio: {e}")
        return False


def load_config(config_path: str = 'config.json') -> dict:
    """Load configuration from JSON file

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary
    """
    config_file = Path(__file__).parent / config_path

    if not config_file.exists():
        logger.error(f"Config file not found: {config_file}")
        logger.error("Copy config.json from repository or create from template")
        sys.exit(1)

    try:
        with open(config_file, 'r') as f:
            config = json.load(f)

        # Substitute environment variables
        def substitute_env(obj):
            if isinstance(obj, dict):
                return {k: substitute_env(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [substitute_env(item) for item in obj]
            elif isinstance(obj, str) and obj.startswith('${') and obj.endswith('}'):
                env_var = obj[2:-1]
                return os.getenv(env_var, obj)
            return obj

        config = substitute_env(config)
        logger.info(f"✓ Configuration loaded from {config_file}")
        return config

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)


def initialize_components(config: dict):
    """Initialize bot components

    Args:
        config: Configuration dictionary

    Returns:
        Tuple of (llm_client, stt_engine, tts_engine, voice_handler)
    """
    logger.info("\n" + "="*60)
    logger.info("Initializing Components")
    logger.info("="*60 + "\n")

    try:
        # Initialize LLM client
        logger.info(">>> Initializing LM Studio client...")
        llm_client = LMStudioClient(config)

        # Initialize STT engine
        logger.info("\n>>> Initializing Speech-to-Text engine...")
        stt_engine = STTEngine(config)

        # Initialize TTS engine
        logger.info("\n>>> Initializing Text-to-Speech engine...")
        tts_engine = TTSEngine(config)

        # Warmup TTS engine (avoid startup delays on first synthesis)
        logger.info("\n>>> Warming up TTS engine...")
        tts_engine.warmup()

        # Initialize voice handler
        logger.info("\n>>> Initializing Voice Handler...")
        voice_handler = VoiceHandler(config, llm_client, stt_engine, tts_engine)

        logger.info("\n" + "="*60)
        logger.info("✓ All components initialized successfully")
        logger.info("="*60 + "\n")

        return llm_client, stt_engine, tts_engine, voice_handler

    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        sys.exit(1)


def run_bot(config: dict, llm_client, stt_engine, tts_engine, voice_handler):
    """Run the Discord bot

    Args:
        config: Configuration dictionary
        llm_client: LLM client instance
        stt_engine: STT engine instance
        tts_engine: TTS engine instance
        voice_handler: Voice handler instance
    """
    try:
        # Get Discord token
        token = config.get('discord', {}).get('token')

        if not token or token.startswith('${'):
            logger.error("Discord token not configured!")
            logger.error("Set DISCORD_TOKEN environment variable or in config.json")
            logger.error("See .env.example for setup instructions")
            sys.exit(1)

        # Create bot
        logger.info("Creating Discord bot...")
        bot = create_bot(config, llm_client, stt_engine, tts_engine, voice_handler)

        # Run bot
        logger.info("\nStarting bot...")
        logger.info("Bot is now running! Use /help for commands.")
        logger.info("Press Ctrl+C to stop.\n")

        # Run with graceful shutdown
        import asyncio
        try:
            asyncio.run(bot.start(token))
        except KeyboardInterrupt:
            logger.info("\n🛑 Shutting down gracefully...")
            asyncio.run(bot.close())
            logger.info("✓ Bot stopped by user")

    except KeyboardInterrupt:
        logger.info("\n✓ Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}")
        sys.exit(1)


def main():
    """Main entry point"""
    try:
        logger.info("\n" + "="*60)
        logger.info("Merith AI Discord Voice Bot")
        logger.info("CPU-Optimized for Surface Pro 5")
        logger.info("="*60 + "\n")

        # Check if LM Studio is running
        if not check_lm_studio_running():
            logger.error("Cannot start bot without LM Studio running!")
            sys.exit(1)

        # Load configuration
        config = load_config()

        # Initialize components
        llm_client, stt_engine, tts_engine, voice_handler = initialize_components(config)

        # Run bot
        run_bot(config, llm_client, stt_engine, tts_engine, voice_handler)

    except KeyboardInterrupt:
        logger.info("\n✓ Graceful shutdown")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
