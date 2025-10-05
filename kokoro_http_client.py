#!/usr/bin/env python3
"""
KokoroHTTPClient - Lightweight HTTP client for Kokoro TTS
Replaces direct model loading with HTTP calls to persistent model worker
Eliminates per-call model loading delays
"""

import os
import logging
import requests
import time
import html
from config import KOKORO_CONFIG

logger = logging.getLogger(__name__)

class KokoroHTTPClient:
    """HTTP-based Kokoro TTS Client - Zero model loading overhead"""

    def __init__(self, worker_url="http://127.0.0.1:8777"):
        """Initialize HTTP client - no model loading"""
        self.worker_url = worker_url
        self.timeout = 60  # HTTP timeout for synthesis requests
        self.voice_name = KOKORO_CONFIG.get("voice", "af_heart")

        # Voice type mapping for different contexts
        self.voice_mapping = {
            "greeting": "af_heart",      # Most human-like for greetings
            "empathetic": "af_sarah",    # Warm, understanding tone
            "helping": "af_bella",       # Clear, helpful tone
            "technical": "af_jessica",   # Professional, precise
            "default": "af_heart",       # Standard voice
            "professional": "af_nova"    # Business-appropriate
        }

        logger.info(f"KokoroHTTPClient initialized - worker: {worker_url}")

        # Test connection to worker
        self._test_connection()

    def _test_connection(self):
        """Test connection to model worker service"""
        try:
            response = requests.get(f"{self.worker_url}/health", timeout=5)
            if response.status_code == 200:
                health = response.json()
                if health.get("models_loaded"):
                    logger.info("✅ Model worker connection verified - ready for TTS")
                else:
                    logger.warning("⚠️ Model worker connected but models not loaded")
            else:
                logger.warning(f"Model worker health check failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Cannot connect to model worker: {e}")
            logger.error("Make sure model worker service is running:")
            logger.error("sudo systemctl start netovo-model-worker")

    def _prepare_text(self, text):
        """Prepare text for synthesis with pronunciation corrections"""
        # HTML decode first
        text = html.unescape(text)

        # Apply pronunciation corrections (from original client)
        text = text.replace("NETOVO", "NET-OH-VOH")
        text = text.replace("Netovo", "Net-oh-voh")
        text = text.replace("netovo", "net-oh-voh")

        # Clean up text
        text = text.strip()

        return text

    def synthesize(self, text, voice_type="default"):
        """
        Synthesize speech from text via HTTP API

        Args:
            text (str): Text to synthesize
            voice_type (str): Voice type (greeting, empathetic, helping, technical, default)

        Returns:
            str: Path to generated audio file or None if failed
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for synthesis")
            return None

        try:
            # Prepare text
            cleaned_text = self._prepare_text(text)
            voice = self.voice_mapping.get(voice_type, self.voice_name)

            start_time = time.time()
            logger.info(f"TTS HTTP request: '{cleaned_text[:50]}...' voice={voice}")

            # Make HTTP request to model worker
            response = requests.post(
                f"{self.worker_url}/synthesize",
                json={
                    "text": cleaned_text,
                    "voice": voice
                },
                timeout=self.timeout
            )

            duration = time.time() - start_time

            if response.status_code == 200:
                result = response.json()
                audio_path = result.get("path")
                synthesis_duration = result.get("duration", 0.0)

                if audio_path and os.path.exists(audio_path):
                    file_size = os.path.getsize(audio_path)
                    logger.info(f"TTS HTTP success ({duration:.2f}s): {audio_path} ({file_size} bytes)")
                    return audio_path
                else:
                    logger.error(f"TTS completed but file not found: {audio_path}")
                    return None

            elif response.status_code == 503:
                logger.error("Model worker service unavailable - models not loaded")
                return None

            else:
                logger.error(f"TTS HTTP request failed: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"TTS HTTP request timed out after {self.timeout}s")
            return None

        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to model worker - is it running?")
            logger.error("Start with: sudo systemctl start netovo-model-worker")
            return None

        except Exception as e:
            logger.error(f"TTS HTTP synthesis failed: {e}")
            return None

    def synthesize_to_file(self, text, output_file, voice_type="default"):
        """
        Synthesize speech and save to specific file

        Args:
            text (str): Text to synthesize
            output_file (str): Target file path
            voice_type (str): Voice type

        Returns:
            bool: True if successful, False otherwise
        """
        temp_file = self.synthesize(text, voice_type)

        if not temp_file:
            return False

        try:
            # Move temp file to target location
            os.rename(temp_file, output_file)
            logger.info(f"TTS file moved: {temp_file} -> {output_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to move TTS file: {e}")
            # Cleanup temp file
            try:
                os.unlink(temp_file)
            except:
                pass
            return False

# Create alias class for backward compatibility
class KokoroTTSClient(KokoroHTTPClient):
    """Backward compatibility alias"""
    pass