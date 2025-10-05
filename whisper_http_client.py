#!/usr/bin/env python3
"""
WhisperHTTPClient - Lightweight HTTP client for Whisper ASR
Replaces direct model loading with HTTP calls to persistent model worker
Eliminates per-call model loading delays
"""

import os
import logging
import requests
import time
from config import WHISPER_CONFIG

logger = logging.getLogger(__name__)

class WhisperHTTPClient:
    """HTTP-based Whisper ASR Client - Zero model loading overhead"""

    def __init__(self, worker_url="http://127.0.0.1:8777"):
        """Initialize HTTP client - no model loading"""
        self.worker_url = worker_url
        self.timeout = 30  # HTTP timeout for transcription requests

        logger.info(f"WhisperHTTPClient initialized - worker: {worker_url}")

        # Test connection to worker
        self._test_connection()

    def _test_connection(self):
        """Test connection to model worker service"""
        try:
            response = requests.get(f"{self.worker_url}/health", timeout=5)
            if response.status_code == 200:
                health = response.json()
                if health.get("models_loaded"):
                    logger.info("✅ Model worker connection verified - ready for ASR")
                else:
                    logger.warning("⚠️ Model worker connected but models not loaded")
            else:
                logger.warning(f"Model worker health check failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Cannot connect to model worker: {e}")
            logger.error("Make sure model worker service is running:")
            logger.error("sudo systemctl start netovo-model-worker")

    def transcribe_file(self, audio_file):
        """
        Transcribe audio file via HTTP API

        Args:
            audio_file (str): Path to audio file

        Returns:
            str: Transcribed text or empty string if failed
        """
        if not os.path.exists(audio_file):
            logger.error(f"Audio file not found: {audio_file}")
            return ""

        try:
            start_time = time.time()
            file_size = os.path.getsize(audio_file)
            logger.info(f"Transcribing via HTTP: {audio_file} ({file_size} bytes)")

            # Make HTTP request to model worker
            response = requests.post(
                f"{self.worker_url}/transcribe",
                json={"path": audio_file},
                timeout=self.timeout
            )

            duration = time.time() - start_time

            if response.status_code == 200:
                result = response.json()
                text = result.get("text", "").strip()
                confidence = result.get("confidence", 0.0)

                logger.info(f"ASR HTTP result ({duration:.2f}s): '{text[:50]}...' (conf: {confidence:.2f})")
                return text

            elif response.status_code == 503:
                logger.error("Model worker service unavailable - models not loaded")
                return ""

            elif response.status_code == 404:
                logger.error(f"Audio file not found by worker: {audio_file}")
                return ""

            else:
                logger.error(f"ASR HTTP request failed: {response.status_code} - {response.text}")
                return ""

        except requests.exceptions.Timeout:
            logger.error(f"ASR HTTP request timed out after {self.timeout}s")
            return ""

        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to model worker - is it running?")
            logger.error("Start with: sudo systemctl start netovo-model-worker")
            return ""

        except Exception as e:
            logger.error(f"ASR HTTP transcription failed: {e}")
            return ""

    def transcribe(self, audio_file):
        """Alias for transcribe_file for compatibility"""
        return self.transcribe_file(audio_file)

# Create alias class for backward compatibility
class WhisperASRClient(WhisperHTTPClient):
    """Backward compatibility alias"""
    pass