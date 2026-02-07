"""
LM Studio API Client for CPU-Optimized LLM Inference
Communicates with LM Studio using OpenAI-compatible API
Supports both local and remote endpoints
"""

import requests
import asyncio
import aiohttp
from typing import Optional, Generator
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class LMStudioClient:
    """Client for Ollama/LM Studio API (OpenAI-compatible endpoint)"""

    def __init__(self, config: dict):
        """Initialize LLM client (Ollama or LM Studio)

        Args:
            config: Configuration dict with llm settings
        """
        self.config = config.get('llm', {})
        self.api_url = self.config.get('api_url', 'http://localhost:11434/v1')
        self.model_name = self.config.get('model_name', 'gemma:3-1b-it-abliterated')
        self.temperature = self.config.get('temperature', 0.6)
        self.max_tokens = self.config.get('max_tokens', 100)
        self.system_prompt = self._load_system_prompt()
        self.retry_attempts = self.config.get('retry_attempts', 3)
        self.retry_delay = self.config.get('retry_delay_seconds', 1.0)
        self.timeout = self.config.get('timeout_seconds', 30.0)

        # Detect if using Ollama or LM Studio
        self.is_ollama = '11434' in self.api_url

        # Ensure API URL doesn't have trailing slash
        self.api_url = self.api_url.rstrip('/')

        # Test connection on startup
        self._test_connection()

    def _load_system_prompt(self) -> str:
        """Load system prompt from system_prompt.json or config

        Returns:
            System prompt string
        """
        # First check if system_prompt_file is specified
        prompt_file = self.config.get('system_prompt_file')
        if prompt_file:
            try:
                prompt_path = Path(prompt_file)
                if not prompt_path.is_absolute():
                    # Make it relative to the bot.py location
                    prompt_path = Path(__file__).parent.parent / prompt_file

                if prompt_path.exists():
                    with open(prompt_path, 'r', encoding='utf-8') as f:
                        prompt_data = json.load(f)
                        # Extract the summary or create from personality
                        if 'summary' in prompt_data:
                            logger.info(f"✓ Loaded system prompt from {prompt_file}")
                            return prompt_data['summary']
                        elif 'core_personality' in prompt_data:
                            # Build prompt from core personality
                            summary = prompt_data.get('summary', '')
                            if summary:
                                logger.info(f"✓ Loaded system prompt from {prompt_file}")
                                return summary
                else:
                    logger.warning(f"System prompt file not found: {prompt_path}")
            except Exception as e:
                logger.warning(f"Error loading system prompt file: {e}")

        # Fallback: use inline system_prompt from config or default
        default = 'You are Merith, a helpful AI assistant.'
        system_prompt = self.config.get('system_prompt', default)
        logger.info("Using system prompt from config")
        return system_prompt

    def _test_connection(self):
        """Test if Ollama/LM Studio is accessible"""
        try:
            if self.is_ollama:
                # Test Ollama connection
                response = requests.get(
                    "http://localhost:11434/api/tags",
                    timeout=5.0
                )
            else:
                # Test LM Studio connection
                response = requests.get(
                    f"{self.api_url}/models",
                    timeout=5.0
                )

            if response.status_code == 200:
                backend = "Ollama" if self.is_ollama else "LM Studio"
                logger.info(f"✓ Connected to {backend} at {self.api_url}")

                if self.is_ollama:
                    models = response.json().get('models', [])
                else:
                    models = response.json().get('data', [])

                if models:
                    logger.info(f"  Available models: {len(models)}")
                    model_names = []
                    for model in models[:3]:  # Show first 3
                        name = model.get('name') if self.is_ollama else model.get('id', 'Unknown')
                        model_names.append(name)
                    logger.info(f"  Examples: {', '.join(model_names)}")
                return True
            else:
                logger.warning(f"⚠ API returned status {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            backend = "Ollama" if self.is_ollama else "LM Studio"
            logger.error(f"✗ Cannot connect to {backend} at {self.api_url}")
            logger.error("  Make sure Ollama/LM Studio is running and accessible")
            return False
        except Exception as e:
            logger.error(f"✗ Connection test failed: {e}")
            return False

    def generate_response(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        voice_mode: bool = False,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate LLM response (synchronous)

        Args:
            user_message: User's message
            system_prompt: Override system prompt
            voice_mode: If True, use shorter context window and fewer tokens
            max_tokens: Override max tokens

        Returns:
            LLM response text
        """
        system = system_prompt or self.system_prompt
        tokens = max_tokens or self.max_tokens

        if voice_mode:
            # Voice chat: shorter, punchier responses
            tokens = min(tokens, 100)

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message}
        ]

        for attempt in range(self.retry_attempts):
            try:
                response = requests.post(
                    f"{self.api_url}/chat/completions",
                    json={
                        "model": self.model_name,
                        "messages": messages,
                        "temperature": self.temperature,
                        "max_tokens": tokens,
                        "stream": False
                    },
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    data = response.json()
                    return data['choices'][0]['message']['content'].strip()
                else:
                    logger.warning(f"API error (attempt {attempt + 1}): {response.status_code}")
                    if attempt < self.retry_attempts - 1:
                        asyncio.sleep(self.retry_delay)
                    continue

            except requests.exceptions.Timeout:
                logger.warning(f"API timeout (attempt {attempt + 1}/{self.retry_attempts})")
                if attempt < self.retry_attempts - 1:
                    asyncio.sleep(self.retry_delay)
            except requests.exceptions.ConnectionError:
                logger.error(f"Cannot connect to API (attempt {attempt + 1}/{self.retry_attempts})")
                if attempt < self.retry_attempts - 1:
                    asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"LLM generation error: {e}")
                return "[Error generating response]"

        return "[API unavailable - max retries exceeded]"

    def generate_streaming(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        voice_mode: bool = False,
        max_tokens: Optional[int] = None
    ) -> Generator[str, None, None]:
        """Generate streaming LLM response

        Args:
            user_message: User's message
            system_prompt: Override system prompt
            voice_mode: If True, use shorter context window
            max_tokens: Override max tokens

        Yields:
            Token chunks from LLM
        """
        system = system_prompt or self.system_prompt
        tokens = max_tokens or self.max_tokens

        if voice_mode:
            tokens = min(tokens, 100)

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message}
        ]

        try:
            response = requests.post(
                f"{self.api_url}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": tokens,
                    "stream": True
                },
                timeout=self.timeout,
                stream=True
            )

            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data_str = line[6:]
                            if data_str == '[DONE]':
                                break
                            try:
                                import json
                                data = json.loads(data_str)
                                delta = data['choices'][0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    yield content
                            except:
                                pass
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield "[Error in streaming]"

    async def generate_response_async(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        voice_mode: bool = False,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate LLM response (asynchronous)

        Args:
            user_message: User's message
            system_prompt: Override system prompt
            voice_mode: If True, use shorter context window
            max_tokens: Override max tokens

        Returns:
            LLM response text
        """
        system = system_prompt or self.system_prompt
        tokens = max_tokens or self.max_tokens

        if voice_mode:
            tokens = min(tokens, 100)

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message}
        ]

        for attempt in range(self.retry_attempts):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.api_url}/chat/completions",
                        json={
                            "model": self.model_name,
                            "messages": messages,
                            "temperature": self.temperature,
                            "max_tokens": tokens,
                            "stream": False
                        },
                        timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data['choices'][0]['message']['content'].strip()
                        else:
                            logger.warning(f"API error (attempt {attempt + 1}): {response.status}")
                            if attempt < self.retry_attempts - 1:
                                await asyncio.sleep(self.retry_delay)

            except asyncio.TimeoutError:
                logger.warning(f"API timeout (attempt {attempt + 1}/{self.retry_attempts})")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Async API error: {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)

        return "[LM Studio unavailable]"

    def get_model_info(self) -> Optional[dict]:
        """Get information about current model

        Returns:
            Model info or None if error
        """
        try:
            response = requests.get(
                f"{self.api_url}/models",
                timeout=5.0
            )
            if response.status_code == 200:
                models = response.json().get('data', [])
                for model in models:
                    if model.get('id') == self.model_name:
                        return model
            return None
        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return None

    def health_check(self) -> bool:
        """Check if LM Studio is healthy

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = requests.get(
                f"{self.api_url}/models",
                timeout=5.0
            )
            return response.status_code == 200
        except:
            return False
